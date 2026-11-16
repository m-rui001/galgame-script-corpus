import os,re,sys,hashlib
CJK=re.compile(r'[\u4e00-\u9fff]'); KANA=re.compile(r'[\u3041-\u30fa\u30fd-\u30ff]')
BAD=re.compile(r'[\uac00-\ud7af\u3130-\u318f\uff66-\uff9f\ue000-\uf8ff]')
TAG=re.compile(r'\[[^\[\]]{0,100}\]')
def dec(b):
    if b.startswith(b'\xff\xfe'): return b[2:].decode('utf-16le','ignore')
    if b.startswith(b'\xfe\xff'): return b[2:].decode('utf-16be','ignore')
    if b.count(b'\x00')>len(b)//4: return b.decode('utf-16le','ignore')
    try: return b.decode('utf-8')
    except: return b.decode('gbk','ignore')
def clean(s):
    out=[]
    for line in s.replace('\r','\n').split('\n'):
        line=line.strip()
        if not line or line[0] in '@*;#': continue
        if line.startswith('//'): continue
        if BAD.search(line): continue
        line=TAG.sub('',line).replace('\u3000',' ').strip()
        if not line: continue
        c=len(CJK.findall(line)); k=len(KANA.findall(line))
        if c<2: continue
        vis=[ch for ch in line if not ch.isspace()]
        if c < len(vis)*0.4: continue
        if k>=3 and k>=c*0.4: continue
        if len(line)>500: line=line[:500]
        out.append(line)
    ded=[]
    for x in out:
        if not ded or ded[-1]!=x: ded.append(x)
    return ded
def run(rid):
    base=os.path.join(r'D:\mxrlib\_patches\scripts',str(rid))
    files=[]
    for dp,_,fs in os.walk(base):
        for fn in fs:
            q=os.path.join(dp,fn); ext=os.path.splitext(fn)[1].lower()
            if ext in ('.png','.jpg','.bmp','.tga','.wav','.ogg','.mp4','.ttf','.otf','.dll','.exe','.arc','.xp3','.pck','.dat','.bin'): continue
            if os.path.getsize(q)>15*1024*1024: continue
            files.append(q)
    files.sort(key=lambda p:(os.path.basename(p).lower(),p))
    lines=[]; seen=set(); used=0
    for q in files:
        ls=clean(dec(open(q,'rb').read()))
        if not ls: continue
        key=hashlib.sha1('\n'.join(ls).encode()).hexdigest()
        if key in seen: continue
        seen.add(key); used+=1; lines.extend(ls)
    body='\n'.join(lines)
    open(os.path.join(r'D:\mxrlib\_patches\clean',f'{rid}.txt'),'w',encoding='utf-8',newline='\n').write(body+'\n')
    c=len(CJK.findall(body)); k=len(KANA.findall(body))
    print(rid,'files',used,'chars',len(body),'lines',len(lines),'cjk',c,'kana%',round(k/max(1,len(body)),4),'sha',hashlib.sha1(body.encode()).hexdigest()[:10])
if __name__=='__main__':
    for x in sys.argv[1:]: run(int(x))
