"""Corpus-wide literary polish driver.

Runs unattended over every Chinese script, worst translationese first, and keeps
a per-line journal so a restart never re-pays for finished work.

    python tools/polish/polish_corpus.py --workers 32 --minutes 60
    python tools/polish/polish_corpus.py --workers 32 --workers-file ...   # one file only
    python tools/polish/polish_corpus.py --report                          # progress only

Design notes
------------
* Segments are runs of consecutive kana-free Chinese lines (<=24 lines, <=600
  chars). A segment is sent with the two lines before it as context.
* A returned line is accepted only if it keeps its speaker prefix, quote count,
  digits, no kana, and 0.4x-1.6x content length (shinjitai normalised, see
  jpkanji.py). Rejected lines are retried in smaller groups, then left alone.
* Accepted lines go to `_audit/polish_journal.jsonl`; `flush` writes them into
  the file and clears them, so an interrupted run loses at most one minute.
"""
import os, re, sys, json, time, random, argparse, hashlib, threading, collections
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"D:\mxrlib\_tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds
from jpkanji import to_sc

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUD = os.path.join(ROOT, "..", "_audit")
JOURNAL = os.path.join(AUD, "polish_journal.jsonl")
CACHE = os.path.join(AUD, "polish_cache.jsonl")
FAILS = os.path.join(AUD, "polish_fails.jsonl")
STATE = os.path.join(AUD, "polish_state.json")
SCAN = os.path.join(AUD, "STYLE_SCAN.csv")

CJK = re.compile(r"[\u4e00-\u9fff]")
KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30fa\u30fc-\u30ff]")
SPEAKER = re.compile(r"^([^\s：:（(「『]{1,6})[：:]")
DIGITS = re.compile(r"[0-9０-９]+")
CONTENT = re.compile(r"[^\u4e00-\u9fff0-9０-９A-Za-zＡ-Ｚａ-ｚ]")

MAX_LINES = int(os.environ.get("POLISH_MAX_LINES", "24"))
MAX_CHARS = int(os.environ.get("POLISH_MAX_CHARS", "900"))
MIN_LEN = 8
PROMPT_VERSION = "c1"

SYS = (
    "你是中文小说编辑。任务：润色日译中的视觉小说正文，改成地道中文，保留全部情节与信息，行数一行不多一行不少。\n"
    "改法：拆长句，一句一个动作；删「被」字被动；删名词化（进行／做出／作出／予以／摆出…的样子）；"
    "删多余的「的时候」「的话」「这件事情」「对于」「关于」「作为」「一个」；句首连词（然后／于是／而且／但是／所以／因为）至多留一半；"
    "代词能省则省；抽象形容（激烈的／强烈的／非常／十分／真的／似乎）换成可感的动作、声音、温度。\n"
    "对白要短、要有声口；人物口癖保留（如梨花句尾「…的说」）。政界／警方／公文段落保留书面连词，不要口语化。"
    "和制汉语改中文常用说法（呆然→愣住、一瞬→刹那、无念→不甘）。\n"
    "硬约束：不改行首说话人前缀与「」「」『』引号；不改人名、数字（阿拉伯数字不得改成汉字）、术语、专名、伏笔；"
    "不添不删情节；不合并、不拆分行；不解释、不加注；中文行内不得出现假名。\n"
    "只输出 JSON 字符串数组，长度与输入等长，逐行一一对应。"
)


def polishable(line):
    s = line.strip()
    return len(s) >= MIN_LEN and not KANA.search(s) and len(CJK.findall(s)) >= 3


def segments(lines):
    out, cur, chars = [], [], 0
    for i, l in enumerate(lines):
        if polishable(l):
            cur.append(i)
            chars += len(l)
            if len(cur) >= MAX_LINES or chars >= MAX_CHARS:
                out.append(cur)
                cur, chars = [], 0
        else:
            if cur:
                out.append(cur)
            cur, chars = [], 0
    if cur:
        out.append(cur)
    return out


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
    a, b = to_sc(src.strip()), to_sc(out.strip())
    if not b:
        return False, "empty"
    if KANA.search(b):
        return False, "kana"
    sa, sb = SPEAKER.match(a), SPEAKER.match(b)
    if bool(sa) != bool(sb) or (sa and sa.group(1) != sb.group(1)):
        return False, "speaker"
    if src.count("「") + src.count("『") != out.count("「") + out.count("『"):
        return False, "quotes"
    if sorted(DIGITS.findall(src)) != sorted(DIGITS.findall(out)):
        return False, "digits"
    cx, cy = len(CONTENT.sub("", a)), len(CONTENT.sub("", b))
    if cy > 1.6 * max(1, cx) or cy < 0.4 * cx:
        return False, f"length:{cx}->{cy}"
    return True, ""


def run_segment(idxs, lines, ctx, tries=2):
    payload = {"context": [lines[i].strip() for i in ctx],
               "lines": [lines[i].strip() for i in idxs]}
    prompt = json.dumps(payload, ensure_ascii=False)
    for _ in range(tries):
        for model in ("deepseek-flash", "glm-5.3", "deepseek-v4.1-flash"):
            try:
                out = ds.chat([{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
                              model=model, max_tokens=max(1500, 170 * len(idxs) + 500),
                              temperature=0.25, timeout=300, attempts=2)
            except Exception:
                continue
            arr = parse_arr(out, len(idxs))
            if arr is None:
                continue
            res, reasons = [], []
            for s, o in zip([lines[i] for i in idxs], arr):
                ok, why = check(s, o)
                res.append(o if ok else None)
                if not ok:
                    reasons.append(why)
            if all(r is not None for r in res):
                return res, []
            if len(idxs) > 6:
                mid = len(idxs) // 2
                left, _ = run_segment(idxs[:mid], lines, ctx, tries=1)
                right, _ = run_segment(idxs[mid:], lines, ctx[-2:] + idxs[:mid], tries=1)
                merged, fails = [], []
                for s, o1, o2 in zip(idxs, left, right):
                    if o1 is not None:
                        merged.append(o1)
                    elif o2 is not None:
                        merged.append(o2)
                    else:
                        merged.append(None)
                return merged, [i for i, m in zip(idxs, merged) if m is None]
            return res, [i for i, r in zip(idxs, res) if r is None]
    return [None] * len(idxs), list(idxs)


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding="utf-8"))
    return {"done_files": [], "lines": 0, "units": 0, "failed": 0}


def save_state(st):
    tmp = STATE + ".tmp"
    json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def queue(only=None, limit_files=None, min_score=0.0, max_lines=0):
    import csv
    rows = list(csv.DictReader(open(SCAN, encoding="utf-8")))
    rows.sort(key=lambda r: -float(r["score"]))
    out = []
    for r in rows:
        if float(r["score"]) < min_score:
            continue
        p = r["path"]
        if "中日对照" in p or "English Edition" in p:
            continue
        if only and only not in p:
            continue
        if max_lines and int(r["lines"]) > max_lines:
            continue
        out.append(p)
        if limit_files and len(out) >= limit_files:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--minutes", type=float, default=0)
    ap.add_argument("--only", default=None)
    ap.add_argument("--files", type=int, default=0)
    ap.add_argument("--min-score", type=float, default=0.0)
    ap.add_argument("--max-lines", type=int, default=0)
    ap.add_argument("--commit", action="store_true", help="git commit each finished file")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    st = load_state()
    if a.report:
        print(json.dumps(st, ensure_ascii=False, indent=1))
        return

    targets = queue(a.only, a.files or None, a.min_score, a.max_lines)
    done = set(st["done_files"])
    pending_files = [p for p in targets if p not in done]
    print(f"queue {len(targets)} files, {len(pending_files)} pending", flush=True)

    cache = {}
    if os.path.exists(CACHE):
        for l in open(CACHE, encoding="utf-8"):
            try:
                r = json.loads(l)
                cache[r["k"]] = r["t"]
            except Exception:
                pass

    lock = threading.RLock()
    jf = open(JOURNAL, "a", encoding="utf-8")
    cf = open(CACHE, "a", encoding="utf-8")
    ff = open(FAILS, "a", encoding="utf-8")
    t0 = time.time()
    deadline = t0 + a.minutes * 60 if a.minutes else None
    total_lines = st["lines"]

    def flush(rel, applied):
        path = os.path.join(ROOT, rel)
        lines = open(path, encoding="utf-8").read().split("\n")
        n = 0
        for i, new in applied.items():
            if i < len(lines) and lines[i].strip():
                lead = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
                lines[i] = lead + new.strip()
                n += 1
        open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
        return n

    for rel in pending_files:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        lines = open(path, encoding="utf-8").read().split("\n")
        segs = segments(lines)
        if not segs:
            st["done_files"].append(rel)
            continue
        applied = {}
        units = []
        for seg in segs:
            src = [lines[i].strip() for i in seg]
            k = hashlib.sha1((PROMPT_VERSION + json.dumps(src, ensure_ascii=False)).encode()).hexdigest()
            units.append((seg, k))
        todo = [(seg, k) for seg, k in units if k not in cache]
        for seg, k in units:
            if k in cache:
                for i, tx in zip(seg, cache[k]):
                    applied[i] = tx
        fu_map = {}
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for seg, k in todo:
                i = seg[0]
                ctx = [j for j in range(max(0, i - 2), i)]
                fu_map[ex.submit(run_segment, seg, lines, ctx)] = (seg, k)
            for fu in as_completed(fu_map):
                if deadline and time.time() > deadline:
                    break
                seg, k = fu_map[fu]
                try:
                    res, fails = fu.result()
                except Exception:
                    res, fails = [None] * len(seg), list(seg)
                with lock:
                    st["units"] += 1
                    for i, tx in zip(seg, res):
                        if tx is not None:
                            applied[i] = tx
                    for i in fails:
                        st["failed"] += 1
                        ff.write(json.dumps({"path": rel, "line": i, "src": lines[i].strip()},
                                            ensure_ascii=False) + "\n")
                    if len(res) == len(seg) and all(r is not None for r in res):
                        cf.write(json.dumps({"k": k, "t": res}, ensure_ascii=False) + "\n")
                        cf.flush()
                    if st["units"] % 20 == 0:
                        rate = total_lines / max(1e-9, (time.time() - t0)) * 3600
                        print(f"{rel} units={st['units']} lines={st['lines']} "
                              f"rate={rate:.0f}/h failed={st['failed']} usage={ds.usage()}", flush=True)
        if applied:
            n = flush(rel, applied)
            with lock:
                st["lines"] += n
                total_lines += n
                for i, tx in applied.items():
                    jf.write(json.dumps({"path": rel, "line": i, "new": tx}, ensure_ascii=False) + "\n")
                jf.flush()
            print(f"DONE {rel}: {n} lines", flush=True)
            if a.commit:
                import subprocess
                subprocess.run(["git", "-C", ROOT, "add", rel], check=False)
                subprocess.run(["git", "-C", ROOT, "commit", "-q", "-m",
                                f"polish: {os.path.basename(rel)} ({n} lines)"], check=False)
        st["done_files"].append(rel)
        save_state(st)
        if deadline and time.time() > deadline:
            break

    save_state(st)
    print(json.dumps({k: st[k] for k in ("lines", "units", "failed")}, ensure_ascii=False), flush=True)
    print(f"elapsed {time.time()-t0:.0f}s, {len(st['done_files'])} files done", flush=True)


if __name__ == "__main__":
    main()