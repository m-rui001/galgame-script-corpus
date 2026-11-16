import os, re, sys, hashlib

CJK = re.compile(r'[\u4e00-\u9fff]')
KANA = re.compile(r'[\u3041-\u30fa\u30fd-\u30ff]')
STR = re.compile(r'"((?:[^"\\]|\\.)*)"')
BAD = re.compile(r'[\uac00-\ud7af\u3130-\u318f\uff66-\uff9f\ue000-\uf8ff]')


def dec(b):
    if b.startswith(b'\xff\xfe'):
        return b[2:].decode('utf-16le', 'ignore')
    try:
        return b.decode('utf-8-sig')
    except UnicodeDecodeError:
        return b.decode('gbk', 'ignore')


def run(rid, outdir=r'D:\mxrlib\_patches\clean'):
    base = os.path.join(r'D:\mxrlib\_patches\raw', str(rid))
    files = []
    for dp, _, fs in os.walk(base):
        for fn in fs:
            if fn.lower().endswith('.ast'):
                files.append(os.path.join(dp, fn))
    files.sort(key=lambda p: os.path.basename(p).lower())
    lines = []
    seen = set()
    used = 0
    for q in files:
        s = dec(open(q, 'rb').read())
        chunk = []
        for raw in STR.findall(s):
            t = raw.replace('\\n', '\n').replace('\\"', '"').replace('\\t', ' ')
            for part in t.split('\n'):
                part = part.replace('\u3000', ' ').strip()
                if not part or BAD.search(part):
                    continue
                if re.search(r'[\\/:]', part) and not CJK.search(part):
                    continue
                c = len(CJK.findall(part))
                k = len(KANA.findall(part))
                if c < 2:
                    continue
                vis = [ch for ch in part if not ch.isspace()]
                if c < len(vis) * 0.4:
                    continue
                if k >= 3 and k >= c * 0.5:
                    continue
                if not re.search(r'[。！？，、…—「」『』：；]', part) and len(part) <= 2:
                    continue
                if len(part) > 500:
                    part = part[:500]
                chunk.append(part)
        ded = []
        for x in chunk:
            if not ded or ded[-1] != x:
                ded.append(x)
        if not ded:
            continue
        key = hashlib.sha1('\n'.join(ded).encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        used += 1
        lines.extend(ded)
    body = '\n'.join(lines)
    p = os.path.join(outdir, f'{rid}.txt')
    open(p, 'w', encoding='utf-8', newline='\n').write(body + '\n')
    c = len(CJK.findall(body))
    k = len(KANA.findall(body))
    print(rid, 'files', used, 'chars', len(body), 'lines', len(lines),
          'cjk', c, 'kana%', round(k / max(1, len(body)), 4),
          'sha', hashlib.sha1(body.encode()).hexdigest()[:10])


if __name__ == '__main__':
    for x in sys.argv[1:]:
        run(int(x))
