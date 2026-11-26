# Extract the original text/font files of each game into <game>/orig and collect the strings to translate.
#   python extract.py            -> marvel/ hp/ sw/ : orig/<DAT>__<index>__<name>, text/src/all.json
import json, os, sys, re
from ttdat2 import Dat
import lz2k
from textsrc import CsvSrc, LtxtSrc, PLAT_OK
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.abspath(__file__))
G = 'L:/SteamLibrary/steamapps/common/'

# game -> install dir, files the game reads (checked with LEGOJP_LOGREADS): (dat, index, kind)   kind: csv / csv1 (SW trc.csv) / ltxt / font / fnt
GAMES = {
    'marvel': ('LEGO Marvel Super Heroes', [
        ('GAME.DAT', 452, 'csv'), ('GAME.DAT', 5897, 'font')]),
    'hp1': ('LEGO Harry Potter', [
        ('GAME.DAT', 395, 'csv'), ('GAME.DAT', 5457, 'font')]),
    'hp2': ('LEGO Harry Potter Years 5-7', [
        ('GAME.DAT', 446, 'csv'), ('GAME.DAT', 6321, 'font')]),
    'sw': ('Lego Star Wars Saga', [
        ('GAME.DAT', 3593, 'ltxt'), ('GAME.DAT', 1789, 'csv1'),
        ('GAME.DAT', 11915, 'fnt')]),
}
# text groups translated together (shared glossary): hp1 + hp2 -> 'hp'
GROUP = {'marvel': 'marvel', 'hp1': 'hp', 'hp2': 'hp', 'sw': 'sw'}

def orig_name(dat, idx, name): return '%s__%d__%s' % (dat, idx, name)

def extract(game):
    inst, files = GAMES[game]
    od = os.path.join(ROOT, game, 'orig'); os.makedirs(od, exist_ok=True)
    out = []
    dats = {}
    for dat, idx, kind in files:
        D = dats.get(dat) or dats.setdefault(dat, Dat(G + inst + '/' + dat))
        o, z, u, fl = D.entry(idx)
        raw = D.raw(idx)
        if fl & 0xff == 2: raw = lz2k.decompress(raw)
        assert len(raw) == u, (game, dat, idx)
        name = D.name(idx).split('\\')[-1]
        p = os.path.join(od, orig_name(dat, idx, name))
        open(p, 'wb').write(raw)
        out.append((dat, idx, kind, name, p))
    return out

def strings(files):
    items = []
    for dat, idx, kind, name, p in files:
        raw = open(p, 'rb').read()
        if kind in ('csv', 'csv1'):
            s = CsvSrc(raw, 3 if kind == 'csv' else 1)
            for label, plat, typ, en, v in s.entries():
                if plat not in PLAT_OK: continue
                items.append({'label': label, 'type': typ or 'Text', 'en': en, 'file': name})
        elif kind == 'ltxt':
            s = LtxtSrc(raw)
            for i, num, sect, en in s.entries():
                items.append({'label': num, 'type': sect[:60], 'en': en, 'file': name})
    return items

def keep(en):
    t = en.strip()
    if not t or t == '¬': return False
    if not re.search(r'[A-Za-z]', re.sub(r'\[\[[^\]]*\]\]|\[[A-Z_]+\]|~\d|~~|%[sdi]', '', t)): return False
    return True

if __name__ == '__main__':
    groups = {}
    for g in GAMES:
        files = extract(g)
        json.dump([(d, i, k, n, os.path.relpath(p, ROOT)) for d, i, k, n, p in files], open(os.path.join(ROOT, g, 'files.json'), 'w'), indent=1)
        groups.setdefault(GROUP[g], []).extend(strings(files))
    for grp, items in groups.items():
        seen = {}; uniq = []
        for x in items:
            if not keep(x['en']) or x['en'] in seen: continue
            seen[x['en']] = 1; x['id'] = len(uniq); uniq.append(x)
        td = os.path.join(ROOT, 'text_' + grp, 'src'); os.makedirs(td, exist_ok=True)
        json.dump(uniq, open(os.path.join(td, 'all.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        words = sum(len(x['en'].split()) for x in uniq)
        print(grp, 'strings', len(uniq), 'words', words)
