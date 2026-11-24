"""Rejoin narration the extraction split mid-sentence.

Japanese script extraction often emits one *message* per line, and messages often
end in the middle of a sentence: the line stops after 「，」 or with no punctuation
at all, and the sentence continues on the next line. Read as prose that is a
stutter; 1.6 million such breaks exist across the Chinese scripts.

This pass joins a line into the next one when, and only when:

* the line carries no speaker prefix and does not open a `「`/`『` quotation,
* it does not end with terminal punctuation (。！？…」』）♪☆★～—),
* it is at least 6 characters,
* the next line is not a speaker line, does not open a quotation, and is not blank.

Nothing inside a line is rewritten; only the boundary is removed. Paragraphs
(blank lines) are never crossed. Quote-only lines and dialogue stay untouched.

    python tools/polish/join_fragments.py --only 水仙3      # one file, dry run
    python tools/polish/join_fragments.py --apply
"""
import os, re, sys, csv, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "FRAGMENTS_JOINED.csv")

END = re.compile(r"[。！？…」』）)♪☆★～—]$")
SPK = re.compile(r"^[^\s：:（(「『]{1,6}[：:]")
OPEN = ("「", "『", "“", "‘")


def joinable(a, b):
    if not a or not b:
        return False
    if END.search(a) or len(a) < 6:
        return False
    if SPK.match(a) or a.startswith(OPEN):
        return False
    if SPK.match(b) or b.startswith(OPEN) or b.startswith("　"):
        return False
    # 只处理「逗号/分号/破折号收尾」这种明确断在半句的地方
    if not a.endswith(("，", "、", "；", "——", "……")):
        return False
    # 任一侧含引号或冒号就不动，避免把对白粘到旁白上
    quoted = re.compile(r"[「」『』“”‘’乽乿]|[：:]")
    if quoted.search(a) or quoted.search(b):
        return False
    return True


def unclosed_quote(t):
    return t.count("「") > t.count("」")


def join_dialogue(lines, limit=3):
    """把被切成两三个对话框的同一句对白接回去。"""
    out, joins, i = [], 0, 0
    while i < len(lines):
        cur = lines[i]
        span = 0
        while (i + 1 < len(lines) and span < limit and unclosed_quote(cur)
               and lines[i + 1].strip()
               and not lines[i + 1].strip().startswith(("「", "『"))
               and not SPK.match(lines[i + 1].strip())):
            cur = cur.rstrip() + lines[i + 1].strip()
            i += 1
            span += 1
            joins += 1
        out.append(cur)
        i += 1
    return out, joins


def join_lines(lines, limit=8):
    out, joins = [], 0
    i = 0
    n = len(lines)
    while i < n:
        cur = lines[i]
        span = 0
        while i + 1 < n and span < limit and joinable(cur.rstrip(), lines[i + 1].strip()):
            nxt = lines[i + 1].strip()
            cur = cur.rstrip() + nxt
            i += 1
            span += 1
            joins += 1
        out.append(cur)
        i += 1
    return out, joins


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
            new, joins = join_lines(lines)
            new, dj = join_dialogue(new)
            joins += dj
            if not joins:
                continue
            rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
            rows.append({"path": rel, "joins": joins, "lines_before": len(lines),
                         "lines_after": len(new)})
            total += joins
            if a.apply:
                open(p, "w", encoding="utf-8", newline="\n").write("\n".join(new))
            elif a.only:
                for k in range(min(6, len(new))):
                    print("  ", new[k][:90])
    if a.apply and rows:
        with open(LOG, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["path", "joins", "lines_before", "lines_after"],
                               lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    print(f"{'applied' if a.apply else 'dry-run'}: {len(rows)} files, {total} joins, "
          f"{sum(r['lines_before'] - r['lines_after'] for r in rows)} lines removed")


if __name__ == "__main__":
    main()