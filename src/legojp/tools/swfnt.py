# LEGO Star Wars: The Complete Saga font (.FNT, little-endian, self-relative pointers + relocation trailer)
#   0x00 u32 trailer offset, 0x04 ptr -> 0x10 (font struct), 0x08 ptr -> DDS
#   0x18 u32 = DDS offset - 0x20 (= terminator offset of the map in the original), 0x1c u32 nglyph, 0x20 u32 nmap (+terminator)
#   0x24 f32 height, base, space ; 0x38..0x58 pointers (0x44 -> glyph table at 0x60, 0x48 -> map), others null
#   glyphs: nglyph * (f32 x, y, w) ; map: (u16 cp, u16 glyph) ... ffff ffff ; DDS ; trailer: u32 n, n * (target - own address)
import struct

PTRS = [4, 8, 0x38, 0x3c, 0x40, 0x44, 0x48, 0x4c, 0x50, 0x54, 0x58]
TI_PTRS = [0x1c, 0x28, 0x30, 0x3c, 0x4c]

class SwFnt:
    def __init__(self, d):
        self.head = bytearray(d[:0x60])
        T = struct.unpack_from('<I', d, 0)[0]
        n = struct.unpack_from('<I', d, T)[0]
        rel = [T + 4 + 4 * i + struct.unpack_from('<i', d, T + 4 + 4 * i)[0] for i in range(n)]
        # LEGO Batman: a 0x80-byte texture info block (w, h, ..., mips at +0x40, DDS size at +0x44, 5 null pointers)
        # sits between the map and the DDS; 0x18 = its offset - 0x20
        self.texinfo = None
        if len(rel) == len(PTRS) + len(TI_PTRS):
            ti = struct.unpack_from('<I', d, 0x18)[0] + 0x20
            assert rel == PTRS + [ti + o for o in TI_PTRS], rel
            self.texinfo = bytearray(d[ti:ti + 0x80])
        else:
            assert rel == PTRS, rel
        assert len(d) == T + 4 + 4 * n
        ng, nm = struct.unpack_from('<II', d, 0x1c)
        self.height, self.base, self.spacew = struct.unpack_from('<3f', d, 0x24)
        g0 = 0x44 + struct.unpack_from('<I', d, 0x44)[0]
        assert g0 == 0x60
        self.glyphs = [list(struct.unpack_from('<3f', d, g0 + 12 * i)) for i in range(ng)]
        m0 = 0x48 + struct.unpack_from('<I', d, 0x48)[0]
        self.map = [struct.unpack_from('<HH', d, m0 + 4 * i) for i in range(nm)]
        assert self.map[-1] == (0xffff, 0xffff)
        self.map = self.map[:-1]
        dd = 8 + struct.unpack_from('<I', d, 8)[0]
        assert d[dd:dd + 4] == b'DDS '
        if self.texinfo is None: assert struct.unpack_from('<I', d, 0x18)[0] == dd - 0x20
        else: assert dd == struct.unpack_from('<I', d, 0x18)[0] + 0x20 + 0x80
        self.dds = d[dd:T]

    def build(self):
        h = bytearray(self.head)
        gl = b''.join(struct.pack('<3f', *g) for g in self.glyphs)
        m = sorted(self.map, key=lambda e: e[0]) + [(0xffff, 0xffff)]
        mp = b''.join(struct.pack('<HH', *e) for e in m)
        gend = 0x60 + len(gl)
        # map start: 4-aligned, and (map end + 0x1c) 0x80-aligned so that DDS - 0x20 is the terminator offset, as in the original
        ms = gend
        if self.texinfo is None:
            while (ms + len(mp) + 0x1c) % 0x80: ms += 4
            dd = ms + len(mp) + 0x1c
            body = bytes(h) + gl + b'\0' * (ms - gend) + mp + b'\0' * 0x1c
            r18 = dd - 0x20
        else:
            ti = (ms + len(mp) + 0x7f) & ~0x7f
            dd = ti + 0x80
            t = bytearray(self.texinfo)
            hh, ww = struct.unpack_from('<II', self.dds, 12)
            struct.pack_into('<II', t, 0, ww, hh)
            struct.pack_into('<II', t, 0x40, struct.unpack_from('<I', self.dds, 28)[0], len(self.dds))
            body = bytes(h) + gl + mp + b'\0' * (ti - ms - len(mp)) + bytes(t)
            r18 = ti - 0x20
        assert len(body) == dd
        T = dd + len(self.dds)
        out = bytearray(body + self.dds)
        struct.pack_into('<I', out, 0, T)
        struct.pack_into('<I', out, 8, dd - 8)
        struct.pack_into('<III', out, 0x18, r18, len(self.glyphs), len(m))
        struct.pack_into('<3f', out, 0x24, self.height, self.base, self.spacew)
        struct.pack_into('<I', out, 0x44, 0x60 - 0x44)
        struct.pack_into('<I', out, 0x48, ms - 0x48)
        ptrs = PTRS + ([r18 + 0x20 + o for o in TI_PTRS] if self.texinfo is not None else [])
        out += struct.pack('<I', len(ptrs))
        for i, t in enumerate(ptrs):
            out += struct.pack('<i', t - (T + 4 + 4 * i))
        return bytes(out)

if __name__ == '__main__':
    import sys
    d = open(sys.argv[1], 'rb').read()
    f = SwFnt(d)
    b = f.build()
    print(len(d), len(b), b == d)
    if b != d:
        for i in range(min(len(b), len(d))):
            if b[i] != d[i]: print('first diff', hex(i)); break
