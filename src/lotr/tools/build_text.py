# Merge translations and build the replacement pack.
#   python tools/build_text.py            -> build/pack.bin (+ build/text.csv, build/chars.txt, fonts)
# Inputs: text/src/all.json, text/out/chunkNN.json, text/fixes.json ({"english": "japanese"} overrides, optional)
import json, os, sys, glob, re
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8')
import tcsv, mkfont, mkpack

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
B = os.path.join(ROOT, 'build')

def load_map():
    items = json.load(open(os.path.join(ROOT, 'text', 'src', 'all.json'), encoding='utf-8'))
    byid = {x['id']: x for x in items}
    tr = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'text', 'out', 'chunk*.json'))):
        for k, v in json.load(open(p, encoding='utf-8')).items():
            tr[byid[int(k)]['en']] = v
    fx = os.path.join(ROOT, 'text', 'fixes.json')
    if os.path.exists(fx):
        for k, v in json.load(open(fx, encoding='utf-8')).items():
            tr[k] = v
    rp = os.path.join(ROOT, 'text', 'replace.json')
    if os.path.exists(rp):
        rep = json.load(open(rp, encoding='utf-8'))
        for k in tr:
            for a, b in rep.items(): tr[k] = tr[k].replace(a, b)
    missing = [x for x in items if x['en'] not in tr]
    return tr, missing

def polish(s):
    s = s.replace('...', '……').replace('¬', '')
    return s

def main():
    os.makedirs(B, exist_ok=True)
    tr, missing = load_map()
    if missing: print('untranslated:', len(missing))
    it = tcsv.load(os.path.join(ROOT, 'orig', 'text.csv'))
    n = 0
    for k, v in it:
        if k != 'rec' or v[0] == 'LABEL' or len(v) < 16: continue
        en = v[3]
        if en in tr:
            ja = polish(tr[en])
            for c in range(3, 16): v[c] = ja
            n += 1
    raw = tcsv.build(it).encode('utf-8')
    assert '"' not in ''.join(tr.values())
    open(os.path.join(B, 'text.csv'), 'wb').write(raw)
    chars = sorted(set(raw.decode('utf-8')) - set('\r\n'))
    open(os.path.join(B, 'chars.txt'), 'w', encoding='utf-8').write(''.join(chars))
    print('records translated', n, 'chars', len(chars))
    mkfont.build(os.path.join(ROOT, 'orig', 'font_nxg.ft2'), chars, os.path.join(B, 'font_nxg.ft2'))
    mkfont.build(os.path.join(ROOT, 'orig', 'font_rus_nxg.ft2'), chars, os.path.join(B, 'font_rus_nxg.ft2'))
    O = lambda p: os.path.getsize(os.path.join(ROOT, 'orig', p))
    R = lambda p: open(os.path.join(B, p), 'rb').read()
    mkpack.pack([(0, 'text.csv', O('text.csv'), raw),
                 (0, 'font_nxg.ft2', O('font_nxg.ft2'), R('font_nxg.ft2')),
                 (0, 'font_rus_nxg.ft2', O('font_rus_nxg.ft2'), R('font_rus_nxg.ft2'))], os.path.join(B, 'pack.bin'))

if __name__ == '__main__':
    main()
