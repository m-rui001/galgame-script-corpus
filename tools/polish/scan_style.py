"""Rank Chinese scripts by translationese density, per 1000 body chars.

Deterministic, no model calls. Used to decide which works to polish first and to
show progress after a polish pass.

    python tools/polish/scan_style.py                 # all Zh files -> _audit/STYLE_SCAN.csv
    python tools/polish/scan_style.py --top 20
"""
import os, re, csv, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "..", "_audit", "STYLE_SCAN.csv")

CJK = re.compile(r"[\u4e00-\u9fff]")
KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30fa\u30fc-\u30ff]")

# (name, pattern, weight) -- weight is per-occurrence
MARKERS = [
    ("passive", r"被", 0.8),
    ("de-shihou", r"的时候", 1.2),
    ("de-hua", r"的话", 1.2),
    ("zuowei", r"作为", 1.0),
    ("yige", r"一个", 0.8),
    ("duiyu", r"对于|关于", 1.0),
    ("jinxing", r"进行|予以|做出|作出", 1.0),
    ("zhe-jian", r"这件事|这种事情|这种行为|这个事实|这种东西", 1.2),
    ("konsetsu", r"然后|于是|而且|但是|所以|因为|虽然", 0.6),
    ("sihu", r"似乎|好像|仿佛", 0.8),
    ("degree", r"非常|十分|相当|极其|真的|实在是", 0.7),
    ("kanai", r"呆然|一瞬|无念|残念|违和|微妙|大丈夫", 1.5),
    ("de-dede", r"[^，。！？」]{6,}的[^，。！？」]{4,}的", 1.0),
    ("subject-wo", r"^[我你他她][，]", 0.5),
    ("says", r"说着|看着|笑着|想着|走着", 0.4),
]

COMP = [(n, re.compile(p, re.M), w) for n, p, w in MARKERS]


def score_file(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    lines = [l for l in text.split("\n") if l.strip()]
    body = "\n".join(lines)
    chars = max(1, len(CJK.findall(body)))
    marks = {n: len(p.findall(body)) for n, p, _ in COMP}
    score = sum(marks[n] * w for n, _, w in COMP) * 1000.0 / chars
    kana = len(KANA.findall(body)) / max(1, len(body))
    return {
        "path": os.path.relpath(path, ROOT).replace(os.sep, "/"),
        "lines": len(lines), "chars": chars, "score": round(score, 2),
        "kana": round(kana, 4),
        **{k: v for k, v in sorted(marks.items())},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()
    rows = []
    for r, _, fs in os.walk(os.path.join(ROOT, "Zh")):
        for f in sorted(fs):
            if not f.endswith(".txt") or "中日对照" in f:
                continue
            p = os.path.join(r, f)
            if os.path.getsize(p) < 20000:
                continue
            rows.append(score_file(p))
    rows.sort(key=lambda x: -x["score"])
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    import statistics
    print(f"{len(rows)} files, median score {statistics.median(r['score'] for r in rows):.2f}")
    for r in rows[:a.top]:
        print(f"{r['score']:6.2f} {r['chars']:>8} {r['path']}")
    print("->", OUT)


if __name__ == "__main__":
    main()