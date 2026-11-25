"""Per-language gates for the polish pipeline.

The ZH gates assume Chinese prose being rewritten from a Japanese original:
no kana may appear, digits must be identical, 「」 counts must match, and a
line is only rewritable when it has three or more hanzi.

That is wrong for the other two corpora:

* `en` - English text. Nothing here is a rewrite of the author's prose: these
  are published or machine localisations, so the gates only demand that the
  line count, the digits, the quote counts and the dialogue tags survive, and
  that the volume stays within 0.6-1.4x. Adding kana or CJK is a failure;
  removing it (that is, translating a line the export left in Japanese) is the
  whole point and must not be blocked.
* `ja` - Japanese originals. Polishing is allowed here (the owner's call: a
  script can be improved in Japanese as well as in Chinese), but the translation
  pipeline depends on these files staying comparable to their ZH counterparts,
  so the gate demands that digits, quote counts and the amount of kana survive.
* `bi` - Bilingual JA/ZH files: the original and its translation sitting in the
  same file, line by line. Both halves may be polished; the gate additionally
  forbids losing kana, because a line that loses its Japanese has been replaced
  by a translation rather than polished.
"""
import re

KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")
CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN = re.compile(r"[A-Za-z]")
WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
DIGITS = re.compile(r"[0-9０-９]+")
QUOTES = "「」『』“”\"‘’"
CONTENT = re.compile(r"[^\u4e00-\u9fff0-9０-９A-Za-zＡ-Ｚａ-ｚ]")

VOLUME = {"zh": (0.60, 1.40), "en": (0.60, 1.40), "ja": (0.60, 1.40),
          "bi": (0.60, 1.40)}
# On a six-character line a ratio gate is noise, not protection: adding three
# words is 1.5x and perfectly reasonable. Short lines are judged by an absolute
# allowance instead.
SHORT = 12
SHORT_SLACK = 8


def _volume_ok(va, vb, lang):
    lo, hi = VOLUME[lang]
    if va and lo <= vb / max(1, va) <= hi:
        return True
    return va <= SHORT and abs(vb - va) <= SHORT_SLACK


def lang_of(path):
    p = path.replace("\\", "/")
    if p.startswith("English/") or "/English/" in p:
        return "en"
    if p.startswith("Bilingual/") or "/Bilingual/" in p:
        return "bi"
    if p.startswith("JA/") or "/JA/" in p:
        return "ja"
    return "zh"


def polishable(line, lang="zh"):
    s = line.strip()
    if lang == "en":
        return len(WORD.findall(s)) >= 4
    if lang in ("ja", "bi"):
        return len(s) >= 6 and bool(KANA.search(s) or CJK.search(s))
    return len(s) >= 8 and not KANA.search(s) and len(CJK.findall(s)) >= 3


def volume(t, lang="zh"):
    if lang == "en":
        return len(WORD.findall(t))
    if lang in ("ja", "bi"):
        return len(KANA.findall(t)) + len(CJK.findall(t))
    return len(CONTENT.sub("", t))


def quote_count(t):
    return sum(t.count(q) for q in QUOTES)


def check(src, out, lang="zh", spk=None):
    """Single line gate. `spk` is (speaker_regex, ) style; caller passes its own."""
    a, b = src.strip(), out.strip()
    if not b:
        return False, "empty"
    if lang in ("zh", "en") and len(KANA.findall(b)) > len(KANA.findall(a)):
        return False, "kana"
    if lang == "en" and len(CJK.findall(b)) > len(CJK.findall(a)) + 2:
        return False, "cjk"
    if lang in ("ja", "bi") and len(KANA.findall(b)) < len(KANA.findall(a)):
        return False, "kana lost"
    if sorted(DIGITS.findall(a)) != sorted(DIGITS.findall(b)):
        return False, "digits"
    if quote_count(a) != quote_count(b):
        return False, "quotes"
    va, vb = volume(a, lang), volume(b, lang)
    if not _volume_ok(va, vb, lang):
        return False, f"volume {va}->{vb}"
    return True, ""


QUOTE_ONLY = re.compile(r"[「」『』（）()]")


def block_ok(src_block, out_block, lang="zh"):
    """Whole-section gate used by the free-merge path."""
    src = "\n".join(src_block)
    out = "\n".join(out_block)
    if not out.strip():
        return False, "empty"
    if lang in ("ja", "bi"):
        # A repair that adds only bracket marks is the whole point of the ja
        # pass: Salthe arrives with 1,456 unmatched 「 because the exporter ate
        # them. Accept it when the text is byte-identical once the brackets are
        # lifted, demanding only that the bracket balance does not get worse.
        if QUOTE_ONLY.sub("", src) == QUOTE_ONLY.sub("", out):
            sb = abs(src.count("「") - src.count("」"))
            ob = abs(out.count("「") - out.count("」"))
            return (ob <= sb), ("brackets %d->%d" % (sb, ob) if ob > sb else "")
    if lang in ("zh", "en") and len(KANA.findall(out)) > len(KANA.findall(src)):
        return False, "kana"
    if lang == "en" and len(CJK.findall(out)) > len(CJK.findall(src)) + 2:
        return False, "cjk"
    if sorted(DIGITS.findall(src)) != sorted(DIGITS.findall(out)):
        return False, "digits"
    if quote_count(src) != quote_count(out):
        return False, "quotes"
    va, vb = volume(src, lang), volume(out, lang)
    if not _volume_ok(va, vb, lang):
        return False, f"volume {va}->{vb}"
    return True, ""