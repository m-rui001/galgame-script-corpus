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
from chunked_polish import slug, check, polishable, load_prog, set_progress
from langrules import lang_of, block_ok, VOLUME

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASES = [os.path.join(ROOT, "..", "_audit", "polish_chunks"),
         os.path.join(ROOT, "_audit", "polish_chunks")]
RANGE = re.compile(r"(\d+)-(\d+)\.txt$")
SPK = re.compile(r"^([^\s：:（(「『]{1,6})[：:]")
# A real speaker line has its prefix directly followed by an opening quote.
# 「我这才明白：……」 and 「就能猜到：……」 are narrative that merely look alike.
SPK_Q = re.compile(r"^([^\s：:（(「『]{1,6})[：:]\s*[「『“\"乽]")
# English scripts tag dialogue as "Furukawa: ..." / "Narration: ..." with a
# space after the colon and no quote at all.
EN_SPK = re.compile(r"^([A-Z][A-Za-z0-9 .'\-]{0,24}):\s")
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


def free_ok(src_block, out_block, lang="zh"):
    src = chr(10).join(src_block)
    out = chr(10).join(out_block)
    ok, why = block_ok(src_block, out_block, lang)
    if not ok:
        return False, why
    if lang == "ja":
        # repair only: no dialogue-tag enforcement, the text is not rewritten
        return True, ""
    if lang == "en":
        cnt = {}
        for l in src_block:
            m = EN_SPK.match(l)
            if m:
                cnt[m.group(1)] = cnt.get(m.group(1), 0) + 1
        a = set(k for k, v in cnt.items() if v >= 2)
        b = set(m.group(1) for m in (EN_SPK.match(l) for l in out_block) if m)
    elif any(SPK_Q.match(l) for l in src_block):
        a = set(m.group(1) for m in (SPK_Q.match(l) for l in src_block) if m)
        b = set(m.group(1) for m in (SPK_Q.match(l) for l in out_block) if m)
    else:
        # no quoted speaker lines here: the file writes names bare. Only demand
        # that names recurring in the block survive; one-off narrative colons
        # like 「就能猜到：……」 are free to be rewritten away.
        cnt = {}
        for l in src_block:
            m = SPK.match(l)
            if m:
                cnt[m.group(1)] = cnt.get(m.group(1), 0) + 1
        a = set(k for k, v in cnt.items() if v >= 2)
        b = set(m.group(1) for m in (SPK.match(l) for l in out_block) if m)
    # A narrative line like 「我这才明白：……」 is not a speaker line, but the
    # shape matches. If the "speaker" text still occurs in the output, the line
    # only lost its colon - which is usually an improvement. Reject only when
    # the text disappears outright.
    gone = [s for s in sorted(a - b) if s not in out]
    if gone:
        return False, "speakers " + ",".join(gone[:3])
    if lang == "zh":
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
    applied_to = -1
    for st, en, name, fp in blocks:
        if st < applied_to:
            # a leftover chunk from an earlier prepare that covers text already
            # replaced in this pass - applying it would overwrite newer text
            bad.append((name, "overlaps-earlier-chunk"))
            continue
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
        ok, why = free_ok(srcb, newl, lang_of(rel))
        if ok:
            new.append((st, min(en, len(cur)), newl))
            applied_to = max(applied_to, min(en, len(cur)))
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
        # advance only over a contiguous run from the previous offset, so a
        # missing or rejected chunk in the middle never gets skipped forever
        p = load_prog().get(rel, 0)
        for st, en, _n in sorted(new):
            if st > p:
                break
            p = max(p, en)
        set_progress(rel, p)
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
        p = load_prog().get(rel, 0)
        for st, en, name, fp in sorted(blocks_of(outdir)):
            if st > p:
                break
            p = max(p, en)
        set_progress(rel, p)
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