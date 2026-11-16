import os, re, sys, json, glob

ROOT = sys.argv[1]
OUT = sys.argv[2]
CFG = sys.argv[3]

d = json.load(open(CFG, encoding='utf-8'))
cs = d.get('character_substitution', {})
table = str.maketrans(cs['source_characters'], cs['target_characters'])

CJK = re.compile(r'[\u4e00-\u9fff]')
KANA = re.compile(r'[\u3041-\u30fa\u30fd-\u30ff]')
BAD = re.compile(r'[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f]')

lines = []
for f in sorted(glob.glob(os.path.join(ROOT, '*.txt'))):
    s = open(f, encoding='utf-8-sig', errors='replace').read()
    s = s.translate(table).replace('\r\n', '\n').replace('\r', '\n')
    for ln in s.split('\n'):
        ln = ln.strip()
        if not ln:
            continue
        if 'SteinsGate' in ln or '2dfan' in ln:
            continue
        if BAD.search(ln):
            ln = BAD.sub('', ln)
        if len(CJK.findall(ln)) < 2:
            continue
        k = len(KANA.findall(ln)); c = len(CJK.findall(ln))
        if k >= 3 and k >= c * 0.6:
            continue
        if len(ln) > 500:
            ln = ln[:500]
        lines.append(ln)

# drop consecutive duplicates
ded = []
for x in lines:
    if not ded or ded[-1] != x:
        ded.append(x)
body = '\n'.join(ded)
open(OUT, 'w', encoding='utf-8', newline='\n').write(body + '\n')
print('lines', len(ded), 'body', len(body), 'cjk', len(CJK.findall(body)), 'kana', len(KANA.findall(body)))
