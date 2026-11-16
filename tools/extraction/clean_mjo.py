import os, re, sys, struct, hashlib
sys.path.insert(0, r'D:\mxrlib\_audit\tools\majiro-py\src')
from mjotool import crypt

CJK = re.compile(r'[\u4e00-\u9fff]')
KANA = re.compile(r'[\u3041-\u30fa\u30fd-\u30ff]')
BAD = re.compile(r'[\uac00-\ud7af\u3130-\u318f\uff66-\uff9f\ue000-\uf8ff\x00-\x08\x0b\x0c\x0e-\x1f]')
COMMON = set('的了是我你他她它们吗呢吧啊这那就都也很不在有和人个上下来去说想要会到看听到给被把让对为与而但却又还只再才更最没么什怎样这样那样')
ASSET = re.compile(r'^(se[-_]|bg|vo|f_|cg|pic|yaz|transit|console|utility)', re.I)


def extract(path):
    b = open(path, 'rb').read()
    if b[:16] != b'MajiroObjX1.000\x00':
        return []
    sig, main, lines, fnc = struct.unpack_from('<16sIII', b, 0)
    off = 28 + 8 * fnc
    if off + 4 > len(b):
        return []
    size = struct.unpack_from('<I', b, off)[0]
    off += 4
    d = crypt.crypt32(b[off:off + size])
    out = []
    for chunk in d.split(b'\x00'):
        try:
            s = chunk.decode('cp932')
        except UnicodeDecodeError:
            continue
        s = s.replace('\u3000', ' ').strip()
        if not s or len(s) < 3 or BAD.search(s):
            continue
        if ASSET.search(s) or re.search(r'[\\/]', s):
            continue
        # drop speaker-only tags
        s2 = re.sub(r'^【[^】]{1,12}】$', '', s).strip()
        if not s2:
            continue
        s = s2
        c = len(CJK.findall(s))
        k = len(KANA.findall(s))
        if c < 2:
            continue
        vis = [ch for ch in s if not ch.isspace()]
        if c < len(vis) * 0.4:
            continue
        if k >= 3 and k >= c * 0.5:
            continue
        com = sum(ch in COMMON for ch in s)
        if not com and not re.search(r'[。！？，、…—「」『』：；]', s):
            continue
        if not re.search(r'[。！？，、…—「」『』：；]', s) and len(s) < 10:
            continue
        if len(s) > 500:
            s = s[:500]
        out.append(s)
    ded = []
    for x in out:
        if not ded or ded[-1] != x:
            ded.append(x)
    return ded


def run(rid):
    base = os.path.join(r'D:\mxrlib\_patches\tmp', str(rid))
    files = []
    for dp, _, fs in os.walk(base):
        for fn in fs:
            if fn.lower().endswith('.mjo'):
                files.append(os.path.join(dp, fn))
    files.sort(key=lambda p: os.path.basename(p).lower())
    lines = []
    seen = set()
    used = 0
    for q in files:
        ls = extract(q)
        if not ls:
            continue
        key = hashlib.sha1('\n'.join(ls).encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        used += 1
        lines.extend(ls)
    body = '\n'.join(lines)
    p = os.path.join(r'D:\mxrlib\_patches\clean', f'{rid}.txt')
    open(p, 'w', encoding='utf-8', newline='\n').write(body + '\n')
    c = len(CJK.findall(body))
    k = len(KANA.findall(body))
    print(rid, 'files', used, 'chars', len(body), 'lines', len(lines),
          'cjk', c, 'kana%', round(k / max(1, len(body)), 4),
          'sha', hashlib.sha1(body.encode()).hexdigest()[:10])


if __name__ == '__main__':
    for x in sys.argv[1:]:
        run(int(x))
