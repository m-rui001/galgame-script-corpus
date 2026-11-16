import os, re, sys, glob
from collections import defaultdict
from fontTools.ttLib import TTFont

ROOT = sys.argv[1] if len(sys.argv) > 1 else r'D:\mxrlib\_patches\tmp\4922'
FONT = sys.argv[2] if len(sys.argv) > 2 else r'D:\mxrlib\_patches\raw\4922\世界征服彼女-gemini-2.5-pro\SekaiSeifukuKanojo_cnjp.ttf'
OUT = sys.argv[3] if len(sys.argv) > 3 else r'D:\mxrlib\_patches\clean\4922.txt'

if FONT and os.path.exists(FONT):
    f = TTFont(FONT, lazy=True)
    cm = f.getBestCmap()
else:
    cm = {}
inv = defaultdict(list)
for cp, g in cm.items():
    inv[g].append(cp)

def cp932ok(cp):
    try:
        chr(cp).encode('cp932')
        return True
    except Exception:
        return False

fix_cache = {}
def fix_char(ch):
    r = fix_cache.get(ch)
    if r is not None:
        return r
    g = cm.get(ord(ch))
    r = ch
    if g:
        cands = [c for c in inv.get(g, []) if c != ord(ch) and not cp932ok(c)]
        if len(cands) == 1:
            r = chr(cands[0])
    fix_cache[ch] = r
    return r

STR_RE = re.compile(r'push_string\("((?:[^"\\]|\\.)*)"\)')
ESC = {'r': '\r', 'n': '\n', 't': '\t', '"': '"', '\\': '\\'}
CJK = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
KANA = re.compile(r'[\u3040-\u30ff]')
BAD = re.compile(r'[\ufffd\ue000-\uf8ff]')

def unescape(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s):
            n = s[i+1]
            if n in ESC:
                out.append(ESC[n]); i += 2; continue
            if n == 'x' and i + 3 < len(s):
                try:
                    out.append(chr(int(s[i+2:i+4], 16))); i += 4; continue
                except Exception:
                    pass
            i += 2; continue
        out.append(c); i += 1
    return ''.join(out)

def clean_line(s):
    s = ''.join(fix_char(c) for c in s)
    s = s.replace('\u3000', ' ')
    s = re.sub(r'[ \t]+', ' ', s).strip()
    if not s:
        return ''
    if s.startswith('E:') or s.startswith('Script'):
        return ''
    if re.fullmatch(r'[A-Za-z0-9_#.\-/: ]+', s):
        return ''
    if len(CJK.findall(s)) < 1:
        return ''
    kana = len(KANA.findall(s))
    if kana > len(CJK.findall(s)) * 0.1:
        return ''
    return s

files = sorted(glob.glob(os.path.join(ROOT, '*.bsd')))
all_lines = []
for bsd in files:
    try:
        text = open(bsd, encoding='utf-8', errors='replace').read()
    except Exception:
        continue
    for m in STR_RE.finditer(text):
        raw = unescape(m.group(1))
        for line in re.split(r'[\r\n]+', raw):
            line = clean_line(line)
            if line:
                all_lines.append(line)

# drop consecutive duplicates
ded = []
for ln in all_lines:
    if not ded or ded[-1] != ln:
        ded.append(ln)

body = '\n'.join(ded)
open(OUT, 'w', encoding='utf-8', newline='\n').write(body + '\n')
cjk = len(CJK.findall(body))
kana = len(KANA.findall(body))
print('files', len(files), 'lines', len(ded), 'chars', len(body), 'cjk', cjk, 'kana', kana)
print('kana_ratio', round(kana / max(1, len(body)), 4))
