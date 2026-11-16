import os, re, subprocess, sys, hashlib

ROOT = r'D:\mxrlib'
GAR = os.path.join(ROOT, '_audit', 'tools', 'garbro2', 'GARbro.Console.exe')
RAW = os.path.join(ROOT, '_patches', 'raw')
OUT = os.path.join(ROOT, '_patches', 'tmp', 'xp3')
SOURCES = os.path.join(ROOT, 'galgame-script-corpus', 'SOURCES.csv')

done_ids = set()
with open(SOURCES, encoding='utf-8-sig') as f:
    for line in f:
        parts = line.rstrip('\n').split(',')
        if len(parts) > 3 and parts[3].isdigit():
            done_ids.add(int(parts[3]))

SKIP_IDS = {1767, 3374}  # duplicate title, nukige
PREF = {
    9202: ('gemini31pro/patch.xp3',),
    969: (),
    6675: None,
}

def list_entries(xp3):
    r = subprocess.run([GAR, 'l', xp3], capture_output=True)
    out = r.stdout.decode('utf-8', 'replace')
    ents = []
    for line in out.splitlines():
        m = re.match(r'\s*\[[0-9A-F]+\]\s+(\d+)\s+(.+?)\s*$', line)
        if m:
            size = int(m.group(1)); name = m.group(2)
            if re.search(r'\.(ks|txt)$', name, re.I) and not re.search(r'\.scn$', name, re.I):
                ents.append((name, size))
    return ents

cands = []
for dirpath, dirnames, filenames in os.walk(RAW):
    for fn in filenames:
        if not fn.lower().endswith('.xp3'):
            continue
        path = os.path.join(dirpath, fn)
        m = re.search(r'raw[\\/](\d+)[\\/]', path)
        if not m:
            continue
        rid = int(m.group(1))
        if rid in done_ids or rid in SKIP_IDS:
            continue
        ents = list_entries(path)
        total = sum(s for _, s in ents)
        if total >= 1_000_000:
            rel = os.path.relpath(path, RAW).replace('\\', '/')
            cands.append((rid, total, len(ents), rel, path))

cands.sort(key=lambda x: -x[1])
seen = {}
for rid, total, n, rel, path in cands:
    if rid in PREF:
        pats = PREF[rid]
        if pats is not None and not any(rel.endswith(p) for p in pats):
            continue
    seen.setdefault(rid, 0)
    seen[rid] += 1
    slug = re.sub(r'[^\w.-]+', '_', rel)[-60:]
    dest = os.path.join(OUT, str(rid), slug)
    os.makedirs(dest, exist_ok=True)
    print(f'extract {rid} {total} {rel}', flush=True)
    r = subprocess.run([GAR, 'x', '-y', '-ni', '-na', '-f', r'\.(ks|txt)$', '-o', dest, path],
                       capture_output=True)
    if r.returncode != 0:
        print('  rc', r.returncode, r.stderr.decode('utf-8', 'replace')[:300], flush=True)
print('done', len(cands))
