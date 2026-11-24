#!/usr/bin/env python3
"""校验《きっと、澄みわたる朝色よりも、》分块润色结果。

用法: python tools/polish/check_konjiki.py [001 002 ...]
默认校验 001-008。
"""
import re, sys, pathlib, collections

SRC = pathlib.Path(r"D:/mxrlib/_audit/polish_chunks/Zh_きっと、澄みわたる朝色よりも、.txt")
NAMES = ["笹丸", "崇", "桔世", "兰", "春告", "若", "半", "青姐", "青妹",
         "白组男生", "三人", "二人", "人"]
KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30fa\u30fc-\u30ff]")
NUM = re.compile(r"[0-9]+")
SPK = re.compile(r"^【([^】]{1,8})】")


def stats(t):
    return {
        "chars": len(re.sub(r"\s", "", t)),
        "kana": KANA.findall(t),
        "nums": collections.Counter(NUM.findall(t)),
        "names": {n: t.count(n) for n in NAMES},
        "spk": collections.Counter(SPK.findall("".join(
            "\n" + ln for ln in t.splitlines()))),
        "lines": len(t.splitlines()),
        "badq": len(re.findall(r'"', t)),
    }


def main(args):
    nums = args or [f"{i:03d}" for i in range(1, 9)]
    ok = True
    for n in nums:
        src = next(iter(SRC.glob(f"{n}_*.txt")))
        out = SRC / "out" / src.name
        if not out.exists():
            print(f"{src.name}: MISSING"); ok = False; continue
        a, b = stats(src.read_text(encoding="utf-8")), stats(out.read_text(encoding="utf-8"))
        r = b["chars"] / a["chars"]
        m = []
        if b["kana"]:
            m.append("kana " + "".join(b["kana"])[:24])
        if not 0.6 <= r <= 1.4:
            m.append(f"ratio {r:.2f}")
        lost = set(a["nums"]) - set(b["nums"])
        if lost:
            m.append(f"lost digits {sorted(lost)}")
        new = set(b["nums"]) - set(a["nums"])
        if new:
            m.append(f"new digits {sorted(new)}")
        ln = {k for k, v in a["names"].items() if v and not b["names"][k]}
        if ln:
            m.append(f"lost names {sorted(ln)}")
        gone = set(a["spk"]) - set(b["spk"])
        if gone:
            m.append(f"lost speakers {sorted(gone)}")
        if b["badq"]:
            m.append(f"straight quotes {b['badq']}")
        print(f"{src.name}: lines {a['lines']}->{b['lines']} ratio {r:.2f} "
              + ("OK" if not m else " | ".join(m)))
        ok = ok and not m
    print("ALL OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))