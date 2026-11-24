"""Drop accidental duplicate lines and malformed punctuation runs.

Two extraction artefacts, both measurable and safe:

* a line repeated verbatim right below itself (same text, >= 10 chars) — the
  extractor emitted the same message twice; 19.6k occurrences in 321 files.
* punctuation runs that no Chinese writer produces: `。。`, `，，`, `，。`, `、，`,
  `。，`. Runs of `……`, `——`, `！？`, `？！` are legitimate and kept.

    python tools/polish/fix_repeats.py            # dry run
    python tools/polish/fix_repeats.py --apply
"""
import os, re, sys, csv, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "REPEATS_FIXED.csv")

BAD_RUNS = [
    (re.compile(r"。{2,}"), "。"),
    (re.compile(r"，{2,}"), "，"),
    (re.compile(r"，。"), "。"),
    (re.compile(r"。，"), "。"),
    (re.compile(r"、，"), "，"),
    (re.compile(r"，、"), "，"),
    (re.compile(r"；，"), "，"),
    (re.compile(r"，；"), "；"),
    (re.compile(r"？。"), "？"),
    (re.compile(r"！。"), "！"),
    (re.compile(r"(?<=[一-鿿])[.]{2,}(?=[一-鿿」』]|$)"), "……"),
    (re.compile(r" +(?=[，。！？；：])"), ""),
]


def fix_line(line):
    n = 0
    s = line
    for rx, rep in BAD_RUNS:
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
    rows, total_p, total_d = [], 0, 0
    for r, _, fs in os.walk(os.path.join(ROOT, "Zh")):
        for f in sorted(fs):
            if not f.endswith(".txt") or "中日对照" in f:
                continue
            if a.only and a.only not in f:
                continue
            p = os.path.join(r, f)
            lines = open(p, encoding="utf-8", errors="replace").read().split("\n")
            out, punc, dup = [], 0, 0
            for l in lines:
                nl, k = fix_line(l)
                punc += k
                if out:
                    prev = out[-1].strip()
                    if len(nl.strip()) >= 10 and nl.strip() == prev:
                        dup += 1
                        continue
                out.append(nl)
            if not punc and not dup:
                continue
            rows.append({"path": os.path.relpath(p, ROOT).replace(os.sep, "/"),
                         "punctuation": punc, "duplicates": dup})
            total_p += punc
            total_d += dup
            if a.apply:
                open(p, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    if a.apply and rows:
        with open(LOG, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["path", "punctuation", "duplicates"], lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    print(f"{'applied' if a.apply else 'dry-run'}: {len(rows)} files, "
          f"{total_p} punctuation, {total_d} duplicate lines")


if __name__ == "__main__":
    main()