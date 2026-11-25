"""Classify every file by language mix and by the kind of repair it needs.

The corpus is ZH / EN / JA, and each needs a different kind of work:

* ZH - free rewrite (docs/STYLE_ZH.md): the translationese is the problem.
* EN - repair plus gentle prose polish (docs/STYLE_EN.md): most of these are
  published localisations, so the mandate is to fix what the export broke and
  to smooth the machine-generated ones, not to re-author them.
* JA - repair only (docs/STYLE_JA.md): these are the originals the ZH
  translations were made from. Rewriting them would destroy their role as the
  reference text.

What this prints per file:

    kana, cjk, latin      raw counts
    ja_ratio              kana / (kana + cjk), the cheap language signal
    mixed                 lines that look like the other language than the file
    wrapped               lines that look like a fixed-width wrap break
    kana_in_en            (EN only) lines with kana - untranslated source
    tagload               engine/HTML markup density

    python tools/lang_scan.py            # summary table
    python tools/lang_scan.py --csv out.csv
"""
import os, re, sys, csv, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")
CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN = re.compile(r"[A-Za-z]")
TAG = re.compile(r"\{[^{}\n]{1,24}\}|<[a-zA-Z/][^<>\n]{0,24}>|\[[a-zA-Z]{2,}[^\]\n]{0,16}\]")
# Simplified-only characters: Japanese writes these with a different form
# (説 時 過 対 様 認 東 麗 変 戦 問 見 現 実 …), so a line containing them and no
# kana is Chinese. Particles like 的/了/那 do NOT work as a signal - 旦那様,
# 没落 and 了解 are ordinary Japanese and the particle test flags them.
SIMP = re.compile(r"[这们说时过对么让还样种觉认识该东丽举义乐习乡书买亚产亲亿仅从众优伟传伤价铁边变战听问间关开长门见现实头]")
TERM = re.compile(r"[。！？…‥」』）)】!?\.\"'~～ー―—]$")
SPK = re.compile(r"^[^\s：:（(「『]{1,8}[：:]")


def classify(p):
    t = open(p, encoding="utf-8", errors="replace").read()
    lines = t.split("\n")
    kana = len(KANA.findall(t))
    cjk = len(CJK.findall(t))
    latin = len(LATIN.findall(t))
    ja_ratio = kana / max(1, kana + cjk)

    wrapped = 0
    for a, b in zip(lines, lines[1:]):
        if not a.strip() or not b.strip():
            continue
        # a line that ends mid-clause, followed by a line that starts without a
        # speaker tag and without a quote, is a wrap break
        if not TERM.search(a.rstrip()) and not SPK.match(b) and not b.lstrip()[:1] in "「『“\"":
            wrapped += 1

    kana_in_en = sum(1 for l in lines if KANA.search(l)) if "English/" in p.replace("\\", "/") else 0
    pp = p.replace("\\", "/")
    zh_in_ja = (sum(1 for l in lines if SIMP.search(l) and not KANA.search(l))
                if ("/JA/" in pp or "/Bilingual/" in pp) else 0)
    return dict(path=p.replace("\\", "/"), lines=len(lines), kana=kana, cjk=cjk, latin=latin,
                ja_ratio=round(ja_ratio, 3), wrapped=wrapped,
                wrapped_ratio=round(wrapped / max(1, len(lines)), 3),
                kana_in_en=kana_in_en, zh_in_ja=zh_in_ja,
                tagload=len(TAG.findall(t)))


def main():
    out = None
    if "--csv" in sys.argv:
        out = sys.argv[sys.argv.index("--csv") + 1]
    rows = []
    for d in ("Zh", "English", "JA", "Bilingual"):
        for p in sorted(glob.glob(os.path.join(ROOT, d, "*.txt"))):
            rows.append(classify(p))
    if out:
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"{len(rows)} rows -> {out}")
        return
    bands = (("EN", "English", "kana_in_en"),
             ("JA", "JA", "zh_in_ja"),
             ("BI", "Bilingual", "zh_in_ja"))
    for lang, d, key in bands:
        sel = [r for r in rows if r["path"].replace("\\", "/").find("/%s/" % d) >= 0]
        if not sel:
            continue
        print("\n== %s: lines in the other language (%s) ==" % (lang, key))
        for r in sorted(sel, key=lambda r: -r[key])[:12]:
            if r[key]:
                print(f"{r[key]:>6}/{r['lines']:<7} {os.path.basename(r['path'])[:62]}")
        print("== %s: wrapped-line share ==" % lang)
        for r in sorted(sel, key=lambda r: -r["wrapped_ratio"])[:8]:
            if r["wrapped_ratio"] >= 0.05:
                print(f"{r['wrapped_ratio']:>6.1%} {r['wrapped']:>6} {os.path.basename(r['path'])[:62]}")


if __name__ == "__main__":
    main()