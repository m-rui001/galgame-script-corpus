"""Validate the galgame script corpus.

Hard failures: non-UTF8, BOM, U+FFFD, empty files, byte-identical duplicates.
Warnings: suspicious language mix, very short files, missing dialogue structure.

Run: python tools/validate_corpus.py
"""
import os, sys, re, json, hashlib, collections

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KANA = re.compile(r"[\u3040-\u30ff]")
CJK = re.compile(r"[\u4e00-\u9fff]")
LAT = re.compile(r"[A-Za-z]")
DIALOG = re.compile(r"[「『\"“]|^[^\s:：]{1,16}[:：]")
SKIP_DIRS = {".git", "tools"}
REF = os.path.join("Zh", "_reference")

def main():
    errors = []
    warnings = []
    hashes = {}
    stats = collections.Counter()
    for dirpath, dirs, files in os.walk(ROOT):
        rel_dir = os.path.relpath(dirpath, ROOT)
        if rel_dir.split(os.sep)[0] in SKIP_DIRS:
            dirs[:] = []
            continue
        for fn in files:
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT)
            b = open(p, "rb").read()
            stats["files"] += 1
            stats["bytes"] += len(b)
            if b.startswith(b"\xef\xbb\xbf"):
                errors.append((rel, "BOM"))
            try:
                s = b.decode("utf-8")
            except UnicodeDecodeError:
                errors.append((rel, "non-utf8"))
                continue
            if "\ufffd" in s:
                errors.append((rel, "replacement-char"))
            if len(s.strip()) < 20:
                errors.append((rel, "empty"))
            h = hashlib.md5(b).hexdigest()
            if h in hashes:
                errors.append((rel, f"duplicate-of:{hashes[h]}"))
            else:
                hashes[h] = rel
            lines = [l for l in s.splitlines() if l.strip()]
            if len(s) < 300 and rel.split(os.sep)[0] != "English":
                warnings.append((rel, "short"))
            if rel.startswith(REF + os.sep):
                stats["reference"] += 1
                continue
            bilingual = "中日对照" in fn
            kana = len(KANA.findall(s)) / max(1, len(s))
            cjk = len(CJK.findall(s)) / max(1, len(s))
            latin = len(LAT.findall(s)) / max(1, len(s))
            top = rel.split(os.sep)[0]
            if bilingual:
                stats["bilingual"] += 1
                continue
            if top == "English":
                if latin < 0.35:
                    warnings.append((rel, "english-low-latin"))
                if kana > 0.01:
                    warnings.append((rel, "english-with-kana"))
            elif top == "JA":
                if kana < 0.01 and cjk < 0.05:
                    warnings.append((rel, "ja-low-kana"))
            elif top == "Zh":
                if kana > 0.01:
                    warnings.append((rel, f"zh-kana:{kana:.3f}"))
                if cjk < 0.05:
                    warnings.append((rel, "zh-low-cjk"))
                if not any(DIALOG.search(l) for l in lines[:500]):
                    warnings.append((rel, "no-dialogue-prefix"))
            else:
                warnings.append((rel, "unknown-top-dir"))
    report = {
        "files": stats["files"],
        "mb": round(stats["bytes"] / 1e6, 1),
        "reference": stats["reference"],
        "bilingual": stats["bilingual"],
        "errors": len(errors),
        "warnings": len(warnings),
        "error_sample": errors[:20],
        "warning_sample": warnings[:30],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
