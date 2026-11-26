# Text sources of the LEGO games: read/write while keeping the original byte layout.
#   csv  : TT text CSV (UTF-8 or UTF-16, all fields quoted). Columns 3.. (or 1.. for SW trc.csv) are languages.
#   ltxt : numbered text file  `NUM [pc] "text" [comment]` (Star Wars TCS english.txt, HP english.txt)
import re, codecs
import tcsv

PLAT_OK = {'All', 'PC', 'None', ''}

class CsvSrc:
    """TT text CSV. first_lang = index of the first language column (3 normally, 1 for SW trc.csv)."""
    def __init__(self, raw, first_lang=3):
        self.raw = raw
        if raw.startswith(codecs.BOM_UTF16_LE):
            self.enc = 'utf-16'; s = raw.decode('utf-16')
        elif raw.startswith(codecs.BOM_UTF8):
            self.enc = 'utf-8-sig'; s = raw.decode('utf-8-sig')
        else:
            self.enc = 'utf-8'; s = raw.decode('utf-8')
        self.items = tcsv.parse(s)
        assert tcsv.build(self.items) == s
        self.first = first_lang
        recs = [v for k, v in self.items if k == 'rec']
        self.header = recs[0]
        self.ncol = len(self.header)
    def entries(self):
        """yield (label, platform, type, english, fields-list)"""
        for k, v in self.items:
            if k != 'rec' or v is self.header or len(v) <= self.first: continue
            if self.first == 3:
                yield v[0], v[1], v[2], v[3], v
            else:
                yield v[0], '', '', v[1], v
    def apply(self, tr):
        """tr(english, label, type) -> japanese or None. fills every language column."""
        n = 0
        for label, plat, typ, en, v in self.entries():
            ja = tr(en, label, typ)
            if ja is None: continue
            for c in range(self.first, len(v)): v[c] = ja
            n += 1
        return n
    def build(self):
        s = tcsv.build(self.items)
        if self.enc == 'utf-16': return codecs.BOM_UTF16_LE + s.encode('utf-16-le')
        if self.enc == 'utf-8-sig': return codecs.BOM_UTF8 + s.encode('utf-8')
        return s.encode('utf-8')

LT = re.compile(r'^(\s*)(\d+)(\s+(?:pc\s+)?)"([^"]*)"(.*)$')

class LtxtSrc:
    """numbered text file. keeps every byte outside the quoted text."""
    def __init__(self, raw, enc=None):
        self.raw = raw
        self.bom = raw.startswith(codecs.BOM_UTF8)
        if enc is None:
            try: raw.decode('utf-8-sig'); enc = 'utf-8'
            except UnicodeDecodeError: enc = 'latin-1'
        self.enc = enc
        s = raw.decode('utf-8-sig' if (self.bom and enc == 'utf-8') else enc)
        self.lines = s.split('\n')
    def entries(self):
        sect = ''
        for i, l in enumerate(self.lines):
            t = l.rstrip('\r')
            if t.lstrip().startswith(';'):
                c = t.lstrip(' \t;').strip()
                if c: sect = c
                continue
            m = LT.match(t)
            if m: yield i, m.group(2), sect, m.group(4)
    def apply(self, tr):
        n = 0
        for i, num, sect, en in list(self.entries()):
            ja = tr(en, num, sect)
            if ja is None: continue
            t = self.lines[i]; cr = t.endswith('\r'); t = t.rstrip('\r')
            m = LT.match(t)
            self.lines[i] = m.group(1) + m.group(2) + m.group(3) + '"' + ja + '"' + m.group(5) + ('\r' if cr else '')
            n += 1
        return n
    def build(self):
        s = '\n'.join(self.lines)
        b = s.encode('utf-8')
        return (codecs.BOM_UTF8 if self.bom else b'') + b
