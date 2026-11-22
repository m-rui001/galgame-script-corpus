"""Literary polish pass for Chinese scripts: rewrite by paragraph, keep the shape.

The corpus keeps one message per line, so a "paragraph" here is a run of
consecutive narrative/dialogue lines from the same scene. Each run is rewritten
as a block (so pronouns, retorts and rhythm stay coherent) but must come back
line-for-line: same count, same speaker prefixes, same quotes, same numbers,
same names, no kana, length within 0.55x-1.6x.

Rules live in docs/STYLE_ZH.md. Results are cached by source hash, and a file is
written only when every one of its runs has come back clean.

    python tools/polish/polish_pool.py --only ひぐらし --limit 500
    python tools/polish/polish_pool.py --only ひぐらし --workers 8
"""
import os, re, sys, json, time, random, hashlib, argparse, threading, collections
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"D:\mxrlib\_tools")
import ds

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, "..", "_audit", "polish_unit_cache.jsonl")
LOG = os.path.join(ROOT, "..", "_audit", "polish_log.jsonl")

KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30fa\u30fc-\u30ff]")  # 不含 U+30FB「・」
CJK = re.compile(r"[\u4e00-\u9fff]")
SPEAKER = re.compile(r"^([^\s：:（(「『]{1,8})[：:]")
QUOTES = re.compile(r"[「」『』]")
DIGITS = re.compile(r"[0-9０-９]+")

PROMPT_VERSION = "v1"
MAX_LINES = 12
MAX_CHARS = 520
MIN_LEN = 8

SYS = (
    "你是中文小说编辑。任务：润色日译中的视觉小说正文，把它改成地道的中文，"
    "保留全部情节、人物关系与信息，行数一行不多一行不少。\n"
    "病灶与改法：\n"
    "1. 拆长句，一句一个动作；叙事句以 8~25 字为宜。\n"
    "2. 删「被」字被动，改主动或受事前置；删「进行／做出／作出／予以／摆出…的样子」这类名词化，直接用动词。\n"
    "3. 删多余的「的时候」「的话」「这件事情／这个事实／这种行为」「对于」「关于」「作为」「一个」。\n"
    "4. 句首连词（然后／于是／而且／但是／所以／因为）至多留一半，其余靠动作与断句承接。\n"
    "5. 代词能省则省（我／他／她不在每句开头重复）。\n"
    "6. 抽象形容（激烈的／强烈的／非常／十分／真的／似乎）换成可感的动作、声音、温度、触觉。\n"
    "7. 对白要短，要有声口；人物口癖保留（如梨花句尾「…的说」）。\n"
    "8. 和制汉语改中文常用说法（呆然→愣住、一瞬→刹那、无念→不甘）。\n"
    "硬约束：不改行首说话人前缀（如「圭一：」）与「」「」『』引号；不改人名、数字、术语、专名、伏笔；"
    "不添不删情节；不合并、不拆分行；不解释、不加注；中文行内不得出现假名。\n"
    "只输出 JSON 字符串数组，长度与输入等长，逐行一一对应。"
)


def polishable(line):
    s = line.strip()
    if len(s) < MIN_LEN or KANA.search(s):
        return False
    if len(CJK.findall(s)) < 3:
        return False
    if SPEAKER.fullmatch(s) or re.fullmatch(r"[「『].{0,2}[」』]", s):
        return False
    return True


def build_segments(lines, lo=0, hi=None):
    """Runs of consecutive polishable lines, split by MAX_LINES/MAX_CHARS."""
    hi = len(lines) if hi is None else hi
    segs, cur, cur_chars = [], [], 0

    def flush():
        nonlocal cur, cur_chars
        if cur:
            segs.append(cur)
        cur, cur_chars = [], 0

    for i in range(lo, hi):
        if polishable(lines[i]):
            cur.append(i)
            cur_chars += len(lines[i])
            if len(cur) >= MAX_LINES or cur_chars >= MAX_CHARS:
                flush()
        else:
            flush()
    flush()
    return segs


def parse_arr(txt, n):
    txt = (txt or "").strip()
    if txt.startswith("```"):
        txt = txt.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    for i, ch in enumerate(txt):
        if ch not in "[{":
            continue
        try:
            obj, _ = json.JSONDecoder().raw_decode(txt[i:])
        except Exception:
            continue
        if isinstance(obj, dict):
            for key in ("lines", "result", "polished", "text"):
                if isinstance(obj.get(key), list):
                    obj = obj[key]
                    break
            else:
                vals = [v for v in obj.values() if isinstance(v, list)]
                obj = vals[0] if vals else None
        if isinstance(obj, list) and len(obj) == n and all(isinstance(x, str) for x in obj):
            return [x.strip() for x in obj]
    return None


def check(src, out):
    """Per-line structural checks. Returns (ok, reason)."""
    a, b = src.strip(), out.strip()
    if not b:
        return False, "empty"
    if KANA.search(b):
        return False, "kana"
    sa, sb = SPEAKER.match(a), SPEAKER.match(b)
    if bool(sa) != bool(sb):
        return False, "speaker"
    if sa and sa.group(1) != sb.group(1):
        return False, "speaker-name"
    qa = a.count("「") + a.count("『")
    if qa != b.count("「") + b.count("『"):
        return False, "quotes"
    if sorted(DIGITS.findall(a)) != sorted(DIGITS.findall(b)):
        return False, "digits"
    if len(CJK.findall(a)) >= 4 and len(CJK.findall(b)) < 2:
        return False, "too-short"
    r = len(b) / max(1, len(a))
    if not (0.55 <= r <= 1.6):
        return False, f"length:{r:.2f}"
    return True, ""


def call_polish(idx, lines, ctx):
    payload = {"context": [lines[i].strip() for i in ctx],
               "lines": [lines[i].strip() for i in idx]}
    prompt = json.dumps(payload, ensure_ascii=False)
    for model in ("deepseek-flash", "deepseek-v4.1-flash", "glm-5.3"):
        try:
            out = ds.chat([{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
                          model=model, max_tokens=max(1200, 160 * len(idx) + 400),
                          temperature=0.25, timeout=240, attempts=2)
        except Exception:
            continue
        arr = parse_arr(out, len(idx))
        if arr is None:
            continue
        good, res = True, []
        for s, o in zip([lines[i] for i in idx], arr):
            ok, why = check(s, o)
            if not ok:
                good = False
                break
            res.append(o)
        if good:
            return res
    # fall back to smaller runs, then to single lines
    if len(idx) > 4:
        half = len(idx) // 2
        left = call_polish(idx[:half], lines, ctx)
        right = call_polish(idx[half:], lines, ctx[-2:] + idx[:half])
        if left is not None and right is not None:
            return left + right
        return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="substring of filename")
    ap.add_argument("--limit", type=int, default=0, help="max segments this run")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--path", default=None, help="exact relative path")
    ap.add_argument("--dry", action="store_true", help="list segments only")
    a = ap.parse_args()

    targets = []
    zh = os.path.join(ROOT, "Zh")
    for r, _, fs in os.walk(zh):
        for f in sorted(fs):
            if not f.endswith(".txt") or "中日对照" in f:
                continue
            if a.path and os.path.relpath(os.path.join(r, f), ROOT).replace(os.sep, "/") != a.path:
                continue
            if not a.path and a.only and a.only not in f:
                continue
            targets.append(os.path.join(r, f))
    if not targets:
        print("no target")
        return

    cache = {}
    if os.path.exists(CACHE):
        for l in open(CACHE, encoding="utf-8"):
            try:
                r = json.loads(l)
                cache[r["k"]] = r["t"]
            except Exception:
                pass
    lock = threading.RLock()
    logf = open(LOG, "a", encoding="utf-8")

    results = collections.defaultdict(dict)
    file_lines, remaining, units = {}, {}, []
    for p in targets:
        rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
        lines = open(p, encoding="utf-8").read().split("\n")
        file_lines[rel] = lines
        remaining[rel] = 0
        for seg in build_segments(lines):
            src = [lines[i].strip() for i in seg]
            k = hashlib.sha1((PROMPT_VERSION + json.dumps(src, ensure_ascii=False)).encode()).hexdigest()
            units.append((rel, seg, src, k))
    if a.limit:
        units = units[:a.limit]

    pending = []
    for rel, seg, src, k in units:
        remaining[rel] += 1
        if k in cache:
            for i, tx in zip(seg, cache[k]):
                results[rel][i] = tx
            remaining[rel] -= 1
        else:
            pending.append((rel, seg, src, k))

    print(f"files={len(file_lines)} units={len(units)} pending={len(pending)} "
          f"cached_units={len(units)-len(pending)}", flush=True)
    if a.dry:
        for rel, seg, src, k in pending[:20]:
            print(rel, len(seg), src[0][:40])
        return

    def write_file(rel):
        lines = file_lines[rel]
        for i, tx in results[rel].items():
            line = lines[i]
            lead = line[:len(line) - len(line.lstrip())]
            trail = line[len(line.rstrip()):]
            lines[i] = lead + tx.strip() + trail
        open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="\n").write("\n".join(lines))
        with lock:
            logf.write(json.dumps({"path": rel, "lines": len(results[rel])}, ensure_ascii=False) + "\n")
            logf.flush()
        print(f"WROTE {rel} ({len(results[rel])} lines)", flush=True)

    for rel in list(remaining):
        if remaining[rel] == 0 and results[rel]:
            write_file(rel)

    random.shuffle(pending)
    done = failed = 0
    cachef = open(CACHE, "a", encoding="utf-8")
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {}
        for rel, seg, src, k in pending:
            i = seg[0]
            ctx = [j for j in range(max(0, i - 3), i) if j not in seg]
            futs[ex.submit(call_polish, seg, file_lines[rel], ctx)] = (rel, seg, src, k)
        for fu in as_completed(futs):
            rel, seg, src, k = futs[fu]
            try:
                arr = fu.result()
            except Exception:
                arr = None
            done += 1
            with lock:
                if arr is None:
                    failed += 1
                    remaining[rel] -= 1
                    print(f"FAIL {rel} {seg[0]} {src[0][:36]}", flush=True)
                else:
                    cachef.write(json.dumps({"k": k, "t": arr}, ensure_ascii=False) + "\n")
                    cachef.flush()
                    for i, tx in zip(seg, arr):
                        results[rel][i] = tx
                    remaining[rel] -= 1
                    if remaining[rel] == 0:
                        write_file(rel)
                if done % 25 == 0:
                    print(f"units {done}/{len(pending)} failed={failed} usage={ds.usage()}", flush=True)
    cachef.close()
    logf.close()
    print(f"DONE units={done} failed={failed} usage={ds.usage()}", flush=True)


if __name__ == "__main__":
    main()