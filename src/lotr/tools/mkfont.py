# Build Japanese ft2 fonts: keep the original atlas in the top-left corner (old glyph coordinates stay valid)
# and add one 48px cell per Japanese character, white fill + black outline like the original glyphs.
#   python tools/mkfont.py chars.txt out_dir
import sys, os, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
from ft2 import Ft2
from dxt import decode_dxt5, encode_dxt5, mip, pad4

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FONT = 'C:/Windows/Fonts/NotoSerifJP-VF.ttf'
SIZE = 31          # em size in px
STROKE = 3
CELL_H = 48
TOP = 9            # y of the em box top inside the 48px cell (Latin caps span 14..39)
ADV_PAD = 0        # extra advance

def render_glyphs(chars):
    f = ImageFont.truetype(FONT, SIZE)
    f.set_variation_by_name('Bold')
    out = {}
    for ch in chars:
        w = SIZE + STROKE * 2 + 2
        im = Image.new('RGBA', (w, CELL_H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        # draw with the em box top at TOP: anchor 'lt' uses the ascender line, so use font metrics
        asc, desc = f.getmetrics()
        bb = f.getbbox(ch, anchor='ls')
        # baseline position so that the em box (ascender-descender scaled to SIZE) starts at TOP
        base = TOP + SIZE * 0.88
        x = STROKE + 1
        if ch in '、。，．': pass
        d.text((x, base), ch, font=f, anchor='ls', fill=(255, 255, 255, 255), stroke_width=STROKE, stroke_fill=(0, 0, 0, 255))
        a = np.array(im)
        # advance = ink width (the game adds its own letter spacing after every glyph, like the Latin glyphs)
        cols = np.where(a[..., 3].max(0) > 16)[0]
        if not len(cols):
            a = a[:, :SIZE // 2]
        elif ord(ch) < 0x2000 or 0xff61 <= ord(ch) <= 0xff9f:
            a = a[:, cols.min():cols.max() + 1]
        else:
            l, r = max(0, cols.min() - 1), min(a.shape[1] - 1, cols.max() + 1)
            minw = int(SIZE * 0.6) + STROKE * 2
            while r - l + 1 < minw:
                if l > 0: l -= 1
                if r - l + 1 < minw and r < a.shape[1] - 1: r += 1
                if l == 0 and r == a.shape[1] - 1: break
            a = a[:, l:r + 1]
        out[ch] = a
    return out

def build(base_path, chars, out_path, tex_w=4096):
    d = open(base_path, 'rb').read()
    f = Ft2(d)
    hdr = f.dds[:128]
    ow, oh = struct.unpack_from('<I', hdr, 16)[0], struct.unpack_from('<I', hdr, 12)[0]
    orig = decode_dxt5(f.dds[128:], ow, oh)
    have = {cp for cp, g in f.map}
    chars = [c for c in chars if ord(c) not in have and ord(c) < 0xffff]
    gl = render_glyphs(chars)
    # layout: rows of CELL_H; to the right of the original atlas first, then below it
    pos = {}
    x, y = ow, 0
    for ch in chars:
        w = gl[ch].shape[1]
        limit_x = tex_w
        if x + w + 2 > limit_x:
            y += CELL_H
            x = ow
            if y + CELL_H > oh:
                # below the original atlas: the full width is free. Never start a row that dips into
                # the original atlas area (its mip 0 blocks are restored from the original file).
                y = max(y, oh)
                x = 0
        pos[ch] = (x, y)
        x += w + 2
    tex_h = max(512, oh)
    while tex_h < y + CELL_H: tex_h *= 2
    atlas = np.zeros((tex_h, tex_w, 4), np.uint8)
    atlas[:oh, :ow] = orig
    for ch in chars:
        px, py = pos[ch]; g = gl[ch]
        atlas[py:py + CELL_H, px:px + g.shape[1]] = g
        f.glyphs.append([float(px), float(py), float(g.shape[1] + ADV_PAD)])
        f.map.append((ord(ch), len(f.glyphs) - 1))
    # DDS with full mip chain; mip 0 keeps the original compressed blocks
    levels = []
    im = atlas
    while True:
        levels.append(im)
        if im.shape[0] == 1 and im.shape[1] == 1: break
        im = mip(im)
    data = bytearray()
    for i, lv in enumerate(levels):
        enc = bytearray(encode_dxt5(pad4(lv)))
        if i == 0:
            bw = tex_w // 4; obw = ow // 4
            src = f.dds[128:128 + (ow // 4) * (oh // 4) * 16]
            for by in range(oh // 4):
                enc[(by * bw) * 16:(by * bw + obw) * 16] = src[by * obw * 16:(by + 1) * obw * 16]
        data += enc
    h = bytearray(hdr)
    struct.pack_into('<I', h, 12, tex_h); struct.pack_into('<I', h, 16, tex_w)
    struct.pack_into('<I', h, 20, (tex_w // 4) * (tex_h // 4) * 16); struct.pack_into('<I', h, 28, len(levels))
    f.dds = bytes(h) + bytes(data)
    open(out_path, 'wb').write(f.build())
    Image.fromarray(atlas, 'RGBA').save(out_path + '.png')
    print(out_path, len(chars), 'new glyphs', tex_w, 'x', tex_h)

if __name__ == '__main__':
    chars = sorted(set(open(sys.argv[1], encoding='utf-8').read()) - set('\r\n'))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    build(os.path.join(ROOT, 'orig', 'font_nxg.ft2'), chars, os.path.join(out, 'font_nxg.ft2'))
    build(os.path.join(ROOT, 'orig', 'font_rus_nxg.ft2'), chars, os.path.join(out, 'font_rus_nxg.ft2'))
