# Pack replacement files for the DLL: "LJPZ" u32 rawsize + LZMS("LJP1" u32 count + entries)
#   entry: u8 dat (0=GAME.DAT, 1=GAME0.DAT, ...), u8 namelen, name, u32 origsize, u32 len, data
import ctypes, struct, sys, os

def lzms(data):
    cab = ctypes.WinDLL('cabinet.dll')
    h = ctypes.c_void_p()
    if not cab.CreateCompressor(5, None, ctypes.byref(h)): raise OSError('CreateCompressor')
    need = ctypes.c_size_t()
    cab.Compress(h, data, ctypes.c_size_t(len(data)), None, ctypes.c_size_t(0), ctypes.byref(need))
    buf = ctypes.create_string_buffer(need.value)
    if not cab.Compress(h, data, ctypes.c_size_t(len(data)), buf, need, ctypes.byref(need)): raise OSError('Compress')
    cab.CloseCompressor(h)
    return buf.raw[:need.value]

def pack(entries, out):
    """entries: list of (dat, name, origsize, bytes)"""
    raw = b'LJP1' + struct.pack('<I', len(entries))
    for dat, name, osz, data in entries:
        n = name.encode('ascii')
        raw += struct.pack('<BB', dat, len(n)) + n + struct.pack('<II', osz, len(data)) + data
    z = lzms(raw)
    open(out, 'wb').write(b'LJPZ' + struct.pack('<I', len(raw)) + z)
    print(out, len(raw), '->', len(z) + 8)
