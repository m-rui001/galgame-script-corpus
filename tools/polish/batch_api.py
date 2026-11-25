"""Drive chunk polishing over an OpenAI-compatible endpoint.

The sub-agent path is nicer when it works (isolated context, real tools) but it
is also the first thing to break when a model endpoint changes its API contract.
This script is the fallback: one chat completion per chunk, straight from the
shell, no tool use. It writes the answer to `out/<same name>` and refuses to
write a result that fails the language gate in langrules.

Providers come from ~/.pi/agent/models.json so keys stay out of this repo.

    python tools/polish/batch_api.py --workdir _audit/polish_chunks/JA_X \
        --prompt docs/prompts/ja.md --threads 3 --limit 5

Bilingual files (`--two-pass`) are cut into two single-language passes. Each
pass masks the *other* language with `@@<line>` placeholders, asks the model to
work on one language only, and then restores the masked lines by position, so
the model never has a chance to touch a line it was not asked about and the two
halves cannot drift apart.
"""
import os
import re
import sys
import json
import time
import argparse
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from langrules import lang_of, block_ok, KANA  # noqa: E402

MODELS = os.path.expanduser(os.path.join("~", ".pi", "agent", "models.json"))
# Ordered by how well they hold a long editorial brief. The flash models are
# fastest and drift toward paraphrase or outright translation, so they come last;
# the gate catches "kana lost" when one of them translates instead of editing.
PREF = ["cssm-gpt", "muse", "yanhuo888", "xcmapiorg", "grok-free", "ds-free"]

BRIEF = ("以下是一段 {n} 行的文本切片。按系统提示的要求输出改写后的全文，"
         "不要解释，不要加代码块标记，不要省略任何行：\n\n{body}")

# Simplified-only characters: a line with these and no kana is Chinese.
SIMP = re.compile(r"[这们说时过对么让还样种觉认识该东丽举义乐习乡书买亚产亲亿仅从众优伟传伤价铁边变战听问间关开长门见现实头]")
MASK = "@@"


def kind(line):
    if KANA.search(line):
        return "ja"
    if SIMP.search(line):
        return "zh"
    return "mt"


def providers():
    cfg = json.load(open(MODELS, encoding="utf-8"))["providers"]
    out = []
    for name in PREF + [n for n in cfg if n not in PREF]:
        v = cfg.get(name)
        if not v or not v.get("baseUrl") or not v.get("apiKey"):
            continue
        out.append({"name": name,
                    "url": v["baseUrl"].rstrip("/") + "/chat/completions",
                    "key": v["apiKey"],
                    "model": v["models"][0]["id"]})
    return out


def chat(prov, system, user, timeout=600):
    body = json.dumps({
        "model": prov["model"],
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.3,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(prov["url"], data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + prov["key"],
    })
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"], time.time() - t0


def strip_fence(t):
    t = t.strip()
    if t.startswith("```"):
        lines = t.split("\n")[1:]
        while lines and lines[-1].strip().startswith("```"):
            lines.pop()
        t = "\n".join(lines)
    return t.rstrip("\n")


def masked_chat(prov, system, lines, keep, tag):
    """Ask for one language only; the rest of the lines are placeholders.

    Line counts must stay 1:1 in this mode, because the untouched language is
    restored by position rather than by the model. A model that merges two lines
    is rejected here instead of silently shifting a bilingual file.
    """
    masked, originals = [], {}
    for i, l in enumerate(lines):
        if kind(l) == keep:
            masked.append(l)
        else:
            masked.append(MASK + str(i))
            originals[i] = l
    note = ("\n\n本次只改「%s」的行。形如 @@12 的行是占位符，代表另一语言的行，"
            "必须原样逐字保留、位置不变、不得删除或合并。行数必须与输入完全一致。"
            % ("日文" if keep == "ja" else "中文"))
    user = BRIEF.format(n=len(masked), body="\n".join(masked))
    txt, secs = chat(prov, system + note, user)
    got = strip_fence(txt).split("\n")
    if len(got) != len(lines):
        raise ValueError("lines %d->%d" % (len(lines), len(got)))
    for i, l in enumerate(got):
        if i in originals and l.strip() != (MASK + str(i)):
            # placeholder was rewritten: the model ignored the mask
            raise ValueError("mask %s -> %s" % (MASK + str(i), l.strip()[:12]))
    return [originals.get(i, got[i]) for i in range(len(lines))], secs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--only", default="")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--two-pass", action="store_true",
                    help="bilingual: polish JA and ZH in two masked passes")
    a = ap.parse_args()

    work = a.workdir if os.path.isabs(a.workdir) else os.path.join(ROOT, "..", a.workdir)
    system = open(a.prompt, encoding="utf-8").read()
    meta = json.load(open(os.path.join(work, "meta.json"), encoding="utf-8"))
    rel = meta["path"]
    lang = lang_of(rel)
    outdir = os.path.join(work, "out")
    os.makedirs(outdir, exist_ok=True)
    provs = providers()
    only = {x.strip() for x in a.only.split(",") if x.strip()}

    todo = []
    for c in meta["chunks"]:
        if only and c["file"] not in only:
            continue
        dst = os.path.join(outdir, c["file"])
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            continue
        todo.append(c["file"])
    if a.limit:
        todo = todo[:a.limit]
    print("%d providers, lang=%s, %d chunks to do, two_pass=%s"
          % (len(provs), lang, len(todo), a.two_pass), flush=True)

    lock = threading.Lock()
    counter = {"done": 0, "idx": 0}

    def next_prov():
        with lock:
            if not provs:
                return None
            p = provs[counter["idx"] % len(provs)]
            counter["idx"] += 1
            return p

    def one(name):
        src = open(os.path.join(work, name), encoding="utf-8").read()
        src_lines = src.split("\n")
        for _ in range(a.retries):
            prov = next_prov()
            if not prov:
                return
            try:
                if a.two_pass:
                    cur, s1 = masked_chat(prov, system, src_lines, "ja", "ja")
                    cur, s2 = masked_chat(prov, system, cur, "zh", "zh")
                    txt = "\n".join(cur)
                    secs = s1 + s2
                else:
                    txt, secs = chat(prov, system, BRIEF.format(n=len(src_lines), body=src))
                    txt = strip_fence(txt)
            except ValueError as e:
                print("  %s %s: %s" % (name, prov["name"], e), flush=True)
                continue
            except Exception as e:
                print("  %s %s: %s %s" % (name, prov["name"], type(e).__name__, str(e)[:70]), flush=True)
                continue
            ok, why = block_ok(src_lines, txt.split("\n"), lang)
            if not ok:
                print("  %s %s: gate %s" % (name, prov["name"], why), flush=True)
                continue
            if not a.dry:
                open(os.path.join(outdir, name), "w", encoding="utf-8", newline="\n").write(txt + "\n")
            with lock:
                counter["done"] += 1
            print("  %s %s %.0fs lines %d->%d" % (name, prov["name"], secs,
                  len(src_lines), len(txt.split("\n"))), flush=True)
            return
        print("  %s: gave up" % name, flush=True)

    if a.threads <= 1:
        for n in todo:
            one(n)
    else:
        with ThreadPoolExecutor(max_workers=a.threads) as ex:
            list(ex.map(one, todo))
    print("done %d/%d" % (counter["done"], len(todo)))


if __name__ == "__main__":
    main()