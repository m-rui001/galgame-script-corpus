"""Find corpus scripts from a VNDB id or a title fragment.

    python tools/find_by_vndb.py v3271
    python tools/find_by_vndb.py 晓之护卫
"""
import os, sys, csv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "VNDB_INDEX.csv")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 1
    q = sys.argv[1].strip()
    want = q.lower()
    if want.isdigit():
        want = "v" + want
    rows = list(csv.DictReader(open(INDEX, encoding="utf-8")))
    hits = [r for r in rows if want.startswith("v") and r["vndb_id"].lower() == want]
    if not hits:
        ql = q.casefold()
        hits = [r for r in rows if ql in r["title"].casefold() or ql in r["matched_title"].casefold()]
    if not hits:
        print("no match:", q)
        return 1
    for r in hits:
        print(f'{r["vndb_id"] or "-":>8}  {int(r["chars"]):>9}  {r["lang"]:>7}  {r["path"]}')
        if r["matched_title"]:
            print(f'{"":>8}  {r["matched_title"]}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
