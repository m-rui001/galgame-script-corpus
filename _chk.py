import sys, os, re
sys.path.insert(0,'tools/polish')
from merge_job import free_ok
base=r"D:/mxrlib/_audit/polish_chunks/Zh_画師～隠された思い～_[qwen-max].txt"
NW=re.compile(r"[^\u4e00-\u9fff0-9０-９A-Za-zＡ-Ｚａ-ｚ]")
for f in sys.argv[1:]:
    src=open(os.path.join(base,f),encoding='utf-8').read().split('\n')
    out=open(os.path.join(base,'out',f),encoding='utf-8').read().split('\n')
    if out and out[-1]=='': out=out[:-1]
    a=NW.sub("",'\n'.join(src)); b=NW.sub("",'\n'.join(out))
    print(f, free_ok(src,out), len(src), len(out), round(len(b)/len(a),3))
