#!/usr/bin/env python3
"""校验单块润色结果：假名残留、数字/专名集合、人名集合、字数区间。"""
import re
import sys
import pathlib
import collections

SRC = pathlib.Path(r"D:/mxrlib/_audit/polish_chunks/Zh_去人たち.txt")

NAMES = ["鹿南", "瑛迩", "迺罗", "枫罗", "麻理", "玛丽", "瑛三", "伊津佳", "章子", "晶子",
         "有濑", "莉莎", "莅弥", "宇沙美", "本部"]


def stats(text):
    nums = collections.Counter(re.findall(r"[0-9]+(?:\.[0-9]+)?", text))
    names = {n: text.count(n) for n in NAMES}
    return {
        "chars": len(text),
        "han": len(re.findall(r"[\u4e00-\u9fff]", text)),
        "kana": re.findall(r"[\u3040-\u30ff]", text),
        "nums": nums,
        "names": names,
    }


def main(names):
    ok = True
    for name in names:
        src = SRC / name
        out = SRC / "out" / name
        if not out.exists():
            print(f"{name}: MISSING output")
            ok = False
            continue
        a, b = src.read_text(encoding="utf-8"), out.read_text(encoding="utf-8")
        sa, sb = stats(a), stats(b)
        ratio = sb["chars"] / sa["chars"]
        msgs = []
        if sb["kana"]:
            msgs.append(f"kana {''.join(sb['kana'])[:20]}")
        if not (0.6 <= ratio <= 1.4):
            msgs.append(f"ratio {ratio:.2f}")
        lost = set(sa["nums"]) - set(sb["nums"])
        if lost:
            msgs.append(f"missing digits {sorted(lost)}")
        gained = set(sb["nums"]) - set(sa["nums"])
        if gained:
            msgs.append(f"new digits {sorted(gained)}")
        lostn = {n for n in NAMES if sa["names"][n] and not sb["names"][n]}
        if lostn:
            msgs.append(f"missing names {sorted(lostn)}")
        status = "OK " if not msgs else "BAD"
        if msgs:
            ok = False
        print(f"{status} {name} ratio={ratio:.2f} han={sb['han']} " + "; ".join(msgs))
    return 0 if ok else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = [p.name for p in sorted(SRC.glob("*.txt"))]
    sys.exit(main(args))