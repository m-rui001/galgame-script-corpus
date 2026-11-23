#!/usr/bin/env python3
"""校验 out/ 下逐段润色结果与 chunk 原文的逐行对应关系。

用法：
    python tools/polish/verify_chunks.py <chunk_dir> [--fix-report]
"""
import re
import sys
import difflib
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = SRC / "out"

KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")
SPEAKER = re.compile(r"^([^：:「」『』\s]{1,14})：")
NAMES = ["木乃实", "雾岛", "和马", "朱莉", "委员长", "恶魔", "契约", "寿命"]
QUOTES = ["「", "」", "『", "』"]


def ratio_bounds(old: str, new: str) -> bool:
    o, n = len(old), len(new)
    if o == 0:
        return n == 0
    if o <= 6:
        return n <= max(12, o * 2)
    return 0.55 * o <= n <= 1.6 * o


def main() -> int:
    bad = 0
    files = sorted(p for p in SRC.glob("*.txt") if p.name != "meta.json")
    missing = []
    for f in files:
        o = OUT / f.name
        if not o.exists():
            missing.append(f.name)
            continue
        a = f.read_text(encoding="utf-8").split("\n")
        b = o.read_text(encoding="utf-8").split("\n")
        errs = []
        if len(a) != len(b):
            errs.append(f"行数不一致: src={len(a)} out={len(b)}")
            for i, s in enumerate(
                difflib.unified_diff([x[:20] for x in a], [x[:20] for x in b],
                                     "src", "out", n=0, lineterm="")
            ):
                if i > 40:
                    errs.append("  ...diff 截断")
                    break
                if s.startswith(("+", "-", "@")):
                    errs.append("  " + s[:120])
        for i, (x, y) in enumerate(zip(a, b), 1):
            if x == "" or x.strip() == "":
                if y.strip() != "":
                    errs.append(f"L{i}: 空行被改写")
                continue
            if y.strip() == "":
                errs.append(f"L{i}: 行被清空")
                continue
            sx, sy = SPEAKER.match(x), SPEAKER.match(y)
            if bool(sx) != bool(sy):
                errs.append(f"L{i}: 说话人前缀丢失/新增")
            elif sx and sy and sx.group(1) != sy.group(1):
                errs.append(f"L{i}: 说话人变了 {sx.group(1)!r}->{sy.group(1)!r}")
            for q in QUOTES:
                if x.count(q) != y.count(q):
                    errs.append(f"L{i}: 引号 {q} 数 {x.count(q)}->{y.count(q)}")
                    break
            if KANA.search(y):
                errs.append(f"L{i}: 含假名 {KANA.search(y).group()}")
            if not ratio_bounds(x, y):
                errs.append(f"L{i}: 长度 {len(x)}->{len(y)}")
            for nm in NAMES:
                if (nm in x) != (nm in y):
                    errs.append(f"L{i}: 专名 {nm} 有增删")
            dx = re.findall(r"\d+", x)
            dy = re.findall(r"\d+", y)
            if dx != dy:
                errs.append(f"L{i}: 数字 {dx}->{dy}")
        if errs:
            bad += 1
            print(f"✗ {f.name}")
            for e in errs[:60]:
                print("   " + e)
        else:
            print(f"✓ {f.name} ({len(a)} 行)")
    for m in missing:
        print(f"… 未产出: {m}")
    print(f"\n不合格文件: {bad} / {len(files)}")
    return 1 if bad or missing else 0


if __name__ == "__main__":
    sys.exit(main())