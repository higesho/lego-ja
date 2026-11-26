# TT Games NXG font (.ft2) read/write, versions 2 and 3 (big-endian)
#   u32 hdrsize (= DDS offset - 4), u32 1, 'TNFN', u32 ver, 6 zero bytes,
#   u32 x (some offset; kept as x - hdrsize), u32 nglyph, u32 nmap(+1 terminator), f32 height, f32 baseline, f32 spacew, 8 zero bytes,
#   [v3: 'ROTV'] u32 n, n*(f32 x, y, w), [v3: 'ROTV'] u32 n, n*(u16 cp, u16 glyph) (last = ffff ffff),
#   [v3: ROTV] u32 nkern, nkern*(u16 c1, u16 c2, f32 adjust), DDS
import struct

class Ft2:
    def __init__(self, data=None):
        if data is None: return
        d = data
        self.ver = struct.unpack_from('>I', d, 12)[0]
        hs = struct.unpack_from('>I', d, 0)[0]
        self.xdelta = struct.unpack_from('>I', d, 0x16)[0] - hs
        self.height, self.base, self.spacew = struct.unpack_from('>3f', d, 0x22)
        ng = struct.unpack_from('>I', d, 0x1a)[0]
        nm = struct.unpack_from('>I', d, 0x1e)[0]
        p = 0x36
        if self.ver >= 3:
            assert d[p:p + 4] == b'ROTV'; p += 4
        assert struct.unpack_from('>I', d, p)[0] == ng
        p += 4
        self.glyphs = [list(struct.unpack_from('>3f', d, p + i * 12)) for i in range(ng)]
        p += ng * 12
        if self.ver >= 3:
            assert d[p:p + 4] == b'ROTV'; p += 4
        assert struct.unpack_from('>I', d, p)[0] == nm
        p += 4
        self.map = [struct.unpack_from('>HH', d, p + i * 4) for i in range(nm)]
        assert self.map[-1] == (0xffff, 0xffff)
        self.map = self.map[:-1]
        p += nm * 4
        # kerning pairs: [v3: 'ROTV'] u32 n, n*(u16 c1, u16 c2, f32 adjust)
        if self.ver >= 3:
            assert d[p:p + 4] == b'ROTV'; p += 4
        nk = struct.unpack_from('>I', d, p)[0]; p += 4
        self.kern = [struct.unpack_from('>HHf', d, p + i * 8) for i in range(nk)]
        p += nk * 8
        assert p == hs + 4, (p, hs)
        assert d[p:p + 4] == b'DDS '
        self.dds = d[p:]

    def build(self):
        m = sorted(self.map, key=lambda e: e[0]) + [(0xffff, 0xffff)]   # stable: duplicate code points keep their order
        tag = b'ROTV' if self.ver >= 3 else b''
        body = tag + struct.pack('>I', len(self.glyphs)) + b''.join(struct.pack('>3f', *g) for g in self.glyphs)
        body += tag + struct.pack('>I', len(m)) + b''.join(struct.pack('>HH', *e) for e in m)
        body += tag + struct.pack('>I', len(self.kern)) + b''.join(struct.pack('>HHf', *k) for k in self.kern)
        hdrsize = 0x36 + len(body) - 4
        head = struct.pack('>II', hdrsize, 1) + b'TNFN' + struct.pack('>I', self.ver) + b'\0' * 6
        head += struct.pack('>III', hdrsize + self.xdelta, len(self.glyphs), len(m))
        head += struct.pack('>3f', self.height, self.base, self.spacew) + b'\0' * 8
        out = head + body + self.dds
        assert struct.unpack_from('>I', out, 0)[0] + 4 == len(head) + len(body)
        return out

def dds_header(w, h, mips, fourcc=b'DXT5'):
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000 | (0x20000 if mips > 1 else 0)
    linsize = max(1, w // 4) * max(1, h // 4) * 16
    hd = struct.pack('<7I', 124, flags, h, w, linsize, 0, mips) + b'\0' * 44
    hd += struct.pack('<2I4s5I', 32, 0x4, fourcc, 0, 0, 0, 0, 0)
    caps = 0x1000 | (0x400008 if mips > 1 else 0)
    hd += struct.pack('<5I', caps, 0, 0, 0, 0)
    return b'DDS ' + hd
