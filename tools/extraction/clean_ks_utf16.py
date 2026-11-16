import os, re, sys, hashlib

CJK = re.compile(r'[\u4e00-\u9fff]')
KANA = re.compile(r'[\u3041-\u30fa\u30fd-\u30ff]')
TAG = re.compile(r'\[[^\[\]]{0,60}\]')
COMMON = set('的了是我你他她它们吗呢吧啊这那就都也很不在有和人个上下来去说想要会到看听到给被把让对为与而但却又还只再才更最没么什怎样这样那样')
BAD = re.compile(r'[\uac00-\ud7af\u3130-\u318f\uff66-\uff9f\ue000-\uf8ff\x00-\x08\x0b\x0c\x0e-\x1f]')

def decode(b):
    if b.startswith(b'\xff\xfe'):
        return b[2:].decode('utf-16le', 'replace')
    if b.startswith(b'\xfe\xff'):
        return b[2:].decode('utf-16be', 'replace')
    if b.count(b'\x00') > len(b) // 4:
        return b.decode('utf-16le', 'replace')
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('cp932', 'replace')

def score_text(s):
    return sum(s.count(ch) for ch in COMMON)

def clean_line(line):
    line = line.replace('\ufeff', '').replace('\u3000', ' ').strip()
    if not line or line[0] in '@*;#' or line.startswith('//'):
        return ''
    if BAD.search(line):
        return ''
    out = []
    pos = 0
    for m in TAG.finditer(line):
        inner = m.group(0)[1:-1]
        out.append(line[pos:m.start()])
        pos = m.end()
        if not CJK.search(inner):
            continue
        if '=' in inner or ':' in inner:
            continue
        if m.start() == 0 and len(inner) <= 8:
            continue
    out.append(line[pos:])
    line = ''.join(out)
    line = re.sub(r'\[[^\[\]]{0,60}\]', '', line).strip()
    if not line or not CJK.search(line):
        return ''
    c = len(CJK.findall(line)); k = len(KANA.findall(line))
    if k >= 3 and k >= c * 0.6:
        return ''
    visible = [ch for ch in line if not ch.isspace()]
    if not visible:
        return ''
    if c < 2 or c < len(visible) * 0.4:
        return ''
    if len(line) > 500:
        line = line[:500]
    return line

def collect(root, layer_pick=False):
    files = []
    for dp, _, fs in os.walk(root):
        for fn in fs:
            if fn.lower().endswith(('.ks', '.txt')):
                q = os.path.join(dp, fn)
                low = q.lower()
                if re.search(r'[\/](macro|plugin|system|sys)[\/]', low) or 'plugin' in os.path.basename(low):
                    continue
                files.append(q)
    if layer_pick:
        best = {}
        for p in files:
            key = os.path.basename(p)
            s = decode(open(p, 'rb').read())
            sc = score_text(s)
            if key not in best or sc > best[key][0]:
                best[key] = (sc, p)
        files = sorted((v[1] for v in best.values()), key=lambda p: os.path.basename(p).lower())
    else:
        files.sort(key=lambda p: os.path.basename(p).lower())
    return files

def main(rid, root, out, layer_pick=False):
    files = collect(root, layer_pick)
    lines = []
    for p in files:
        s = decode(open(p, 'rb').read())
        for ln in s.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
            t = clean_line(ln)
            if t:
                lines.append(t)
    body = '\n'.join(lines)
    open(out, 'w', encoding='utf-8', newline='\n').write(body + '\n')
    c = len(CJK.findall(body)); k = len(KANA.findall(body))
    print(rid, 'files', len(files), 'chars', len(body), 'lines', len(lines),
          'cjk', c, 'kana', round(k / max(1, len(body)), 4), 'sha', hashlib.sha1(body.encode()).hexdigest()[:10])

if __name__ == '__main__':
    if len(sys.argv) > 1:
        for rid in sys.argv[1:]:
            main(int(rid), rf'D:\mxrlib\_patches\tmp\xp3\{rid}', rf'D:\mxrlib\_patches\clean\{rid}.txt', layer_pick=True)
    else:
        main(9202, r'D:\mxrlib\_patches\tmp\xp3\9202', r'D:\mxrlib\_patches\clean\9202.txt')
        main(5735, r'D:\mxrlib\_patches\tmp\xp3\5735', r'D:\mxrlib\_patches\clean\5735.txt', layer_pick=True)
