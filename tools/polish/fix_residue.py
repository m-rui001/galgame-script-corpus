"""Repair residual engine/glyph characters left in Chinese script text.

Extraction from Shift-JIS era engines often keeps half-width katakana marks in
place of Chinese punctuation:

    '・'*n      Japanese ellipsis glyph (…/……)
    'ﾟ'        half-width semi-voiced mark, used as '？'
    'ﾞ'        half-width voiced mark, used as '！'
    'ｰ'        half-width long vowel, used as '—'
    'ﾊﾉ'       kept verbatim (license-plate katakana)

Only the characters below are touched. No wording is changed.

    python tools/polish/fix_residue.py            # dry run, prints counts
    python tools/polish/fix_residue.py --apply    # write files
    python tools/polish/fix_residue.py --apply --only ひぐらし
"""
import os, re, sys, csv, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "RESIDUE_FIXED.csv")
KEEP_KANA = {"ﾊ", "ﾉ"}  # 车牌等处的半角片假名
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CJK = re.compile(r"[\u4e00-\u9fff]")
KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30fa\u30fc-\u30ff]")  # 不含 U+30FB「・」


CORRUPT_QUOTES = {"乽": "「", "乿": "」"}


def fix_line(line):
    """Return (new_line, replacements). Deterministic, idempotent.

    行首的人物名前缀（`名字：`）原样保留，所有改动只发生在正文部分。
    """
    quoted = 0
    if any(c in line for c in CORRUPT_QUOTES):
        for k, v in CORRUPT_QUOTES.items():
            quoted += line.count(k)
            line = line.replace(k, v)
    if not (any(c in line for c in "・ﾟﾞｰ")
            or CTRL.search(line)
            or re.search(r"·{2,}", line)
            or re.search(r"[一-鿿][.．](?=[一-鿿」』]|$)", line)):
        return line, quoted
    # 假名较多的行是日文（或假名夹用的专名／标识符），整行不动
    kana = len(KANA.findall(line))
    if kana and kana / max(1, len(line)) > 0.08:
        return line, 0

    m = re.match(r"^[^：:]{0,10}[：:]", line)
    cut = m.end() if m else 0
    pre, s = line[:cut], line[cut:]
    n = 0

    # 问号感叹号连写：ﾟﾞ / ﾞﾟ -> ？！
    new = re.sub(r"[ﾟﾞ]{2,}", "？！", s)
    if new != s:
        n += 1
        s = new
    if "ﾟ" in s:
        n += s.count("ﾟ")
        s = s.replace("ﾟ", "？")
    if "ﾞ" in s:
        s = re.sub(r"([。？！…])\s*[ﾞ]+", r"\1", s)   # 已有句末标点时不补叹号
        n += s.count("ﾞ")
        s = s.replace("ﾞ", "！")
    if "ｰ" in s:
        n += s.count("ｰ")
        s = s.replace("ｰ", "—")

    # 中点：连写（≥2）→ ……；单点在句首、引号括号后、或紧贴标点时算省略号
    def dots(mm):
        if len(mm.group(0)) >= 2:
            return "……"
        i = mm.start()
        prev = s[i - 1] if i else ""
        nxt = s[i + 1] if i + 1 < len(s) else ""
        left_ok = prev == "" or prev in "「（(【[，。？！、…：;‘“ "
        right_ok = nxt == "" or nxt in "」）)】]，。？！、…：;’” "
        return "…" if (left_ok or right_ok) else "・"
    new = re.sub(r"・+", dots, s)
    if new != s:
        n += 1
        s = new

    # 引号内的短专名（『光之勇者・传说正义』一类）不改
    guarded = set()
    for qm in re.finditer(r"[「『]([^「」『』]{0,12})[」』]", s):
        if len(CJK.findall(qm.group(1))) <= 8 and not re.search(r"[，。？！、…]", qm.group(1)):
            guarded.update(range(qm.start(1), qm.end(1)))
    char_s = list(s)
    # 行内剩下的单点：正文够长、两侧非假名时当读点；同一字叠写用「、」
    if "・" in s and len(CJK.findall(s)) >= 6:
        chars = list(s)
        for i in range(len(chars)):
            if chars[i] != "・":
                continue
            l = chars[i - 1] if i else ""
            r = chars[i + 1] if i + 1 < len(chars) else ""
            if i in guarded:
                continue
            if ("぀" <= l <= "ヿ") or ("぀" <= r <= "ヿ"):
                continue
            chars[i] = "、" if l == r else "，"
            n += 1
        s = "".join(chars)

    # 控制字节：多为提取时的句读标记，按句末处理
    if CTRL.search(s):
        def ctrl(mm):
            i = mm.start()
            prev = s[i - 1] if i else ""
            nxt = s[i + 1] if i + 1 < len(s) else ""
            if prev and prev in "。！？…—，、":
                return ""
            if nxt and (nxt in "」』，。？！…" or "一" <= nxt <= "鿿"):
                return "。"
            return ""
        n += len(CTRL.findall(s))
        s = CTRL.sub(ctrl, s)

    # 「···」是省略号的另一种残留
    def middots(mm):
        return "……" if len(mm.group(0)) >= 2 else "·"
    new = re.sub(r"·+", middots, s)
    if new != s:
        n += 1
        s = new

    # 汉字之间的半角／全角句点当作句号（数字与文件名不动）
    s2 = re.sub(r"([一-鿿])[.．](?=[一-鿿])", r"\1。", s)
    s2 = re.sub(r"([一-鿿])[.．](?=[」』]|$)", r"\1。", s2)
    if s2 != s:
        n += 1
        s = s2

    # 标点收敛
    s = re.sub(r"[，、]{2,}", "，", s)
    s = re.sub(r"(…){3,}", "……", s)
    s = re.sub(r"—{3,}", "——", s)
    s = re.sub(r"([。！？])…+", r"\1", s)          # 「。……」冗余
    s = re.sub(r"(…+)。", r"\1", s)                # 「……」后不接句号
    s = re.sub(r"~+", "～", s)
    s = re.sub(r"～{2,}", "～", s)
    s = re.sub(r"，\s*([。！？])", r"\1", s)        # 「，。」->「。」
    s = re.sub(r"？\s*？", "？", s)
    s = re.sub(r"！\s*！", "！", s)
    s = re.sub(r"([！？])。", r"\1", s)
    return pre + s, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default=None)
    a = ap.parse_args()

    rows, total = [], 0
    for r, _, fs in os.walk(os.path.join(ROOT, "Zh")):
        for f in sorted(fs):
            if not f.endswith(".txt"):
                continue
            if "中日对照" in f:
                continue
            if a.only and a.only not in f:
                continue
            p = os.path.join(r, f)
            rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
            s = open(p, encoding="utf-8", errors="replace").read()
            if not any(c in s for c in "・ﾟﾞｰ"):
                continue
            lines = s.split("\n")
            hits = 0
            for i, l in enumerate(lines):
                nl, k = fix_line(l)
                if k:
                    lines[i] = nl
                    hits += k
            if hits:
                total += hits
                rows.append({"path": rel, "replacements": hits})
                if a.apply:
                    open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
                print(f"{'write' if a.apply else 'would'} {rel}: {hits}")
    if a.apply and rows:
        with open(LOG, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["path", "replacements"], lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    print(f"{'applied' if a.apply else 'dry-run'}: {len(rows)} files, {total} replacements")


if __name__ == "__main__":
    main()