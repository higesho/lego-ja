import numpy as np
def dec565(c):
    r=((c>>11)&31)*255//31; g=((c>>5)&63)*255//63; b=(c&31)*255//31
    return np.stack([r,g,b],-1).astype(np.int32)
def decode_dxt5(data,w,h):
    bw,bh=w//4,h//4
    a=np.frombuffer(data,dtype=np.uint8,count=bw*bh*16).reshape(bh,bw,16)
    a0=a[...,0].astype(np.int32); a1=a[...,1].astype(np.int32)
    bits=np.zeros((bh,bw),dtype=np.uint64)
    for i in range(6): bits|=a[...,2+i].astype(np.uint64)<<np.uint64(8*i)
    lut=np.zeros((bh,bw,8),np.int32); lut[...,0]=a0; lut[...,1]=a1
    big=a0>a1
    for i in range(1,7):
        lut[...,1+i]=np.where(big,((7-i)*a0+i*a1)//7, lut[...,1+i])
    for i in range(1,5):
        lut[...,1+i]=np.where(~big,((5-i)*a0+i*a1)//5,lut[...,1+i])
    lut[...,6]=np.where(~big,0,lut[...,6]); lut[...,7]=np.where(~big,255,lut[...,7])
    alpha=np.zeros((bh,bw,16),np.int32)
    for p in range(16):
        idx=((bits>>np.uint64(3*p))&np.uint64(7)).astype(np.int64)
        alpha[...,p]=np.take_along_axis(lut,idx[...,None],-1)[...,0]
    c0=a[...,8].astype(np.int32)|(a[...,9].astype(np.int32)<<8); c1=a[...,10].astype(np.int32)|(a[...,11].astype(np.int32)<<8)
    col0=dec565(c0); col1=dec565(c1)
    pal=np.stack([col0,col1,(2*col0+col1)//3,(col0+2*col1)//3],2)
    ci=a[...,12].astype(np.uint32)|(a[...,13].astype(np.uint32)<<8)|(a[...,14].astype(np.uint32)<<16)|(a[...,15].astype(np.uint32)<<24)
    rgb=np.zeros((bh,bw,16,3),np.int32)
    for p in range(16):
        idx=((ci>>(2*p))&3).astype(np.int64)
        rgb[...,p,:]=np.take_along_axis(pal,idx[...,None,None].repeat(3,-1),2)[...,0,:]
    out=np.zeros((h,w,4),np.uint8)
    rgb=rgb.reshape(bh,bw,4,4,3).transpose(0,2,1,3,4).reshape(h,w,3)
    alpha=alpha.reshape(bh,bw,4,4).transpose(0,2,1,3).reshape(h,w)
    out[...,:3]=rgb; out[...,3]=alpha
    return out
def encode_dxt5_alpha(alpha, rgb=(255,255,255)):
    """alpha: HxW uint8, colour constant"""
    h,w=alpha.shape; bh,bw=h//4,w//4
    A=alpha.reshape(bh,4,bw,4).transpose(0,2,1,3).reshape(bh,bw,16).astype(np.int32)
    a0=A.max(-1); a1=A.min(-1)
    out=np.zeros((bh,bw,16),np.uint8)
    # 8-level mode a0>a1 ; if equal, all idx 0
    rng=np.maximum(a0-a1,1)
    t=((a0[...,None]-A)*7+rng[...,None]//2)//rng[...,None]   # 0..7, 0=a0 7=a1
    # map t -> index: 0->0, 7->1, i->i+1
    idx=np.where(t==0,0,np.where(t==7,1,t+1)).astype(np.uint64)
    idx=np.where((a0==a1)[...,None],0,idx).astype(np.uint64)
    bits=np.zeros((bh,bw),np.uint64)
    for p in range(16): bits|=idx[...,p]<<np.uint64(3*p)
    out[...,0]=a0; out[...,1]=a1
    for i in range(6): out[...,2+i]=((bits>>np.uint64(8*i))&np.uint64(255)).astype(np.uint8)
    r,g,b=rgb; c=((r*31//255)<<11)|((g*63//255)<<5)|(b*31//255)
    out[...,8]=c&255; out[...,9]=c>>8; out[...,10]=c&255; out[...,11]=c>>8
    return out.tobytes()

def encode_dxt5(rgba):
    """rgba: HxWx4 uint8 -> DXT5 bytes (simple min/max encoder, fine for grey glyphs)"""
    h, w = rgba.shape[:2]; bh, bw = h // 4, w // 4
    B = rgba.reshape(bh, 4, bw, 4, 4).transpose(0, 2, 1, 3, 4).reshape(bh, bw, 16, 4).astype(np.int32)
    A = B[..., 3]
    out = np.zeros((bh, bw, 16), np.uint8)
    a0 = A.max(-1); a1 = A.min(-1)
    rng = np.maximum(a0 - a1, 1)
    t = ((a0[..., None] - A) * 7 + rng[..., None] // 2) // rng[..., None]
    idx = np.where(t == 0, 0, np.where(t == 7, 1, t + 1))
    idx = np.where((a0 == a1)[..., None], 0, idx).astype(np.uint64)
    bits = np.zeros((bh, bw), np.uint64)
    for p in range(16): bits |= idx[..., p] << np.uint64(3 * p)
    out[..., 0] = a0; out[..., 1] = a1
    for i in range(6): out[..., 2 + i] = ((bits >> np.uint64(8 * i)) & np.uint64(255)).astype(np.uint8)
    rgb = B[..., :3]
    lum = rgb[..., 0] * 3 + rgb[..., 1] * 6 + rgb[..., 2]
    lum = np.where(A > 8, lum, -1)
    imax = lum.argmax(-1); lmin = np.where(A > 8, lum, 1 << 20); imin = lmin.argmin(-1)
    cmax = np.take_along_axis(rgb, imax[..., None, None].repeat(3, -1), 2)[..., 0, :]
    cmin = np.take_along_axis(rgb, imin[..., None, None].repeat(3, -1), 2)[..., 0, :]
    def q(c): return ((c[..., 0] * 31 + 127) // 255 << 11) | ((c[..., 1] * 63 + 127) // 255 << 5) | ((c[..., 2] * 31 + 127) // 255)
    q0 = q(cmax); q1 = q(cmin)
    # ensure c0 > c1 for 4-colour mode
    sw = q0 < q1
    q0, q1 = np.where(sw, q1, q0), np.where(sw, q0, q1)
    c0 = dec565(q0); c1 = dec565(q1)
    pal = np.stack([c0, c1, (2 * c0 + c1) // 3, (c0 + 2 * c1) // 3], 2)  # bh,bw,4,3
    dist = ((rgb[..., None, :] - pal[:, :, None, :, :]) ** 2).sum(-1)    # bh,bw,16,4
    ci = dist.argmin(-1)
    ci = np.where((q0 == q1)[..., None], 0, ci).astype(np.uint32)
    word = np.zeros((bh, bw), np.uint32)
    for p in range(16): word |= ci[..., p] << np.uint32(2 * p)
    out[..., 8] = q0 & 255; out[..., 9] = q0 >> 8; out[..., 10] = q1 & 255; out[..., 11] = q1 >> 8
    for i in range(4): out[..., 12 + i] = (word >> np.uint32(8 * i)) & 255
    return out.tobytes()

def mip(rgba):
    h, w = rgba.shape[:2]
    if h == 1 and w == 1: return rgba
    r = rgba.astype(np.uint32)
    if h > 1 and w > 1: r = (r[0::2, 0::2] + r[1::2, 0::2] + r[0::2, 1::2] + r[1::2, 1::2] + 2) // 4
    elif h > 1: r = (r[0::2] + r[1::2] + 1) // 2
    else: r = (r[:, 0::2] + r[:, 1::2] + 1) // 2
    return r.astype(np.uint8)

def pad4(rgba):
    h, w = rgba.shape[:2]
    if h >= 4 and w >= 4: return rgba
    o = np.zeros((max(4, h), max(4, w), 4), np.uint8); o[:h, :w] = rgba; return o
