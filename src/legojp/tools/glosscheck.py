# python glosscheck.py <grp> : glossary names in the English text should appear in the Japanese text
import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
import build
ROOT = os.path.dirname(os.path.abspath(__file__))
grp = sys.argv[1]
tr, _, _ = build.load_map(grp)
pairs = []
for line in open(os.path.join(ROOT, 'text_' + grp, 'glossary.md'), encoding='utf-8'):
    m = re.match(r'^\| ([^|]+) \| ([^|]+) \|', line.strip())
    if not m or m.group(1).strip() in ('英語', '---'): continue
    ens = [e.strip() for e in m.group(1).split('/')]
    jas = [re.sub(r'（.*?）', '', j).strip() for j in m.group(2).split('/')]
    if len(ens) == len(jas):
        for e, j in zip(ens, jas):
            if len(e) > 3 and not e.islower() and j: pairs.append((e, j))
bad = {}
for en, ja in tr.items():
    for e, j in pairs:
        if re.search(r'\b' + re.escape(e) + r'\b', en) and j not in ja:
            bad.setdefault((e, j), []).append((en[:50], ja[:60]))
for (e, j), l in sorted(bad.items(), key=lambda x: -len(x[1])):
    print('%3d %s -> %s | %s => %s' % (len(l), e, j, l[0][0], l[0][1]))
