"""Merge a polished job directory back into a script, tolerating naming drift.

Agents write chunk outputs under either `<repo>/../_audit/polish_chunks/<slug>/out`
or `<repo>/_audit/polish_chunks/<slug>/out`, and sometimes re-chunk the source
themselves. This tool rebuilds the full polished text from whatever chunks are
there (portable: file names carrying `start-end`, otherwise concatenated in name
order), then merges line by line with the same checks as chunked_polish.

    python tools/polish/merge_job.py --path "Zh/葛唄.txt"
    python tools/polish/merge_job.py --path "Zh/葛唄.txt" --dry
"""
import os, re, sys, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chunked_polish import slug, check, polishable  # reuse the checker

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASES = [os.path.join(ROOT, "..", "_audit", "polish_chunks"), os.path.join(ROOT, "_audit", "polish_chunks")]
RANGE = re.compile(r"(\d+)-(\d+)\.txt$")


def find_out(rel):
    s = slug(rel)
    for b in BASES:
        p = os.path.join(b, s, "out")
        if os.path.isdir(p) and os.listdir(p):
            return p
    return None


def rebuild(outdir, n):
    files = sorted(f for f in os.listdir(outdir) if f.endswith(".txt"))
    # 先读一遍，去掉块尾多出的空行，使总行数回到源文件长度
    chunks = []
    for f in files:
        ls = open(os.path.join(outdir, f), encoding="utf-8").read().split(chr(10))
        chunks.append([f, ls])
    total = sum(len(ls) for _, ls in chunks)
    k = 0
    while total > n and k < len(chunks):
        ls = chunks[k][1]
        if ls and ls[-1] == "" and k < len(chunks) - 1:
            ls.pop()
            total -= 1
        k += 1
    text = [None] * n
    covered = [False] * n
    ranged = any(RANGE.search(f) for f, _ in chunks)
    if ranged:
        for f, lines in chunks:
            m = RANGE.search(f)
            a, b = int(m.group(1)), int(m.group(2))
            body = lines[:-1] if lines and lines[-1] == "" else lines
            if len(body) == b - a - 1:      # 末块少一个空行：补回
                body = body + [""]
            if len(body) != b - a:
                print(f"  skip {f}: {len(body)} lines, expected {b - a}")
                continue
            for k2, l in enumerate(body):
                if a + k2 < n:
                    text[a + k2] = l
                    covered[a + k2] = True
    else:
        # 顺序块：按每块固定长度平移，允许块尾多一个空行
        stride = len(chunks[0][1])
        if len(chunks) > 1 and stride > 1 and chunks[0][1][-1] == "":
            stride -= 1
        for idx, (f, lines) in enumerate(chunks):
            base = idx * stride
            for k2, l in enumerate(lines):
                i = base + k2
                if i < n:
                    text[i] = l
                    covered[i] = True
    return text, covered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    outdir = find_out(a.path)
    if not outdir:
        print("no out dir for", a.path)
        return
    path = os.path.join(ROOT, a.path)
    lines = open(path, encoding="utf-8").read().split("\n")
    cand, covered = rebuild(outdir, len(lines))
    applied = kept = 0
    bad = []
    for i, (src, pol) in enumerate(zip(lines, cand)):
        if pol is None or not src.strip() or not polishable(src):
            kept += 1
            continue
        ok, why = check(src, pol)
        if ok:
            lead = src[:len(src) - len(src.lstrip())]
            lines[i] = lead + pol.strip()
            applied += 1
        else:
            kept += 1
            bad.append((i + 1, why))
    print(f"{outdir}\n{'would merge' if a.dry else 'merged'}: {applied} rewritten, {kept} kept, {len(bad)} problems, covered {sum(covered)}/{len(lines)}")
    for b in bad[:10]:
        print("  ", b)
    if not a.dry and applied:
        open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))


if __name__ == "__main__":
    main()