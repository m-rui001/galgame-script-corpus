"""Rejoin lines the exporter broke at a fixed display width.

Scripts are exported by walking text boxes, so a sentence that wraps on screen
arrives as two or three lines:

    花音「はぁ……私なんて、こんなにおヒゲがモジャモジャでも、
    すぐに宮原くんだったらわかったのになぁ」

Joining is safe when the previous line has no terminal punctuation and the next
line is not a new speaker turn and does not open a quote. Everything else is
left alone, so a miss costs nothing while a wrong join would corrupt text.

Invariants asserted per file: digit multiset unchanged, quote counts unchanged,
kana/kanji volume unchanged (whitespace for English only).

    python tools/repair/fix_wrap.py --path "JA/Ouchi ni Kaeru made.txt" --dry
    python tools/repair/fix_wrap.py --path "JA" --glob "*.txt" --apply
"""
import os, re, sys, glob, argparse, statistics

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "polish"))
from langrules import lang_of, DIGITS, quote_count, KANA, CJK  # noqa: E402

# ─ ── ; ； and any tag/markup ending also mark a deliberate break
TERM = re.compile(r"[。！？…‥」』）)】!?\.\"'~～ー―—─;；:：\]\}]$")
CODE = re.compile(r"^(if\(|for\(|function|var |const |let |console\.|\{|</?[a-z]+>)")
OPENQ = re.compile(r"^[\s　]*[「『“‘\"]")
SPK = re.compile(r"^[\s　]*[^\s：:（(「『]{1,8}[：:]")
SPK_JA = re.compile(r"^[\s　]*[^\s「『（(]{1,10}(「|『)")
ZHW = re.compile(r"[的了这那们吗呢很没吧啊]")
SPK_EN = re.compile(r"^[\s]*[A-Z][A-Za-z0-9 .'\-]{0,24}:\s")
SKIP = re.compile(r"^(=====|#|\s*$|\{)")
JOINERS = {"zh": "", "ja": "", "en": " "}


def is_turn_start(line, lang):
    if OPENQ.match(line):
        return True
    if lang == "en":
        return bool(SPK_EN.match(line))
    if lang == "ja":
        return bool(SPK_JA.match(line) or SPK.match(line))
    return bool(SPK.match(line))


def joinable(prev, nxt, lang):
    if SKIP.match(prev) or SKIP.match(nxt):
        return False
    p = prev.rstrip()
    if not p or TERM.search(p):
        return False
    # a line that is only markup or only punctuation is not prose
    if len(re.sub(r"[\s　]", "", p)) < 2:
        return False
    if CODE.match(p) or CODE.match(nxt.lstrip()):
        return False
    if is_turn_start(nxt, lang):
        return False
    if lang == "en":
        # a wrapped English line continues in lower case; anything that starts
        # with a capital, a quote or a dash is a new sentence and stays as is
        if not re.match(r"[\s]*[a-z0-9(,;—]", nxt):
            return False
    if lang == "ja":
        # never glue a kana line to a line that is pure hanzi: that is the
        # join that mixes a Japanese sentence into a Chinese one
        if bool(KANA.search(p)) != bool(KANA.search(nxt)):
            return False
    return True


def wrap_width(lines, lang):
    """Estimate the export column width, or 0 when this is not a wrapped file.

    A display-width wrap leaves a tight cluster of line lengths at the column
    boundary. Verse that is deliberately one clause per line (Minikui Mojika)
    does not: its candidate lines are short and their lengths scatter. Requiring
    a median of at least 18 characters, then only joining lines within six
    characters of that median, keeps the second kind out entirely.
    """
    lens = [len(a.rstrip()) for a, b in zip(lines, lines[1:]) if joinable(a, b, lang)]
    if len(lens) < 8:
        return 0, len(lens), 0.0
    med = statistics.median(lens)
    sd = statistics.pstdev(lens)
    # a tight cluster means a display wrap; a wide spread means the author or
    # the exporter broke lines for other reasons and we must not touch them
    return (med if med >= 18 and sd <= 12 else 0), len(lens), sd


def fix(path, dry=False, verbose=0):
    lang = lang_of(os.path.relpath(path, ROOT).replace("\\", "/"))
    text = open(path, encoding="utf-8").read()
    lines = text.split("\n")
    # mixed Japanese/Chinese files need a classification decision, not repair
    zh_lines = sum(1 for l in lines if CJK.search(l) and not KANA.search(l)
                   and ZHW.search(l))
    if lang == "ja" and zh_lines > len(lines) * 0.05:
        print(f"skip  {os.path.basename(path)[:56]} - mixed JA/ZH "
              f"({zh_lines}/{len(lines)} chinese-looking lines)")
        return 0
    width, cand, sd = wrap_width(lines, lang)
    if not width:
        print(f"skip  {os.path.basename(path)[:56]} - not wrapped "
              f"({cand} candidates, median too short)")
        return 0
    out, joined, samples = [], 0, []
    for line in lines:
        if out and len(out[-1].rstrip()) >= width - 6 and joinable(out[-1], line, lang):
            j = JOINERS[lang]
            new = out[-1].rstrip() + j + line.lstrip(" \u3000")
            if verbose and joined < verbose:
                samples.append((out[-1].rstrip(), line.lstrip(" \u3000"), new))
            out[-1] = new
            joined += 1
        else:
            out.append(line)
    newtext = "\n".join(out)

    # invariants: a rejoin must not change any character, only line breaks
    problems = []
    if sorted(DIGITS.findall(text)) != sorted(DIGITS.findall(newtext)):
        problems.append("digits")
    if quote_count(text) != quote_count(newtext):
        problems.append("quotes")
    if lang != "en":
        if len(KANA.findall(text)) != len(KANA.findall(newtext)):
            problems.append("kana")
        if len(CJK.findall(text)) != len(CJK.findall(newtext)):
            problems.append("cjk")
    if problems:
        print(f"  !! {os.path.basename(path)}: invariant broken {problems} - not written")
        return 0

    print(f"{'would join' if dry else 'joined'} {joined:>6}  lines {len(lines)} -> {len(out)}  "
          f"w~{width:.0f} sd={sd:.1f}  {os.path.basename(path)[:50]}")
    for a, b, c in samples:
        print(f"      - {a[-38:]}")
        print(f"      + {c[:52]}")
    if not dry and joined:
        open(path, "w", encoding="utf-8", newline="\n").write(newtext)
    return joined


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--samples", type=int, default=0)
    a = ap.parse_args()
    p = a.path
    if os.path.isdir(p):
        tot = 0
        for f in sorted(glob.glob(os.path.join(p, "*.txt"))):
            tot += fix(f, a.dry, a.samples)
        print(f"total joins: {tot}")
    else:
        fix(p, a.dry, a.samples)


if __name__ == "__main__":
    main()