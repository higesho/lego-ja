# LZ2K (TT Games) decompressor: chunks of "LZ2K" u32 usize u32 zsize + LHA(ar002 lh5-style) static-Huffman data.
import struct

class BitReader:
    def __init__(s, data):
        s.d = data; s.pos = 0; s.buf = 0; s.n = 0
    def fill(s, need):
        while s.n < need:
            b = s.d[s.pos] if s.pos < len(s.d) else 0
            s.pos += 1
            s.buf = (s.buf << 8) | b; s.n += 8
    def peek(s, k):
        s.fill(k); return (s.buf >> (s.n - k)) & ((1 << k) - 1)
    def get(s, k):
        if k == 0: return 0
        v = s.peek(k); s.n -= k; s.buf &= (1 << s.n) - 1; return v

def make_table(lens):
    # returns dict-based decoder: (code_len -> {code: sym}) canonical like ar002 (codes assigned in symbol order by length)
    maxl = max(lens) if lens else 0
    count = [0] * 17
    for l in lens:
        if l: count[l] += 1
    start = [0] * 18
    for i in range(1, 17):
        start[i + 1] = (start[i] + (count[i] << (16 - i))) & 0x1ffff
    table = {}
    nxt = list(start)
    for sym, l in enumerate(lens):
        if not l: continue
        code = nxt[l] >> (16 - l)
        nxt[l] += 1 << (16 - l)
        table[(l, code)] = sym
    return table, maxl

def decode_sym(br, tab):
    table, maxl = tab
    if len(table) == 1 and maxl == 0:
        return next(iter(table.values()))
    for l in range(1, maxl + 1):
        code = br.peek(l)
        sym = table.get((l, code))
        if sym is not None:
            br.get(l); return sym
    raise ValueError('bad code')

def read_pt_len(br, nn, nbit, i_special):
    n = br.get(nbit)
    if n == 0:
        c = br.get(nbit)
        return None, c
    lens = [0] * nn
    i = 0
    while i < n:
        c = br.peek(3)
        if c == 7:
            br.get(3)
            while br.get(1): c += 1
        else:
            br.get(3)
        lens[i] = c; i += 1
        if i == i_special:
            c = br.get(2)
            for _ in range(c):
                lens[i] = 0; i += 1
    return lens, None

class Single:
    def __init__(s, v): s.v = v

def read_c_len(br, pt, NC=510, CBIT=9):
    n = br.get(CBIT)
    if n == 0:
        c = br.get(CBIT); return None, c
    lens = [0] * NC
    i = 0
    while i < n:
        c = pt_decode(br, pt)
        if c <= 2:
            if c == 0: c = 1
            elif c == 1: c = br.get(4) + 3
            else: c = br.get(CBIT) + 20
            for _ in range(c):
                lens[i] = 0; i += 1
        else:
            lens[i] = c - 2; i += 1
    return lens, None

def pt_decode(br, pt):
    if isinstance(pt, Single): return pt.v
    return decode_sym(br, pt)

def lh_decode(data, outsize, DICBIT=13):
    NP = DICBIT + 1; NT = 19; TBIT = 5; PBIT = 4 if DICBIT <= 13 else 5; THRESHOLD = 3
    br = BitReader(data)
    out = bytearray()
    blocksize = 0
    while len(out) < outsize:
        if blocksize == 0:
            blocksize = br.get(16)
            lens, single = read_pt_len(br, NT, TBIT, 3)
            pt = Single(single) if lens is None else make_table(lens)
            lens, single = read_c_len(br, pt)
            ct = Single(single) if lens is None else make_table(lens)
            lens, single = read_pt_len(br, NP, PBIT, -1)
            ptp = Single(single) if lens is None else make_table(lens)
        blocksize -= 1
        c = pt_decode(br, ct)
        if c < 256:
            out.append(c)
        else:
            ln = c - (256 - THRESHOLD)
            p = pt_decode(br, ptp)
            if p != 0: p = (1 << (p - 1)) + br.get(p - 1)
            src = len(out) - p - 1
            for k in range(ln):
                out.append(out[src + k])
    return bytes(out[:outsize])

def decompress(data, DICBIT=13):
    out = bytearray(); p = 0
    while p < len(data):
        if data[p:p + 4] != b'LZ2K': raise ValueError('no LZ2K at %d' % p)
        us, zs = struct.unpack_from('<II', data, p + 4)
        out += lh_decode(data[p + 12:p + 12 + zs], us, DICBIT)
        p += 12 + zs
    return bytes(out)
