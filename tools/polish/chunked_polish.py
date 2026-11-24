"""Split a script into chunk files for parallel polishing, then merge them back.

Sub-agents read one chunk file each and write a polished copy with the same
number of lines. `merge` re-checks every line against the original (speaker
prefix, quotes, digits, kana, content length) and keeps the original wherever a
line fails, so a bad chunk can never damage the corpus.

    python tools/polish/chunked_polish.py prepare --path "Zh/x.txt" --start 19000 --end 23000 --size 250
    python tools/polish/chunked_polish.py merge   --path "Zh/x.txt"
    python tools/polish/chunked_polish.py report  --path "Zh/x.txt"
"""
import os, re, sys, json, shutil, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jpkanji import to_sc

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORK = os.path.join(ROOT, "..", "_audit", "polish_chunks")
CJK = re.compile(r"[\u4e00-\u9fff]")
KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30fa\u30fc-\u30ff]")
SPEAKER = re.compile(r"^([^\s：:（(「『]{1,6})[：:]")
DIGITS = re.compile(r"[0-9０-９]+")
CONTENT = re.compile(r"[^\u4e00-\u9fff0-9０-９A-Za-zＡ-Ｚａ-ｚ]")


def slug(rel):
    return re.sub(r"[\\/:*?\"<>| ]+", "_", rel)[:80]


def prepare(rel, start, end, size):
    path = os.path.join(ROOT, rel)
    lines = open(path, encoding="utf-8").read().split("\n")
    end = min(end, len(lines))
    d = os.path.join(WORK, slug(rel))
    out = os.path.join(d, "out")
    os.makedirs(out, exist_ok=True)
    meta = {"path": rel, "start": start, "end": end, "size": size, "chunks": []}
    k = 0
    for a in range(start, end, size):
        b = min(a + size, end)
        k += 1
        name = f"{k:03d}_{a}-{b}.txt"
        open(os.path.join(d, name), "w", encoding="utf-8", newline="\n").write("\n".join(lines[a:b]))
        meta["chunks"].append({"file": name, "start": a, "end": b})
    json.dump(meta, open(os.path.join(d, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(meta['chunks'])} chunks of <= {size} lines -> {d}")
    for c in meta["chunks"]:
        print("  ", c["file"])


def polishable(line):
    s = line.strip()
    return len(s) >= 8 and not KANA.search(s) and len(CJK.findall(s)) >= 3


def norm_quotes(t):
    return t.replace("乽", "「").replace("乿", "」")


def check(src, out):
    a, b = src.strip(), out.strip()
    if not b:
        return False, "empty"
    if len(KANA.findall(b)) > len(KANA.findall(a)):
        return False, "kana"
    sa, sb = SPEAKER.match(to_sc(a)), SPEAKER.match(to_sc(b))
    if bool(sa) != bool(sb) or (sa and sa.group(1) != sb.group(1)):
        return False, "speaker"
    if norm_quotes(a).count("「") + norm_quotes(a).count("『") != norm_quotes(b).count("「") + norm_quotes(b).count("『"):
        return False, "quotes"
    if sorted(DIGITS.findall(a)) != sorted(DIGITS.findall(b)):
        return False, "digits"
    cx, cy = len(CONTENT.sub("", to_sc(a))), len(CONTENT.sub("", to_sc(b)))
    if cy > 1.5 * max(1, cx) or cy < 0.40 * cx:
        return False, f"length:{cx}->{cy}"
    return True, ""


def merge(rel, dry=False):
    d = os.path.join(WORK, slug(rel))
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    path = os.path.join(ROOT, rel)
    lines = open(path, encoding="utf-8").read().split("\n")
    applied = kept = 0
    bad = []
    for c in meta["chunks"]:
        outf = os.path.join(d, "out", c["file"])
        if not os.path.exists(outf):
            bad.append((c["file"], "missing"))
            continue
        got = open(outf, encoding="utf-8").read().split("\n")
        src = lines[c["start"]:c["end"]]
        if len(got) == len(src) + 1 and got[-1] == "":
            got = got[:-1]
        if len(got) != len(src):
            bad.append((c["file"], f"lines {len(src)}->{len(got)}"))
            continue
        for off, (x, y) in enumerate(zip(src, got)):
            if x.strip() == "" or not polishable(x):
                kept += 1
                continue
            ok, why = check(x, y)
            if ok:
                lead = x[:len(x) - len(x.lstrip())]
                trail = x[len(x.rstrip()):]
                lines[c["start"] + off] = lead + y.strip() + trail
                applied += 1
            else:
                kept += 1
                bad.append((f"{c['file']}@{c['start'] + off + 1}", why))
    if not dry:
        open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print(f"{'would merge' if dry else 'merged'}: {applied} lines rewritten, {kept} kept, {len(bad)} problems")
    for b in bad[:15]:
        print("  ", b)


def report(rel):
    d = os.path.join(WORK, slug(rel))
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    done = [c["file"] for c in meta["chunks"] if os.path.exists(os.path.join(d, "out", c["file"]))]
    print(f"{len(done)}/{len(meta['chunks'])} chunks back")
    for c in meta["chunks"]:
        mark = "ok " if c["file"] in done else "-- "
        print(mark, c["file"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "merge", "report"])
    ap.add_argument("--path", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=10 ** 9)
    ap.add_argument("--size", type=int, default=250)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.cmd == "prepare":
        prepare(a.path, a.start, a.end, a.size)
    elif a.cmd == "merge":
        merge(a.path, a.dry)
    else:
        report(a.path)


if __name__ == "__main__":
    main()