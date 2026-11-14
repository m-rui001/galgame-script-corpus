"""Normalize Japanese-style punctuation in Chinese scripts.

Targets Chinese files with heavy `、` usage and no matching `，` usage.
Keeps short enumerations (`A、B、C`) intact; rewrites clause-level `、` to `，`.
Also rewrites `・・・` to `……` and long `ー` runs to `——`.

Run: python tools/normalize_punct.py
"""
import os, re, csv, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CJK = re.compile(r"[\u4e00-\u9fff]")

def normalize_line(line):
    if "、" not in line and "・・・" not in line and "ー" not in line:
        return line, 0
    n = 0
    out = line
    if "、" in out:
        parts = out.split("、")
        is_list = len(parts) >= 3 and all(len(p.strip()) <= 6 for p in parts[1:-1]) and not any("，" in p for p in parts)
        if not is_list:
            n += out.count("、")
            out = out.replace("、", "，")
    if "・・・" in out:
        n += out.count("・・・")
        out = out.replace("・・・", "……")
    out2 = re.sub(r"ー{2,}", "——", out)
    if out2 != out:
        n += 1
        out = out2
    return out, n

def main():
    rows = []
    for r, _, fs in os.walk(os.path.join(ROOT, "Zh")):
        for f in fs:
            if not f.endswith(".txt") or "中日对照" in f:
                continue
            p = os.path.join(r, f)
            rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
            s = open(p, encoding="utf-8", errors="replace").read()
            if len(s) < 3000:
                continue
            jp = s.count("、")
            cn = s.count("，")
            if jp < 20 or jp / max(1, jp + cn) < 0.8:
                continue
            lines = s.split("\n")
            total = 0
            for i, l in enumerate(lines):
                nl, n = normalize_line(l)
                if n:
                    lines[i] = nl
                    total += n
            if total:
                open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
                rows.append({"path": rel, "replacements": total, "jp_before": jp, "cn_before": cn})
    with open(os.path.join(ROOT, "PUNCT_NORMALIZED.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "replacements", "jp_before", "cn_before"])
        w.writeheader()
        w.writerows(rows)
    print(f"normalized {len(rows)} files, {sum(r['replacements'] for r in rows)} replacements")

if __name__ == "__main__":
    main()
