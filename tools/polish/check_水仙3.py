#!/usr/bin/env python3
"""校验 Zh_水仙3.txt 单块润色结果。"""
import re, sys, pathlib, collections

SRC = pathlib.Path(r"D:/mxrlib/_audit/polish_chunks/Zh_水仙3.txt")
NAMES = ["姬子", "千寻", "优花", "濑津美", "昭岛", "依诺斯", "水仙", "优花"]

def stats(t):
    return dict(chars=len(t),
                kana=re.findall(r"[\u3040-\u30ff]", t),
                nums=collections.Counter(re.findall(r"[0-9]+(?:\.[0-9]+)?", t)),
                names={n: t.count(n) for n in set(NAMES)})

def main(names):
    ok = True
    for name in names:
        src, out = SRC/name, SRC/"out"/name
        if not out.exists():
            print(f"MISSING {name}"); ok = False; continue
        a, b = src.read_text(encoding="utf-8"), out.read_text(encoding="utf-8")
        sa, sb = stats(a), stats(b)
        r = sb["chars"]/sa["chars"]
        m = []
        if sb["kana"]: m.append("kana:"+"".join(sb["kana"])[:20])
        if not 0.6 <= r <= 1.4: m.append(f"ratio {r:.2f}")
        lost = set(sa["nums"])-set(sb["nums"]); gained = set(sb["nums"])-set(sa["nums"])
        if lost: m.append(f"lost nums {sorted(lost)}")
        if gained: m.append(f"new nums {sorted(gained)}")
        ln = [n for n in NAMES if sa["names"][n] and not sb["names"][n]]
        if ln: m.append(f"lost names {sorted(set(ln))}")
        if "「" in a and "「" not in b: m.append("quote style changed")
        print(("OK  " if not m else "BAD ") + f"{name} r={r:.2f} lines {b.count(chr(10))+1} " + "; ".join(m))
        ok &= not m
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or [p.name for p in sorted(SRC.glob("*.txt"))]))