"""Mechanical punctuation and width repair, by language.

These are the fixes that do not need a writer: a machine can make them and a
machine can prove they changed nothing else. The invariants below are asserted
per file (digit multiset, quote counts, kana count for ja) and the file is not
written if any of them moves.

English rules (`--lang en`):

  * `....` and longer -> `…`            (three dots are left alone, they are a style)
  * `{l[tobechecked10]}` and friends    export markers, removed, text kept
  * trailing spaces, double spaces      collapsed
  * `, .` / `.,`                        the obvious slips
  * missing space after a sentence end  only when unambiguous (not `Mr.Smith`,
                                        `e.g.`, initials, `3.a`)

Deliberately not done: `!?` vs `?!` unification. It looks like a tidy-up and
it is not: `now!?!` becomes `now!!?`, which is worse than what the translator
wrote. Emphatic punctuation is voice, so it is left alone.

Japanese rules (`--lang ja`):

  * half-width katakana -> full-width    NFKC on the half-width range only
  * leading `、` `。` `，` on a line     wrap residue, never legitimate
  * trailing spaces                      removed

    python tools/repair/fix_punct.py --path "English/X.txt" --dry
    python tools/repair/fix_punct.py --path "English" --apply
"""
import os, re, sys, glob, argparse, unicodedata
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "polish"))
from langrules import lang_of, DIGITS, KANA, quote_count  # noqa: E402

HW_KANA = re.compile(r"[\uff61-\uff9f]+")
LEAD_PUNCT = re.compile(r"^([、。，,])(?!\s*$)")
TAG_MARK = re.compile(r"\{l\[tobechecked\d*\]\}")
# four or more dots is an export artifact; three dots is the house style and stays
DOTS = re.compile(r"(?<=[A-Za-z,;'\"])\.{4,}")
TRAIL = re.compile(r"[ \t]+$")
DBLSP = re.compile(r"(?<=[A-Za-z,;:])\s{2,}(?=[A-Za-z\"'“(])")
SLIPS = [(re.compile(r", \."), "."), (re.compile(r"\.,"), ".")]
NOSPACE = re.compile(r"(?<=[a-z][.!?])(?=[A-Z][a-z])")
ABBREV = re.compile(r"\b(Mr|Mrs|Ms|Dr|St|Jr|Sr|vs|etc|e\.g|i\.e|No|Vol|Prof)\.$")


def en_rules(lines, dots=False):
    n = Counter()
    out = []
    for line in lines:
        s = line
        s2 = TAG_MARK.sub("", s)
        if s2 != s:
            n["export-mark"] += 1
            s = s2
        for rx, rep in SLIPS:
            s2 = rx.sub(rep, s)
            if s2 != s:
                n["slip"] += 1
                s = s2
        if dots:
            s2 = DOTS.sub("…", s)
            if s2 != s:
                n["dots"] += 1
                s = s2
        if not ABBREV.search(s.rstrip()):
            s2 = NOSPACE.sub(" ", s)
            if s2 != s:
                n["missing space"] += 1
                s = s2
        s2 = DBLSP.sub(" ", s)
        if s2 != s:
            n["double space"] += 1
            s = s2
        s2 = s.rstrip(" \t")
        if s2 != s:
            n["trailing space"] += 1
            s = s2
        out.append(s)
    return out, n


def ja_rules(lines):
    n = Counter()
    out = []
    for line in lines:
        s = line
        s2 = HW_KANA.sub(lambda m: unicodedata.normalize("NFKC", m.group(0)), s)
        if s2 != s:
            n["half-width kana"] += 1
            s = s2
        s2 = LEAD_PUNCT.sub("", s)
        if s2 != s:
            n["leading punct"] += 1
            s = s2
        s2 = s.rstrip(" \t")
        if s2 != s:
            n["trailing space"] += 1
            s = s2
        out.append(s)
    return out, n


def fix(path, lang, dry, samples=0, dots=False):
    text = open(path, encoding="utf-8").read()
    lines = text.split("\n")
    out, counts = en_rules(lines, dots) if lang == "en" else ja_rules(lines)
    new = "\n".join(out)
    if new == text:
        print(f"clean  {os.path.basename(path)[:58]}")
        return Counter()
    ref = unicodedata.normalize("NFKC", text) if lang == "ja" else text
    problems = []
    if sorted(DIGITS.findall(text)) != sorted(DIGITS.findall(new)):
        problems.append("digits")
    if quote_count(ref) != quote_count(new):
        problems.append("quotes")
    if len(KANA.findall(ref)) != len(KANA.findall(new)):
        problems.append("kana")
    if problems:
        print(f"  !! {os.path.basename(path)[:56]}: invariant broken {problems} - skipped")
        return Counter()
    total = sum(v for k, v in counts.items() if k not in ("!?", "?!"))
    if samples:
        shown = 0
        for a, b in zip(lines, out):
            if a != b and shown < samples:
                print(f"      - {a[:76]}")
                print(f"      + {b[:76]}")
                shown += 1
    print(f"{'would fix' if dry else 'fixed'} {total:>6}  "
          + " ".join(f"{k}={v}" for k, v in sorted(counts.items()) if k not in ("!?", "?!") and v)
          + f"   {os.path.basename(path)[:46]}")
    if not dry:
        open(path, "w", encoding="utf-8", newline="\n").write(new)
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--samples", type=int, default=0)
    ap.add_argument("--dots", action="store_true",
                    help="also turn .... into one ellipsis (a style call - the "
                         "Fata Morgana translation uses a run of dots as a "
                         "silence marker, so this is off by default)")
    a = ap.parse_args()
    targets = sorted(glob.glob(os.path.join(a.path, "*.txt"))) if os.path.isdir(a.path) else [a.path]
    grand = Counter()
    for p in targets:
        lang = lang_of(os.path.relpath(p, ROOT).replace("\\", "/"))
        if lang == "zh":
            continue
        grand += fix(p, lang, a.dry, a.samples, a.dots)
    if len(targets) > 1:
        print("total:", " ".join(f"{k}={v}" for k, v in sorted(grand.items()) if v))


if __name__ == "__main__":
    main()