"""Validate polished chunk outputs against their source chunks (free-rewrite rules).

Usage:  python tools/polish/check_chunk.py [work_substring ...]
Scans _audit/polish_chunks/*/ for out/*.txt files and checks each against the
source chunk of the same name. With no args, checks every work directory.
"""
import os, re, sys, glob

KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30fa\u30fc-\u30ff]")
NON_WORD = re.compile(r"[^\u4e00-\u9fff0-9０-９A-Za-zＡ-Ｚａ-ｚ]")
SPK = re.compile(r"^([^\s：:（(「『]{1,6})[：:]")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.join(ROOT, "..", "_audit", "polish_chunks")


def rd(p):
    t = open(p, encoding="utf-8").read().split("\n")
    while t and t[-1] == "":
        t.pop()
    return t


def check(src, out):
    s, o = "\n".join(src), "\n".join(out)
    why = []
    if KANA.search(o):
        why.append("kana:" + "".join(sorted(set(KANA.findall(o)))))
    ds, do = sorted(re.findall(r"[0-9０-９]+", s)), sorted(re.findall(r"[0-9０-９]+", o))
    if ds != do:
        why.append(f"digits {ds}->{do}")
    a = set(m.group(1) for m in (SPK.match(l) for l in src) if m)
    b = set(m.group(1) for m in (SPK.match(l) for l in out) if m)
    if not a <= b:
        why.append("lost speakers " + ",".join(sorted(a - b)))
    ca, cb = len(NON_WORD.sub("", s)), len(NON_WORD.sub("", o))
    r = cb / max(1, ca)
    if not 0.6 <= r <= 1.4:
        why.append(f"ratio {r:.2f}")
    return why, (len(src), len(out), ca, cb, r)


def _unesc(p):
    return p.encode("utf-8").decode("unicode_escape") if "\\u" in p else p


ANCHORS = {"zhongmo": "\u7d42\u672b\u306b\u3088\u305b\u3066_[\u840c",
           "yumemi": "\u5922\u898b\u30f6\u4e18"}


def main():
    pats = [ANCHORS.get(a, a) for a in sys.argv[1:]]
    dirs = sorted(glob.glob(os.path.join(BASE, "*")))
    for d in dirs:
        outs = sorted(glob.glob(os.path.join(glob.escape(d), "out", "*.txt")))
        if not outs:
            continue
        if pats and not any(p in d for p in pats):
            continue
        print(os.path.basename(d))
        for op in outs:
            sp = os.path.join(d, os.path.basename(op))
            if not os.path.exists(sp):
                print("    ?  no source for", os.path.basename(op))
                continue
            why, st = check(rd(sp), rd(op))
            print(f"    {'OK ' if not why else 'BAD'} {os.path.basename(op)}: "
                  f"lines {st[0]}->{st[1]}, chars {st[2]}->{st[3]} ({st[4]:.2f}) "
                  + "| ".join(why))


if __name__ == "__main__":
    main()