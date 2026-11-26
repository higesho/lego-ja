# LEGO Batman 3's own Japanese font (font_jp_nxg.ft2) has a map whose glyph numbers are off by one for most
# characters (the PC version never used it). Rebuild the map by comparing every glyph image with the character
# drawn in a similar font, choosing among nearby glyph numbers.
import struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from dxt import decode_dxt5

REF = 'C:/Windows/Fonts/NotoSansJP-VF.ttf'

def norm(mask, size=24):
    ys, xs = np.where(mask > 100)
    if not len(xs): return None
    m = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    im = Image.fromarray(m.astype(np.uint8)).resize((size, size), Image.BILINEAR)
    v = np.asarray(im, np.float32).ravel()
    v -= v.mean(); n = np.linalg.norm(v)
    return v / n if n else None

def ref_mask(ch, f):
    im = Image.new('L', (80, 80), 0)
    ImageDraw.Draw(im).text((10, 60), ch, font=f, anchor='ls', fill=255)
    return np.asarray(im)

def fix(F, log=None):
    """The stored glyph number is one too high for every character outside ASCII (checked by eye against the
    atlas and with check() below); ASCII entries are right."""
    new, changed = [], 0
    for cp, g in F.map:
        k = g if cp < 0x80 or g == 0 else g - 1
        if k != g: changed += 1
        new.append((cp, k))
    F.map = new
    return changed

def check(F):
    """image-match score of every non-ASCII map entry against a reference font: list of (char, score) sorted"""
    h, w = struct.unpack_from('<II', F.dds, 12)
    a = decode_dxt5(F.dds[128:], w, h)
    H = int(F.height)
    f = ImageFont.truetype(REF, 40)
    try: f.set_variation_by_name('Bold')
    except Exception: f.set_variation_by_name(b'Bold')
    out = []
    for cp, g in F.map:
        ch = chr(cp)
        if cp < 0x80 or ch.isspace(): continue
        x, y, gw = F.glyphs[g]
        c = a[int(y):int(y) + H, int(x):int(x + gw)]
        v = norm(c[..., :3].mean(2) * (c[..., 3] / 255.0)) if gw > 0 else None
        r = norm(ref_mask(ch, f))
        out.append((ch, float(v @ r) if v is not None and r is not None else -1))
    return sorted(out, key=lambda e: e[1])
