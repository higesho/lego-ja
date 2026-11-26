# Add Japanese glyphs to a LEGO font (ft2 v2/v3 or Star Wars .FNT).
# The original atlas stays in the top-left corner (old glyph coordinates stay valid, its mip 0 blocks are copied
# unchanged); new glyphs go into cells to the right of it and below it.
# After building, verify():
#   - every requested character is in the map
#   - no new glyph rectangle overlaps an original glyph or another new glyph, and all lie inside the texture
#   - the decoded mip 0 of every new glyph matches the rendered glyph (catches cut-off glyphs)
import struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ft2 import Ft2
from swfnt import SwFnt
from dxt import decode_dxt5, encode_dxt5, mip, pad4

FONTS = 'C:/Windows/Fonts/'
ZERO_W = {'\u200b', '\u2009', '\u200a'}     # invisible break-opportunity characters (1 px blank glyph)

# per game: font file, weight, em size, stroke, cell height, em-box top, outline colour, texture width
STYLE = {
    'hp':     dict(font='NotoSerifJP-VF.ttf', var='Bold',  size=32, stroke=3, cell=48, top=8,  outline=(0, 0, 0)),
    'marvel': dict(font='NotoSansJP-VF.ttf',  var='Black', size=56, stroke=5, cell=96, top=26, outline=(0, 0, 0)),
    'sw':     dict(font='NotoSansJP-VF.ttf',  var='Bold',  size=36, stroke=3, cell=48, top=5,  outline=(40, 40, 40)),
}

def render_glyphs(chars, st):
    f = ImageFont.truetype(FONTS + st['font'], st['size'])
    try: f.set_variation_by_name(st['var'])
    except Exception: f.set_variation_by_name(st['var'].encode())
    S, K, C = st['size'], st['stroke'], st['cell']
    out = {}
    for ch in chars:
        w = S + K * 2 + 4
        im = Image.new('RGBA', (w, C), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        base = st['top'] + S * 0.88
        d.text((K + 2, base), ch, font=f, anchor='ls', fill=(255, 255, 255, 255), stroke_width=K, stroke_fill=st['outline'] + (255,))
        a = np.array(im)
        assert a[0, :, 3].max() == 0 and a[-1, :, 3].max() == 0 or ch in '|｜', ('glyph touches the cell edge', ch)
        cols = np.where(a[..., 3].max(0) > 16)[0]
        if ch in ZERO_W:
            a = a[:, :1] * 0
        elif not len(cols):
            a = a[:, :S // 2]
        elif ord(ch) < 0x2000 or 0xff61 <= ord(ch) <= 0xff9f:
            a = a[:, cols.min():cols.max() + 1]
        else:
            l, r = max(0, cols.min() - 1), min(a.shape[1] - 1, cols.max() + 1)
            minw = int(S * 0.6) + K * 2
            while r - l + 1 < minw:
                if l > 0: l -= 1
                if r - l + 1 < minw and r < a.shape[1] - 1: r += 1
                if l == 0 and r == a.shape[1] - 1: break
            a = a[:, l:r + 1]
        out[ch] = a
    return out

def load(path, kind):
    d = open(path, 'rb').read()
    return SwFnt(d) if kind == 'fnt' else Ft2(d)

def dds_info(dds):
    h, w = struct.unpack_from('<II', dds, 12)
    mips = struct.unpack_from('<I', dds, 28)[0]
    return w, h, max(1, mips)

def level_sizes(w, h, n):
    out = []
    for i in range(n):
        out.append(max(1, w // 4) * max(1, h // 4) * 16)
        w, h = max(1, w // 2), max(1, h // 2)
    return out

def build(base_path, kind, chars, out_path, style, tex_w=4096):
    st = STYLE[style]
    C = st['cell']
    f = load(base_path, kind)
    hdr = f.dds[:128]
    ow, oh, omips = dds_info(f.dds)
    tail = f.dds[128 + sum(level_sizes(ow, oh, omips)):]      # bytes after the last mip level (kept)
    orig = decode_dxt5(f.dds[128:], ow, oh)
    have = {cp for cp, g in f.map}
    new = [c for c in chars if ord(c) not in have and ord(c) < 0xffff]
    gl = render_glyphs(new, st)
    pos = {}
    x, y = ow, 0
    for ch in new:
        w = gl[ch].shape[1]
        while x + w + 2 > tex_w:
            y += C
            x = ow
            if y + C > oh:
                y = max(y, oh)
                x = 0
        pos[ch] = (x, y)
        x += w + 2
    tex_h = max(512, oh)
    while tex_h < y + C: tex_h *= 2
    atlas = np.zeros((tex_h, tex_w, 4), np.uint8)
    atlas[:oh, :ow] = orig
    first_new = len(f.glyphs)
    for ch in new:
        px, py = pos[ch]; g = gl[ch]
        atlas[py:py + C, px:px + g.shape[1]] = g
        f.glyphs.append([float(px), float(py), float(g.shape[1])])
        f.map.append((ord(ch), len(f.glyphs) - 1))
    levels = [atlas]
    if omips > 1:
        while levels[-1].shape[0] > 1 or levels[-1].shape[1] > 1:
            levels.append(mip(levels[-1]))
    data = bytearray()
    for i, lv in enumerate(levels):
        enc = bytearray(encode_dxt5(pad4(lv)))
        if i == 0:
            bw = tex_w // 4; obw = ow // 4
            src = f.dds[128:128 + obw * (oh // 4) * 16]
            for by in range(oh // 4):
                enc[(by * bw) * 16:(by * bw + obw) * 16] = src[by * obw * 16:(by + 1) * obw * 16]
        data += enc
    h = bytearray(hdr)
    struct.pack_into('<II', h, 12, tex_h, tex_w)
    struct.pack_into('<I', h, 20, (tex_w // 4) * (tex_h // 4) * 16)
    struct.pack_into('<I', h, 28, len(levels) if omips > 1 else struct.unpack_from('<I', hdr, 28)[0])
    f.dds = bytes(h) + bytes(data) + tail
    out = f.build()
    open(out_path, 'wb').write(out)
    Image.fromarray(atlas, 'RGBA').save(out_path + '.png')
    print(out_path, len(new), 'new glyphs', tex_w, 'x', tex_h, 'mips', len(levels), len(out), 'bytes')
    verify(base_path, out_path, kind, chars, gl, first_new, C)
    return out

def verify(base_path, out_path, kind, chars, rendered, first_new, C):
    o = load(base_path, kind)
    f = load(out_path, kind)
    W, H, _ = dds_info(f.dds)
    a = decode_dxt5(f.dds[128:], W, H)
    m = dict(f.map)
    bad = 0
    miss = [c for c in chars if ord(c) not in m and c not in '\r\n\t']
    if miss: print('  MISSING in map:', ''.join(miss)); bad += len(miss)
    # original glyphs must be unchanged
    assert f.glyphs[:first_new] == o.glyphs, 'original glyph table changed'
    ow, oh, _ = dds_info(o.dds)
    oa = decode_dxt5(o.dds[128:], ow, oh)
    if not np.array_equal(a[:oh, :ow], oa): print('  original atlas area changed'); bad += 1
    # rectangles
    oh_cell = int(o.height)
    rects = [(int(x), int(y), int(x + w), int(y + oh_cell)) for x, y, w in o.glyphs if w > 0]
    news = []
    for cp, gi in f.map:
        if gi < first_new: continue
        x, y, w = f.glyphs[gi]
        r = (int(x), int(y), int(x + w), int(y + C))
        if r[2] > W or r[3] > H: print('  outside texture', chr(cp), r); bad += 1
        for q in rects:
            if r[0] < q[2] and q[0] < r[2] and r[1] < q[3] and q[1] < r[3]:
                print('  overlaps original glyph', chr(cp), r, q); bad += 1; break
        news.append((cp, r))
    news.sort(key=lambda e: (e[1][1], e[1][0]))
    for i in range(1, len(news)):
        p, q = news[i - 1][1], news[i][1]
        if p[1] == q[1] and p[2] > q[0]: print('  new glyphs overlap', chr(news[i - 1][0]), chr(news[i][0])); bad += 1
    # pixels
    worst = 0
    for cp, r in news:
        g = rendered.get(chr(cp))
        if g is None: continue
        got = a[r[1]:r[3], r[0]:r[2], 3].astype(int)
        exp = g[..., 3].astype(int)
        if got.shape != exp.shape: print('  size differs', chr(cp)); bad += 1; continue
        # compare 4x4-block means of alpha (DXT5 alpha error is small; a cut-off glyph differs a lot)
        diff = np.abs(got - exp)
        rowmax = diff.max(1)
        if (diff > 40).mean() > 0.01 or rowmax[:C // 3].max() > 96:
            print('  pixels differ', chr(cp), U(cp), 'bad px %.3f' % (diff > 40).mean()); bad += 1
        worst = max(worst, (diff > 40).mean())
    print('  verify: %d new glyphs, worst %.4f, %d problems' % (len(news), worst, bad))
    if bad: raise SystemExit('font verification failed: ' + out_path)

def U(cp): return 'U+%04X' % cp
