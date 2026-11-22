"""Structural check for the polish pass: compare working tree against git HEAD.

What must not change: line count, speaker prefixes, quote counts, digit sets,
names, and the absence of kana. What is expected to drop: passive 被, 的时候,
的话, 作为, 一个, sentence-initial conjunctions.

    python tools/polish/verify_polish.py            # all changed Zh files
    python tools/polish/verify_polish.py --only ひぐらし
"""
import os, re, sys, csv, argparse, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "..", "_audit", "polish_verify.csv")
SPEAKER = re.compile(r"^([^\s：:（(「『]{1,6})[：:]")
KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30fa\u30fc-\u30ff]")  # 不含 U+30FB「・」
DIGITS = re.compile(r"[0-9０-９]+")
CONTENT = re.compile(r"[^一-鿿0-9０-９A-Za-zＡ-Ｚａ-ｚ]")
MARKERS = {
    "被": "被",
    "的时候": "的时候",
    "的话": "的话",
    "作为": "作为",
    "一个": "一个",
    "对于": "对于",
    "进行": "进行",
    "做出": r"做出|作出",
}


def head_text(rel):
    try:
        return subprocess.run(["git", "-C", ROOT, "-c", "core.quotepath=false", "show", f"HEAD:{rel}"],
                              capture_output=True, check=True).stdout.decode("utf-8")
    except subprocess.CalledProcessError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    a = ap.parse_args()

    changed = subprocess.run(["git", "-C", ROOT, "-c", "core.quotepath=false",
                              "diff", "--name-only", "HEAD", "--", "Zh"],
                             capture_output=True, check=True).stdout.decode("utf-8").split("\n")
    rows = []
    for rel in [r.strip() for r in changed if r.strip().endswith(".txt")]:
        if a.only and a.only not in rel:
            continue
        old = head_text(rel)
        if old is None:
            continue
        new = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        ol, nl = old.split("\n"), new.split("\n")
        bad = []
        if len(ol) != len(nl):
            bad.append(f"lines:{len(ol)}->{len(nl)}")
        drops = {k: 0 for k in MARKERS}
        for i, (x, y) in enumerate(zip(ol, nl)):
            if x == y:
                continue
            sx, sy = SPEAKER.match(x), SPEAKER.match(y)
            if bool(sx) != bool(sy) or (sx and sx.group(1) != sy.group(1)):
                bad.append(f"speaker@{i + 1}:{x.strip()[:20]}->{y.strip()[:20]}")
            if sorted(DIGITS.findall(x)) != sorted(DIGITS.findall(y)):
                bad.append(f"digits@{i + 1}")
            if x.count("「") + x.count("『") != y.count("「") + y.count("『"):
                bad.append(f"quotes@{i + 1}")
            if KANA.search(y) and not KANA.search(x):
                bad.append(f"kana@{i + 1}")
            cx, cy = len(CONTENT.sub("", x)), len(CONTENT.sub("", y))
            if cy > 1.5 * max(1, cx) or cy < 0.4 * cx:
                bad.append(f"length@{i + 1}:{cx}->{cy}")
            for k, pat in MARKERS.items():
                drops[k] += len(re.findall(pat, x)) - len(re.findall(pat, y))
        tot_old = sum(len(x) for x in ol)
        rows.append({"path": rel, "lines": len(ol), "chars": tot_old,
                     **{f"-{k}": v for k, v in drops.items()},
                     "problems": len(bad), "detail": "; ".join(bad[:6])})

    if not rows:
        print("no changed Zh files vs HEAD")
        return
    rows.sort(key=lambda r: -r["problems"])
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} files checked, {sum(r['problems'] for r in rows)} problems -> {OUT}")
    for r in rows[:10]:
        print(r["path"], r["lines"], "problems", r["problems"], r["detail"][:120])
    agg = {k: sum(r[k] for r in rows) for k in rows[0] if k.startswith("-")}
    print("marker deltas:", agg)


if __name__ == "__main__":
    main()