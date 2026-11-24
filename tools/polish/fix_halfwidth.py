"""Half-width punctuation inside Chinese prose -> full-width.

Extraction pipelines sometimes keep ASCII `, . ! ? ;` between Chinese characters
(88k occurrences in 237 files). Chinese needs the full-width forms; the half-width
mark also breaks the rhythm because it reads as a foreign mark.

Colons are left alone: `名字:` is a legitimate speaker separator in part of the
corpus. Lines that are mostly kana are skipped.

    python tools/polish/fix_halfwidth.py            # dry run
    python tools/polish/fix_halfwidth.py --apply
"""
import os, re, sys, csv, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "HALFWIDTH_FIXED.csv")
KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30fa\u30fc-\u30ff]")
CJK = re.compile(r"[\u4e00-\u9fff]")

RULES = [
    (re.compile(r"(?<=[\u4e00-\u9fff]),(?=[\u4e00-\u9fff])"), "，"),
    (re.compile(r"(?<=[\u4e00-\u9fff]),(?=[「『])"), "，"),
    (re.compile(r"(?<=[\u4e00-\u9fff])\.(?=[\u4e00-\u9fff])"), "。"),
    (re.compile(r"(?<=[\u4e00-\u9fff])\.(?=[」』])"), "。"),
    (re.compile(r"(?<=[\u4e00-\u9fff])!(?=[\u4e00-\u9fff」』])"), "！"),
    (re.compile(r"(?<=[\u4e00-\u9fff])\?(?=[\u4e00-\u9fff」』])"), "？"),
    (re.compile(r"(?<=[\u4e00-\u9fff]);(?=[\u4e00-\u9fff])"), "；"),
]


def fix_line(line):
    if KANA.search(line) and len(KANA.findall(line)) / max(1, len(line)) > 0.05:
        return line, 0
    n = 0
    s = line
    for rx, rep in RULES:
        s2 = rx.sub(rep, s)
        if s2 != s:
            n += len(rx.findall(s))
            s = s2
    return s, n


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
                rows.append({"path": os.path.relpath(p, ROOT).replace(os.sep, "/"), "replacements": hits})
                if a.apply:
                    open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    if a.apply and rows:
        with open(LOG, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["path", "replacements"], lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    print(f"{'applied' if a.apply else 'dry-run'}: {len(rows)} files, {total} replacements")


if __name__ == "__main__":
    main()