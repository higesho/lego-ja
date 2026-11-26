# TT Games DAT index (versions -3..-5).
#   header: u32 info offset (high bit: ((x^~0)<<8)+0x100), u32 info size
#   info: i32 ver, u32 n, n * (u32 off>>8, u32 zsize, u32 size, u32 flags[low byte = compression])
#         u32 cnt, cnt * (s16 next, s16 prev, u32 nameoff [, u32 hash for ver <= -5]), u32 poolsize, pool,
#         then n * u32 hash (sorted; entry i has hash[i])
#   Name records form a tree: a dir record has next = index of its last descendant record; children follow it.
#   Path hash: FNV-1a with prime 0x199933 over the uppercase path ("STUFF\\TEXT\\TEXT.CSV").
import struct

def tthash(path):
    h = 0x811c9dc5
    for c in path.upper().encode('latin1'):
        h ^= c; h = (h * 0x199933) & 0xffffffff
    return h

class Dat:
    def __init__(s, path):
        s.path = path; f = open(path, 'rb'); s.f = f
        off, sz = struct.unpack('<II', f.read(8))
        if off & 0x80000000: off = ((off ^ 0xffffffff) << 8) + 0x100
        s.info_off = off
        f.seek(off); info = f.read(sz); s.info = info
        s.ver, n = struct.unpack_from('<iI', info, 0)
        s.ents = [struct.unpack_from('<IIII', info, 8 + i * 16) for i in range(n)]
        p = 8 + n * 16
        cnt = struct.unpack_from('<I', info, p)[0]
        rs = 12 if s.ver <= -5 else 8
        s.recs = [struct.unpack_from('<hhI', info, p + 4 + i * rs) for i in range(cnt)]
        pe = p + 4 + cnt * rs
        poolsz = struct.unpack_from('<I', info, pe)[0]
        pool = pe + 4
        s.names = []
        for r in s.recs:
            e = info.index(b'\0', pool + r[2]); s.names.append(info[pool + r[2]:e].decode('latin1'))
        q = pool + poolsz
        s.hashes = list(struct.unpack_from('<%dI' % n, info, q)) if len(info) - q >= n * 4 else None
        # full paths
        paths = [''] * cnt; stack = [(0, s.recs[0][0])]
        for i in range(1, cnt):
            while len(stack) > 1 and i > stack[-1][1]: stack.pop()
            par = stack[-1][0]
            paths[i] = (paths[par] + '\\' if paths[par] else '') + s.names[i]
            if s.recs[i][0] > 0: stack.append((i, s.recs[i][0]))
        s.paths = {}   # entry index -> full path
        hidx = {h: i for i, h in enumerate(s.hashes)} if s.hashes else {}
        s.by_hash = bool(hidx) and s.ver >= -3
        for i in range(1, cnt):
            if s.recs[i][0] > 0: continue
            if s.by_hash:
                k = hidx.get(tthash(paths[i]))
                if k is None: continue
            else:
                k = -s.recs[i][0]
            s.paths[k] = paths[i] if s.ver >= -3 else s.names[i]
    def name(s, idx):
        p = s.paths.get(idx); return p.split('\\')[-1] if p else None
    def path_of(s, idx): return s.paths.get(idx)
    def find(s, path):
        for k, p in s.paths.items():
            if p.upper() == path.upper(): return k
    def entry(s, idx):
        o, z, u, fl = s.ents[idx]; return (o << 8), z, u, fl
    def raw(s, idx):
        o, z, u, fl = s.entry(idx); s.f.seek(o); return s.f.read(z)
