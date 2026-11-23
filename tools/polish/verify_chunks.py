#!/usr/bin/env python3
"""校验润色 chunk：行数/说话人前缀/引号数/假名/长度比/空行对应。"""
import re
import sys
import unicodedata
from pathlib import Path

KANA = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\uFF66-\uFF9D]')
SPK = re.compile(r'^([^「『\s]{1,10})：')
QUOTES = '「」『』'


def cjk_len(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in s)


def check(src: Path, out: Path):
    s = src.read_text(encoding='utf-8').split('\n')
    if not out.exists():
        return [f'MISSING {out}']
    o = out.read_text(encoding='utf-8').split('\n')
    errs = []
    if len(s) != len(o):
        errs.append(f'行数 {len(s)} -> {len(o)}')
    for i, (a, b) in enumerate(zip(s, o), 1):
        if not a.strip():
            if b.strip():
                errs.append(f'{i}: 应为空行 -> {b[:20]}')
            continue
        if not b.strip():
            errs.append(f'{i}: 空行 (漏译?)')
            continue
        if KANA.search(b):
            errs.append(f'{i}: 含假名 {KANA.findall(b)[:3]}')
        sa, sb = SPK.match(a), SPK.match(b)
        if bool(sa) != bool(sb):
            errs.append(f'{i}: 说话人前缀丢失/新增')
        elif sa and sa.group(1) != sb.group(1):
            errs.append(f'{i}: 说话人 {sa.group(1)} -> {sb.group(1)}')
        for q in QUOTES:
            if a.count(q) != b.count(q):
                errs.append(f'{i}: 引号 {q} {a.count(q)}->{b.count(q)}')
        la, lb = cjk_len(a), cjk_len(b)
        if lb < 0.55 * la or lb > 1.6 * la:
            errs.append(f'{i}: 长度 {la}->{lb} ({lb/la:.2f})')
    return errs


def main():
    d = Path(sys.argv[1])
    outs = d / 'out'
    total = 0
    for src in sorted(d.glob('[0-9][0-9][0-9]_*.txt')):
        errs = check(src, outs / src.name)
        total += len(errs)
        if errs:
            print(f'== {src.name} ({len(errs)})')
            for e in errs[:25]:
                print('   ', e)
    print(f'TOTAL ISSUES: {total}')


if __name__ == '__main__':
    main()