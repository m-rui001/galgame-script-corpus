"""Corpus-wide, rule-level translationese reduction.

High-precision only: each rule either removes a redundant function word or swaps
one fixed pattern for its Chinese equivalent. No sentence is restructured here —
that is the LLM pass's job (polish_corpus.py). Line count, speaker prefixes,
quotes and digits are never touched, so the change is reversible and auditable.

    python tools/polish/fix_translationese.py            # dry run, counts per rule
    python tools/polish/fix_translationese.py --apply
"""
import os, re, sys, csv, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "TRANSLATIONESE_FIXED.csv")

# 「小时候」「那时候」是词，不能缩成「小时」「那候」
DE_SKIP_BEFORE = "小那这此当同有儿什多啥一"

JINXING = ("调查|确认|检查|搜索|搜查|说明|报告|治疗|攻击|防御|准备|整理|分析|研究|讨论|核对|比较|"
           "判断|预测|实验|训练|记录|观察|询问|审问|交涉|谈判|交易|战斗|救助|搬运|修理|制造|建设|"
           "破坏|处理|打扫|联络|接触|实验|测定|拍摄|追踪|监视|回收|搬运|分发|补充|印刷|修理")
ZUOCHU = {"决定": "决定", "判断": "判断", "选择": "选择", "回答": "回答", "反应": "反应",
          "解释": "解释", "说明": "说明", "牺牲": "牺牲", "行动": "行动", "结论": "下结论",
          "让步": "让步", "指示": "指示", "评价": "评价", "主张": "主张"}

RULES = [
    ("de-shihou", re.compile(r"(?<=[\u4e00-\u9fff])的时候(?=[，。！？、…」』\s])"),
     lambda m: "时"),
    ("duiyu-laishuo", re.compile(r"对于([^，。！？]{1,12})来说"), lambda m: "对%s来说" % m.group(1)),
    ("ruguo-dehua", re.compile(r"(如果|要是|若是|假如|万一)([^，。！？]{1,30})的话"),
     lambda m: m.group(1) + m.group(2)),
    ("jinxing", re.compile(r"进行(%s)(?![：:、])" % JINXING), lambda m: m.group(1)),
    ("zuochu", re.compile(r"(做出|作出)了?(%s)(?![：:、])" % "|".join(ZUOCHU)), None),  # 见 zuochu_repl
]


def zuochu_repl(m):
    base = ZUOCHU[m.group(2)]
    if "了" in m.group(0):
        return "下了结论" if base == "下结论" else base + "了"
    return base


def fix_line(line, counts=None):
    if "的时候" not in line and "对于" not in line and "的话" not in line \
            and "进行" not in line and "做出" not in line and "作出" not in line:
        return line
    s = line
    # 「…的时候」：前一字是词缀时跳过
    m = re.search(r"(.)的时候(?=[，。！？、…」』\s])", s)
    if m and m.group(1) not in DE_SKIP_BEFORE:
        s2 = re.sub(r"(?<=[\u4e00-\u9fff])的时候(?=[，。！？、…」』\s])", "时", s)
        if counts is not None:
            counts["de-shihou"] += len(re.findall(r"的时候(?=[，。！？、…」』\s])", s))
        s = s2
    for name, rx, fn in RULES[1:]:
        fn = zuochu_repl if fn is None else fn
        s2 = rx.sub(fn, s)
        if s2 != s:
            if counts is not None:
                counts[name] += len(rx.findall(s))
            s = s2
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    totals = {}
    rows = []
    for r, _, fs in os.walk(os.path.join(ROOT, "Zh")):
        for f in sorted(fs):
            if not f.endswith(".txt") or "中日对照" in f:
                continue
            if a.only and a.only not in f:
                continue
            p = os.path.join(r, f)
            lines = open(p, encoding="utf-8", errors="replace").read().split("\n")
            counts = dict.fromkeys([n for n, _, _ in RULES], 0)
            n = 0
            for i, l in enumerate(lines):
                nl = fix_line(l, counts)
                if nl != l:
                    lines[i] = nl
                    n += 1
            if n:
                rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
                rows.append({"path": rel, "lines": n, **counts})
                for k, v in counts.items():
                    totals[k] = totals.get(k, 0) + v
                if a.apply:
                    open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    if a.apply and rows:
        with open(LOG, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["path", "lines"] + [n for n, _, _ in RULES],
                               lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    print(f"{'applied' if a.apply else 'dry-run'}: {len(rows)} files, "
          f"{sum(r['lines'] for r in rows)} lines, {sum(totals.values())} edits")
    for k, v in sorted(totals.items(), key=lambda kv: -kv[1]):
        print(f"  {k:14s} {v}")


if __name__ == "__main__":
    main()