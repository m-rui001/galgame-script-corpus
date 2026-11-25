"""Rebuild MANIFEST.csv from the current tree."""
import os, re, csv, hashlib, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KANA = re.compile(r"[\u3040-\u30ff]")
CJK = re.compile(r"[\u4e00-\u9fff]")
LAT = re.compile(r"[A-Za-z]")
DIALOG = re.compile(r"[「『\"“]|^[^\s:：]{1,16}[:：]")

def load_vndb_index():
    index = {}
    p = os.path.join(ROOT, "VNDB_INDEX.csv")
    if not os.path.exists(p):
        return index
    for row in csv.DictReader(open(p, encoding="utf-8")):
        index[row["path"]] = row["vndb_id"]
    return index


def lookup(index, rel):
    if rel in index:
        return index[rel]
    for k, v in index.items():
        if k.endswith("/") and rel.startswith(k):
            return v
    return ""


def main():
    rows = []
    vndb = load_vndb_index()
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "tools")]
        for fn in files:
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
            b = open(p, "rb").read()
            s = b.decode("utf-8")
            lines = [l for l in s.splitlines() if l.strip()]
            dlg = sum(1 for l in lines if DIALOG.search(l))
            kana = len(KANA.findall(s)) / max(1, len(s))
            top = rel.split("/")[0]
            lang = {"English": "en", "JA": "ja", "Zh": "zh", "Bilingual": "bi"}.get(top, "other")
            bilingual = "中日对照" in fn or top == "Bilingual"
            reference = rel.startswith("Zh/_reference/")
            flags = []
            if len(s) < 300: flags.append("short")
            if kana > 0.01 and not bilingual: flags.append("kana_residue")
            if dlg / max(1, len(lines)) < 0.02: flags.append("low_dialogue")
            rows.append({
                "path": rel, "vndb_id": lookup(vndb, rel), "lang": lang,
                "bilingual": int(bilingual), "reference": int(reference),
                "chars": len(s), "lines": len(lines), "dialogue_lines": dlg,
                "dialogue_ratio": round(dlg / max(1, len(lines)), 3),
                "kana_ratio": round(kana, 4),
                "cjk_ratio": round(len(CJK.findall(s)) / max(1, len(s)), 4),
                "latin_ratio": round(len(LAT.findall(s)) / max(1, len(s)), 4),
                "flags": ";".join(flags),
                "sha1": hashlib.sha1(b).hexdigest(),
            })
    rows.sort(key=lambda x: x["path"])
    with open(os.path.join(ROOT, "MANIFEST.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    summary = {
        "files": len(rows),
        "by_lang": {k: sum(1 for r in rows if r["lang"] == k) for k in ("en", "ja", "zh", "other")},
        "bilingual": sum(r["bilingual"] for r in rows),
        "reference": sum(r["reference"] for r in rows),
        "kana_residue": sum(1 for r in rows if "kana_residue" in r["flags"]),
        "short": sum(1 for r in rows if "short" in r["flags"]),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
