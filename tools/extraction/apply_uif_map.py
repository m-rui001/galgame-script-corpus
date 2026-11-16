import json, sys

cfg = json.load(open(r'D:\mxrlib\_patches\raw\7423\gemini25pro\uif_config.json', encoding='utf-8'))
cs = cfg['character_substitution']
table = str.maketrans(cs['source_characters'], cs['target_characters'])

for path in sys.argv[1:]:
    s = open(path, encoding='utf-8').read()
    out = s.translate(table)
    open(path, 'w', encoding='utf-8', newline='\n').write(out)
    print(path, len(s), '->', len(out))
