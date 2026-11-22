"""Convert Japanese shinjitai left in Chinese script lines to simplified forms.

Only lines that are kana-free are touched, so Japanese kept on purpose (names,
songs, 『』 quoted originals) is untouched.

    python tools/polish/fix_jpkanji.py            # dry run
    python tools/polish/fix_jpkanji.py --apply
"""
import os, re, sys, csv, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jpkanji import JP2SC, TABLE

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "JPKANJI_FIXED.csv")
KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30fa\u30fc-\u30ff]")
PAT = re.compile("[" + "".join(JP2SC) + "]")


def fix_line(line):
    if not PAT.search(line) or KANA.search(line):
        return line, 0
    n = len(PAT.findall(line))
    return line.translate(TABLE), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    rows, total = [], 0
    for r, _, fs in os.walk(os.path.join(ROOT, "Zh")):
        for f in sorted(fs):
            if not f.endswith(".txt") or "中日对照" in f:
                continue
            if a.only and a.only not in f:
                continue
            p = os.path.join(r, f)
            lines = open(p, encoding="utf-8", errors="replace").read().split("\n")
            hits = 0
            for i, l in enumerate(lines):
                nl, k = fix_line(l)
                if k:
                    lines[i] = nl
                    hits += k
            if hits:
                total += hits
                rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
                rows.append({"path": rel, "replacements": hits})
                if a.apply:
                    open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    if a.apply and rows:
        with open(LOG, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["path", "replacements"], lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    print(f"{'applied' if a.apply else 'dry-run'}: {len(rows)} files, {total} replacements")


if __name__ == "__main__":
    main()
