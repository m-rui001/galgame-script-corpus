"""Merge polished chunk outputs back into a script.

Two modes:

* default — per-line merge. A line is accepted only if it keeps its speaker
  prefix, quote counts, digits, no kana, and 0.4-1.6x content length.
* `--free` — a section may be replaced wholesale, so line counts inside it can
  change (merging short lines, splitting long ones, dropping filler). Accepted
  if the section keeps every speaker, the same digit set, no kana, and stays
  within 0.6-1.4x of the original content volume.

Chunk files are matched by the `start-end` in their name when present;
otherwise they are taken in name order with a fixed stride.

    python tools/polish/merge_job.py --path "Zh/x.txt"
    python tools/polish/merge_job.py --path "Zh/x.txt" --free
"""
import os, re, sys, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chunked_polish import slug, check, polishable, set_progress

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASES = [os.path.join(ROOT, "..", "_audit", "polish_chunks"),
         os.path.join(ROOT, "_audit", "polish_chunks")]
RANGE = re.compile(r"(\d+)-(\d+)\.txt$")
SPK = re.compile(r"^([^\s：:（(「『]{1,6})[：:]")
KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30fa\u30fc-\u30ff]")
NON_WORD = re.compile(r"[^\u4e00-\u9fff0-9０-９A-Za-zＡ-Ｚａ-ｚ]")


def find_out(rel):
    s = slug(rel)
    for b in BASES:
        p = os.path.join(b, s, "out")
        if os.path.isdir(p) and os.listdir(p):
            return p
    return None


def read_lines(p):
    return open(p, encoding="utf-8").read().split(chr(10))


def blocks_of(outdir):
    out = []
    for f in sorted(os.listdir(outdir)):
        if not f.endswith(".txt"):
            continue
        m = RANGE.search(f)
        if not m:
            continue
        out.append((int(m.group(1)), int(m.group(2)), f, os.path.join(outdir, f)))
    out.sort()
    return out


def free_ok(src_block, out_block):
    src = chr(10).join(src_block)
    out = chr(10).join(out_block)
    if not out.strip():
        return False, "empty"
    if len(KANA.findall(out)) > len(KANA.findall(src)):
        return False, "kana"
    if sorted(re.findall(r"[0-9０-９]+", src)) != sorted(re.findall(r"[0-9０-９]+", out)):
        return False, "digits"
    a = set(m.group(1) for m in (SPK.match(l) for l in src_block) if m)
    b = set(m.group(1) for m in (SPK.match(l) for l in out_block) if m)
    if not a <= b:
        return False, "speakers " + ",".join(sorted(a - b)[:3])
    ca, cb = len(NON_WORD.sub("", src)), len(NON_WORD.sub("", out))
    if not (0.6 <= cb / max(1, ca) <= 1.4):
        return False, f"length {ca}->{cb}"
    return True, ""


def merge_free(rel, outdir, dry):
    path = os.path.join(ROOT, rel)
    cur = read_lines(path)
    blocks = blocks_of(outdir)
    if not blocks:
        print("free mode: no ranged chunk outputs")
        return
    replaced, bad, new = 0, [], []
    for st, en, name, fp in blocks:
        newl = read_lines(fp)
        if newl and newl[-1] == "":
            newl = newl[:-1]
        srcb = cur[st:min(en, len(cur))]
        # 源区间与切片是否仍然对齐（自由改写会改变行数，切片随之后移）
        chunk_src = read_lines(os.path.join(os.path.dirname(fp), "..", name))
        cs = chunk_src[:-1] if chunk_src and chunk_src[-1] == "" else chunk_src
        if cs and (not srcb or cs[0].strip() != srcb[0].strip()):
            bad.append((name, "stale-range"))
            continue
        ok, why = free_ok(srcb, newl)
        if ok:
            new.append((st, min(en, len(cur)), newl))
            replaced += 1
        else:
            bad.append((name, why))
    if new and not dry:
        out, last = [], 0
        for st, en, newl in new:
            out.extend(cur[last:st])
            out.extend(newl)
            last = en
        out.extend(cur[last:])
        open(path, "w", encoding="utf-8", newline=chr(10)).write(chr(10).join(out))
    delta = sum(len(n) - (e - s) for s, e, n in new)
    if new:
        set_progress(rel, max(e for s, e, n in new))
    print(f"{outdir}\nfree mode: {replaced} sections replaced, {len(bad)} rejected, "
          f"lines {len(cur)} -> {len(cur) + delta}")
    for b in bad[:10]:
        print("  ", b)


def merge_line(rel, outdir, dry):
    path = os.path.join(ROOT, rel)
    lines = read_lines(path)
    applied = kept = 0
    bad = []
    covered = 0
    for st, en, name, fp in blocks_of(outdir):
        got = read_lines(fp)
        if got and got[-1] == "":
            got = got[:-1]
        if len(got) == en - st - 1:
            got = got + [""]
        if len(got) != en - st:
            print(f"  skip {name}: {len(got)} lines, expected {en - st}")
            continue
        covered += len(got)
        for off, pol in enumerate(got):
            i = st + off
            if i >= len(lines):
                break
            src = lines[i]
            if not src.strip() or not polishable(src):
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
    print(f"{outdir}\n{'would merge' if dry else 'merged'}: {applied} rewritten, "
          f"{kept} kept, {len(bad)} problems, covered {covered}/{len(lines)}")
    for b in bad[:10]:
        print("  ", b)
    if not dry and applied:
        set_progress(rel, max(st + en - st for st, en, name, fp in blocks_of(outdir)))
        open(path, "w", encoding="utf-8", newline=chr(10)).write(chr(10).join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--free", action="store_true")
    a = ap.parse_args()
    outdir = find_out(a.path)
    if not outdir:
        print("no out dir for", a.path)
        return
    if a.free:
        merge_free(a.path, outdir, a.dry)
    else:
        merge_line(a.path, outdir, a.dry)


if __name__ == "__main__":
    main()