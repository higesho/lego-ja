# TT Games NXG font (.ft2) read/write
#   u32be hdrsize (= DDS offset - 4), u32be 1, 'TNFN', u32be 3, 6 zero bytes,
#   u32be hdrsize+26, u32be nglyph, u32be nmap(+1 terminator), f32be height, f32be baseline, f32be spacew, 8 zero bytes,
#   'ROTV' u32be n, n*(f32be x, y, w), 'ROTV' u32be n, n*(u16be cp, u16be glyph) (last = ffff ffff),
#   'ROTV' u32be 0, DDS
import struct

class Ft2:
    def __init__(self, data=None):
        if data is None: return
        d = data
        self.height, self.base, self.spacew = struct.unpack_from('>3f', d, 0x22)
        ng = struct.unpack_from('>I', d, 0x1a)[0]
        nm = struct.unpack_from('>I', d, 0x1e)[0]
        p = 0x36
        assert d[p:p + 4] == b'ROTV'
        p += 8
        self.glyphs = [list(struct.unpack_from('>3f', d, p + i * 12)) for i in range(ng)]
        p += ng * 12
        assert d[p:p + 4] == b'ROTV'
        p += 8
        self.map = [struct.unpack_from('>HH', d, p + i * 4) for i in range(nm)]
        assert self.map[-1] == (0xffff, 0xffff)
        self.map = self.map[:-1]
        p += nm * 4
        assert d[p:p + 8] == b'ROTV\0\0\0\0'
        p += 8
        self.dds = d[p:]

    def build(self):
        m = sorted(self.map) + [(0xffff, 0xffff)]
        body = b'ROTV' + struct.pack('>I', len(self.glyphs)) + b''.join(struct.pack('>3f', *g) for g in self.glyphs)
        body += b'ROTV' + struct.pack('>I', len(m)) + b''.join(struct.pack('>HH', *e) for e in m)
        body += b'ROTV' + struct.pack('>I', 0)
        hdrsize = 0x36 + len(body) - 4
        head = struct.pack('>II', hdrsize, 1) + b'TNFN' + struct.pack('>I', 3) + b'\0' * 6
        head += struct.pack('>III', hdrsize + 26, len(self.glyphs), len(m))
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
