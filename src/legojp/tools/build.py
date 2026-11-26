# Build the replacement pack of one game.
#   python build.py <game>      (marvel / hp1 / hp2 / sw)  -> <game>/build/pack.bin (+ built files, chars.txt)
# Translations: text_<grp>/out/prefill.json + chunkNN.json, then text_<grp>/fixes.json ({"english": "japanese"}),
# then text_<grp>/replace.json ({"old": "new"} applied to every translation).
import json, os, sys, glob, struct, ctypes
from textsrc import CsvSrc, LtxtSrc, PLAT_OK
import mkfont2
import delta as deltamod
import re
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.abspath(__file__))
GROUP = {'marvel': 'marvel', 'hp1': 'hp', 'hp2': 'hp', 'sw': 'sw', 'bat1': 'bat', 'bat2': 'bat', 'bat3': 'bat', 'hobbit': 'hobbit'}
# settings entries for the DLL: lang = language id it reports (0x409 if absent), jpcsv = use the JAPANESE column
# of the downloaded front-end CSVs (LEGO Batman 3)
SETTINGS = {'bat3': [('jpcsv', 1)]}
# extra text shown by the game from outside the DAT (characters for the font): game -> [(csv file, column)]
EXTRA_CHARS = {'bat3': [('bat3/orig/dl_text_gamescom.csv', 'JAPANESE')]}

def load_map(grp):
    d = os.path.join(ROOT, 'text_' + grp)
    items = json.load(open(os.path.join(d, 'src', 'all.json'), encoding='utf-8'))
    byid = {x['id']: x for x in items}
    tr = {}
    for p in [os.path.join(d, 'out', 'prefill.json')] + sorted(glob.glob(os.path.join(d, 'out', 'chunk*.json'))):
        for k, v in json.load(open(p, encoding='utf-8')).items():
            tr[byid[int(k)]['en']] = v
    fx = os.path.join(d, 'fixes.json')
    if os.path.exists(fx):
        for k, v in json.load(open(fx, encoding='utf-8')).items(): tr[k] = v
    rp = os.path.join(d, 'replace.json')
    if os.path.exists(rp):
        rep = json.load(open(rp, encoding='utf-8'))
        for k in tr:
            for a, b in rep.items(): tr[k] = tr[k].replace(a, b)
    missing = [x for x in items if x['en'] not in tr]
    wt = os.environ.get('WRAPTEST')       # test only: WRAPTEST="english" makes that string very long
    if wt:
        t = 'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん'
        def sep(c): return c.join(t[i:i + 6] for i in range(0, len(t), 6))
        t = t + t[:30]
        mode = os.environ.get('WRAPMODE', '1')
        NL = chr(13) + chr(10)
        def sep2(c, u): return c.join(u[i:i + 6] for i in range(0, len(u), 6))
        tr[wt] = {'1': 'A' + sep(chr(0x200b)) + NL + 'B' + sep(chr(0x2009)),
                  '2': 'C' + sep(chr(0x3000)) + NL + 'D' + sep(chr(0x3001)),
                  '3': 'E' + sep(' ') + NL + 'F' + sep(chr(0x200a)),
                  '5': 'G' + sep2(chr(0x200b), t[:60]) + 'H' + sep2(chr(0x3000), t[:60]),
                  '6': 'I' + sep2(chr(0x2009), t[:60]) + 'J' + sep2(' ', t[:60])}[mode]
    return {k: polish(v) for k, v in tr.items()}, missing, items

def polish(s):
    s = s.replace('...', '……').replace('¬', '')
    return s

def lzms(data):
    cab = ctypes.WinDLL('cabinet.dll')
    h = ctypes.c_void_p()
    if not cab.CreateCompressor(5, None, ctypes.byref(h)): raise OSError('CreateCompressor')
    need = ctypes.c_size_t()
    cab.Compress(h, data, ctypes.c_size_t(len(data)), None, ctypes.c_size_t(0), ctypes.byref(need))
    buf = ctypes.create_string_buffer(need.value)
    if not cab.Compress(h, data, ctypes.c_size_t(len(data)), buf, need, ctypes.byref(need)): raise OSError('Compress')
    cab.CloseCompressor(h)
    return buf.raw[:need.value]

def pack(entries, out, settings=()):
    """entries: (dat, name, index, origsize, data)  ->  "LJPZ" u32 rawsize + LZMS("LJP2" ...)
    settings: (name, value) -> extra entries ("" name index=value) for the DLL"""
    entries = entries + [('', k, v, 0, b'') for k, v in settings]
    raw = b'LJP2' + struct.pack('<I', len(entries))
    for dat, name, idx, osz, data in entries:
        dn, n = dat.encode('ascii'), name.encode('ascii')
        raw += bytes([len(dn)]) + dn + bytes([len(n)]) + n + struct.pack('<III', idx, osz, len(data)) + data
    z = lzms(raw)
    open(out, 'wb').write(b'LJPZ' + struct.pack('<I', len(raw)) + z)
    print(out, len(raw), '->', len(z) + 8)

def main(game):
    grp = GROUP[game]
    tr, missing, items = load_map(grp)
    if missing:
        print('UNTRANSLATED:', len(missing))
        for x in missing[:20]: print('  ', x['id'], x['en'][:80])
        raise SystemExit(1)
    assert not any('"' in v for v in tr.values())
    B = os.path.join(ROOT, game, 'build'); os.makedirs(B, exist_ok=True)
    files = json.load(open(os.path.join(ROOT, game, 'files.json')))
    built = []
    chars = set()
    fonts = []
    leftover = []
    for dat, idx, kind, name, rel in files:
        raw = open(os.path.join(ROOT, rel), 'rb').read()
        if kind == 'csvjp':
            # the game's own Japanese column for every string that has one, our translation for the rest
            hdr = CsvSrc(raw).header
            ji = hdr.index('JAPANESE')
            def has_ja(t): return bool(re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', t))
            def choose(f, c, ji=ji):
                if f[0] == 'LABEL' or c < 3 or len(f) <= 3: return None
                if len(f) > ji and has_ja(f[ji]): return ('col', ji)
                ja = tr.get(f[3])
                return ('text', ja) if ja is not None else None
            dl = deltamod.csv_delta(idx, raw, choose)
            full = dl.apply()
            s = CsvSrc(full)
            for label, plat, typ, en, v in s.entries():
                if plat in PLAT_OK:
                    for c in v[3:]: chars.update(c)
            n = sum(1 for o in dl.ops if o[0] == 'i')
            print(name, 'delta', dl.stats())
            open(os.path.join(B, name), 'wb').write(full)
            built.append((dat, name, idx, len(raw), dl.encode()))
            continue
        if kind in ('csv', 'csv1'):
            s = CsvSrc(raw, 3 if kind == 'csv' else 1)
            n = s.apply(lambda en, label, typ: tr.get(en))
            out = s.build()
            text = out.decode(s.enc if s.enc != 'utf-16' else 'utf-16')
            # characters actually shown: language columns of the rows the game uses
            for label, plat, typ, en, v in CsvSrc(out, s.first).entries():
                if plat in PLAT_OK:
                    for c in v[s.first:]: chars.update(c)
            for label, plat, typ, en, v in s.entries():
                pass
        elif kind == 'ltxt':
            s = LtxtSrc(raw)
            n = s.apply(lambda en, num, sect: tr.get(en))
            out = s.build()
            for i, num, sect, ja in LtxtSrc(out).entries(): chars.update(ja)
        else:
            fonts.append((dat, idx, kind, name, rel)); continue
        print(name, 'translated', n)
        open(os.path.join(B, name), 'wb').write(out)
        built.append((dat, name, idx, len(raw), out))
    # every string the game shows must be translated: list English-looking strings left in the built files
    tset = set(tr)
    for x in items:
        if x['en'] not in tset: leftover.append(x)
    # strings of this game only (the group may hold several games)
    # characters shown from outside the text files: the DLL's own strings (src/*.c, e.g. the Star Wars PC menu
    # words) and, to be safe, every kana and the common full-width punctuation
    import re as _re
    for p in glob.glob(os.path.join(ROOT, 'src', '*.c')):
        for lit in _re.findall(r'"((?:[^"\\]|\\.)*)"', open(p, encoding='utf-8').read()):
            if _re.search(r'[　-鿿＀-￯]', lit): chars.update(lit)
    for p, col in EXTRA_CHARS.get(game, ()):
        es = CsvSrc(open(os.path.join(ROOT, p), 'rb').read())
        ci = es.header.index(col)
        for label, plat, typ, en, v in es.entries():
            if len(v) > ci: chars.update(v[ci])
    chars.update(chr(c) for c in range(0x3041, 0x3097))
    chars.update(chr(c) for c in range(0x30a1, 0x30fb))
    chars.update('ー・、。「」『』（）！？：；…―〜＆％＋－＝／＊　')
    chars -= set('\r\n\t')
    chars = sorted(chars)
    open(os.path.join(B, 'chars.txt'), 'w', encoding='utf-8').write(''.join(chars))
    print('chars', len(chars))
    for dat, idx, kind, name, rel in fonts:
        if kind.startswith('fontjp:'):
            # the game's own Japanese font with our extra glyphs, sent as a delta against it
            j = int(kind.split(':')[1])
            src = [p for p in glob.glob(os.path.join(ROOT, game, 'orig', '%s__%d__*' % (dat, j)))][0]
            # its map points one glyph too far for every non-ASCII character: fix the map first
            import fixmap
            from ft2 import Ft2
            F = Ft2(open(src, 'rb').read())
            print('font map fixed:', fixmap.fix(F), 'entries')
            fixed = os.path.join(B, 'fixed_' + os.path.basename(src))
            open(fixed, 'wb').write(F.build())
            out = mkfont2.build(fixed, 'ft2', chars, os.path.join(B, name), game)
            dl = deltamod.bin_delta([(j, open(src, 'rb').read())], out)
            print(name, 'delta', dl.stats())
            built.append((dat, name, idx, os.path.getsize(os.path.join(ROOT, rel)), dl.encode()))
            continue
        out = mkfont2.build(os.path.join(ROOT, rel), 'fnt' if kind == 'fnt' else 'ft2', chars, os.path.join(B, name),
                            'hp' if grp == 'hp' else (game if game in mkfont2.STYLE else grp))
        built.append((dat, name, idx, os.path.getsize(os.path.join(ROOT, rel)), out))
    pack(built, os.path.join(B, 'pack.bin'), SETTINGS.get(game, ()))

if __name__ == '__main__':
    for g in sys.argv[1:]: main(g)
