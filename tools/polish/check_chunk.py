#!/usr/bin/env python3
"""Chunk polish checker for _audit/polish_chunks/<work>/.

Compares each source block NNN_*.txt with out/NNN_*.txt:
  - no kana in output
  - arabic-digit set of source must be subset of output
  - speaker prefixes ("名字：") preserved
  - char count (punctuation stripped) ratio 0.6-1.4
  - quote style sanity: 「」count parity per block not required, just report

Usage: python tools/polish/check_chunk.py <work-substring> [NNN ...]
"""
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path("D:/mxrlib/_audit/polish_chunks")

KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u31f0-\u31ff\uff66-\uff9f]")
DIGITS = re.compile(r"\d+")
SPEAKER = re.compile(r"^([^\s「」『』（）：:]{1,12})[：:]")


def body_chars(text: str) -> int:
    """Count chars excluding whitespace and punctuation/symbols."""
    n = 0
    for ch in text:
        if ch.isspace():
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("P") or cat.startswith("S"):
            continue
        n += 1
    return n


def lines(path: Path):
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def check(src: Path, out: Path):
    s, o = lines(src), lines(out)
    stext, otext = "\n".join(s), "\n".join(o)
    errs = []

    kana = KANA.findall(otext)
    if kana:
        errs.append(f"kana in output: {''.join(sorted(set(kana)))[:40]} ({len(kana)}x)")

    sd, od = set(DIGITS.findall(stext)), set(DIGITS.findall(otext))
    missing = sd - od
    if missing:
        errs.append(f"missing digits: {sorted(missing)}")
    extra = od - sd
    if extra:
        errs.append(f"new digits: {sorted(extra)}")

    ss = {m.group(1) for ln in s if (m := SPEAKER.match(ln))}
    os_ = {m.group(1) for ln in o if (m := SPEAKER.match(ln))}
    if ss - os_:
        errs.append(f"missing speakers: {sorted(ss - os_)}")
    if os_ - ss:
        errs.append(f"new speakers: {sorted(os_ - ss)}")

    sb, ob = body_chars(stext), body_chars(otext)
    ratio = ob / sb if sb else 0
    if not (0.6 <= ratio <= 1.4):
        errs.append(f"length ratio {ratio:.2f} outside 0.6-1.4 (src {sb} -> out {ob})")

    return errs, ratio, sb, ob


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    key, only = sys.argv[1], set(sys.argv[2:])
    dirs = [d for d in ROOT.iterdir() if d.is_dir() and key in d.name]
    if not dirs:
        sys.exit(f"no chunk dir matching {key!r} under {ROOT}")
    d = dirs[0]
    outdir = d / "out"
    srcs = sorted(p for p in d.glob("[0-9][0-9][0-9]_*.txt"))
    if only:
        srcs = [p for p in srcs if p.name[:3] in only]
    bad = 0
    for src in srcs:
        out = outdir / src.name
        if not out.exists():
            print(f"{src.name}: MISSING out/")
            bad += 1
            continue
        errs, ratio, sb, ob = check(src, out)
        status = "OK  " if not errs else "FAIL"
        print(f"{status} {src.name}: ratio {ratio:.2f} ({sb}->{ob})")
        for e in errs:
            print(f"     - {e}")
        bad += bool(errs)
    print(f"\n{bad} block(s) failing")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()