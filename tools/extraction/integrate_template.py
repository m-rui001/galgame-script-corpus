import os, re, csv, json, hashlib, sys

ROOT = r'D:\mxrlib\galgame-script-corpus'
CLEAN = r'D:\mxrlib\_patches\clean'
CJK = re.compile(r'[\u4e00-\u9fff]')
KANA = re.compile(r'[\u3041-\u30fa\u30fd-\u30ff]')
NAME_TAG = re.compile(r'^【[^】]{1,40}】')

MAP = [
    (4837, 'Zh/窓ごしの部屋3 [gemini-2.5-pro].txt'),
    (9427, 'Zh/サマー☆きゃんぷ [gemini-3-flash].txt'),
]
TITLES = {4837: '窓ごしの部屋3', 9427: 'サマー☆きゃんぷ'}
MODELS = {4837: 'gemini-2.5-pro', 9427: 'gemini-3-flash-preview'}
NOTES = {
    4837: 'KiriKiri .ks scripts from patch cache; gemini-2.5-pro translation',
    9427: 'KiriKiri scripts; gemini-3-flash-preview; patch also fixes voice toggle and CG script errors',
}

meta = {}
for line in open(r'D:\mxrlib\_audit\patch_meta.jsonl', encoding='utf-8'):
    m = json.loads(line); meta[m['id']] = m
det = {}
for line in open(r'D:\mxrlib\_audit\resource_details.jsonl', encoding='utf-8'):
    m = json.loads(line); det[m['id']] = m

existing_hashes = {}
for dirpath, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'tools')]
    for fn in files:
        if fn.endswith('.txt'):
            p = os.path.join(dirpath, fn)
            existing_hashes[hashlib.sha1(open(p, 'rb').read()).hexdigest()] = os.path.relpath(p, ROOT).replace(os.sep, '/')

errors = []
rows = []
payload = {}
for rid, rel in MAP:
    if os.path.exists(os.path.join(ROOT, rel)):
        errors.append((rid, 'target exists'))
    b = open(os.path.join(CLEAN, f'{rid}.txt'), 'rb').read()
    s = b.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
    if '\ufffd' in s:
        errors.append((rid, 'encoding'))
    lines = [l for l in s.splitlines() if l.strip()]
    body = ''.join(lines)
    cjk = len(CJK.findall(s)); kana = len(KANA.findall(s))
    kana_ratio = kana / max(1, len(s)); cjk_ratio = cjk / max(1, len(s))
    jp = 0
    for l in lines:
        l2 = NAME_TAG.sub('', l)
        c2 = len(CJK.findall(l2)); k2 = len(KANA.findall(l2))
        if k2 >= 3 and k2 >= c2 * 0.6:
            jp += 1
    jp_ratio = jp / max(1, len(lines))
    maxline = max((len(l) for l in lines), default=0)
    if len(body) < 30000: errors.append((rid, f'short:{len(body)}'))
    if kana_ratio > 0.03: errors.append((rid, f'kana:{kana_ratio:.3f}'))
    if cjk_ratio < 0.5: errors.append((rid, f'cjk:{cjk_ratio:.3f}'))
    if jp_ratio > 0.01: errors.append((rid, f'jp:{jp_ratio:.3f}'))
    if maxline > 500: errors.append((rid, f'longline:{maxline}'))
    nb = s.encode('utf-8')
    sha = hashlib.sha1(nb).hexdigest()
    if sha in existing_hashes: errors.append((rid, 'dup-existing:' + existing_hashes[sha]))
    payload[rid] = nb
    p = meta.get(rid, {}); d = det.get(rid, {})
    rows.append({
        'path': rel, 'source': 'moyu.moe', 'source_url': f'https://www.moyu.moe/resource/{rid}',
        'resource_id': rid, 'patch_name': TITLES[rid],
        'patch_type': ';'.join(p.get('type') or []), 'model': MODELS[rid],
        'galgame_id': p.get('galgame_id', ''), 'vndb_id': d.get('vndb', ''),
        'extracted_on': '2026-11-16', 'note': NOTES[rid],
        'chars': len(s), 'lines': len(lines), 'kana_ratio': round(kana_ratio, 4),
    })

if errors:
    print('BLOCKED:')
    for e in errors: print(' ', e)
    sys.exit(1)

for rid, rel in MAP:
    open(os.path.join(ROOT, rel), 'wb').write(payload[rid])

fields = ['path', 'source', 'source_url', 'resource_id', 'patch_name', 'patch_type', 'model',
          'galgame_id', 'vndb_id', 'extracted_on', 'note', 'chars', 'lines', 'kana_ratio']
src_csv = os.path.join(ROOT, 'SOURCES.csv')
old_rows = list(csv.DictReader(open(src_csv, encoding='utf-8')))
with open(src_csv, 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=fields, lineterminator='\n')
    w.writeheader(); w.writerows(old_rows + rows)
for r in rows:
    print(r['resource_id'], r['chars'], r['lines'], r['kana_ratio'])
print('added', len(rows))
