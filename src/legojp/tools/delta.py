# Delta entries ("LJPD"): a file rebuilt by the DLL from entries of the game's own DAT plus our bytes
# (LEGO Batman 3: its own Japanese text and font are used without being copied into the patch).
#   "LJPD" u32 outlen, u8 nsrc, nsrc * (u32 index, u32 size), ops: 1 u8 src u32 off u32 len | 2 u32 len bytes | 0
import struct

class Delta:
    def __init__(self, sources):
        """sources: list of (dat index, bytes)"""
        self.src = sources
        self.ops = []          # ('c', s, off, len) / ('i', bytes)
        self.n = 0
    def copy(self, s, off, ln):
        if ln <= 0: return
        if self.ops and self.ops[-1][0] == 'c' and self.ops[-1][1] == s and self.ops[-1][2] + self.ops[-1][3] == off:
            o = self.ops[-1]; self.ops[-1] = ('c', s, o[2], o[3] + ln)
        else:
            self.ops.append(('c', s, off, ln))
        self.n += ln
    def ins(self, b):
        if not b: return
        if self.ops and self.ops[-1][0] == 'i':
            self.ops[-1] = ('i', self.ops[-1][1] + b)
        else:
            self.ops.append(('i', b))
        self.n += len(b)
    def apply(self):
        out = bytearray()
        for o in self.ops:
            if o[0] == 'c': out += self.src[o[1]][1][o[2]:o[2] + o[3]]
            else: out += o[1]
        return bytes(out)
    def encode(self):
        b = bytearray(b'LJPD' + struct.pack('<IB', self.n, len(self.src)))
        for idx, data in self.src: b += struct.pack('<II', idx, len(data))
        for o in self.ops:
            if o[0] == 'c': b += struct.pack('<BBII', 1, o[1], o[2], o[3])
            else: b += struct.pack('<BI', 2, len(o[1])) + o[1]
        b += b'\0'
        return bytes(b)
    def stats(self):
        ins = sum(len(o[1]) for o in self.ops if o[0] == 'i')
        return '%d ops, %d bytes ours, %d bytes copied' % (len(self.ops), ins, self.n - ins)

def csv_spans(raw):
    """TT text CSV (bytes, all fields quoted, no escaped quotes) -> list of ('rec', [(start, end) of each field's content]) / ('raw', (start, end))"""
    out = []
    i, n = 0, len(raw)
    while i < n:
        if raw[i] == 0x22:
            f = []
            while True:
                j = raw.index(b'"', i + 1)
                f.append((i + 1, j))
                i = j + 1
                if i + 1 < n and raw[i] == 0x2c and raw[i + 1] == 0x22:
                    i += 1; continue
                break
            out.append(('rec', f))
        else:
            k = i
            while True:
                k = raw.find(b'\n"', k)
                if k < 0: k = n; break
                k += 1; break
            if k == i: k = i + 1
            out.append(('raw', (i, k)))
            i = k
    return out

def csv_delta(idx, raw, choose):
    """Rebuild a text CSV. choose(rec_fields_text, col) -> None (keep the original field) / ('col', c) (copy the
    original field c of the same record) / ('text', str) (our text). raw must be UTF-8 (BOM allowed)."""
    d = Delta([(idx, raw)])
    for kind, v in csv_spans(raw):
        if kind == 'raw':
            d.copy(0, v[0], v[1] - v[0]); continue
        texts = [raw[a:b].decode('utf-8') for a, b in v]
        d.copy(0, v[0][0] - 1, 1)                      # opening quote
        for c, (a, b) in enumerate(v):
            ch = choose(texts, c)
            if ch is None: d.copy(0, a, b - a)
            elif ch[0] == 'col': d.copy(0, v[ch[1]][0], v[ch[1]][1] - v[ch[1]][0])
            else: d.ins(ch[1].encode('utf-8'))
            d.copy(0, b, 1)                            # closing quote
            if c + 1 < len(v): d.copy(0, b + 1, 2)     # ,"
    return d

def bin_delta(srcs, new, block=16, minrun=32):
    """Generic delta: copy every run of >= minrun bytes found in the sources (indexed at block-aligned offsets)."""
    d = Delta(srcs)
    index = {}
    for s, (idx, data) in enumerate(srcs):
        for p in range(0, len(data) - block + 1, block):
            index.setdefault(data[p:p + block], (s, p))
    i, n, lit = 0, len(new), bytearray()
    while i < n:
        hit = index.get(new[i:i + block]) if i + block <= n else None
        if hit:
            s, p = hit; data = srcs[s][1]
            # extend backwards into the pending literal and forwards
            back = 0
            while back < len(lit) and p - back - 1 >= 0 and data[p - back - 1] == lit[len(lit) - back - 1]: back += 1
            ln = block
            while i + ln < n and p + ln < len(data):
                step = min(4096, n - i - ln, len(data) - p - ln)
                if new[i + ln:i + ln + step] == data[p + ln:p + ln + step]: ln += step; continue
                while i + ln < n and p + ln < len(data) and new[i + ln] == data[p + ln]: ln += 1
                break
            if ln + back >= minrun:
                if back: del lit[len(lit) - back:]
                d.ins(bytes(lit)); lit = bytearray()
                d.copy(s, p - back, ln + back)
                i += ln
                continue
        lit.append(new[i]); i += 1
    d.ins(bytes(lit))
    assert d.apply() == new
    return d
