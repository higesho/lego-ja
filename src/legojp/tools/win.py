# Drive the test game through the DLL's shared memory (never the foreground window).
#   python win.py start            copy build/test/dinput8.dll (試験版: src/build.bat test) into the game, launch with LEGOJP_TEST=1 (game: work/game.txt or LEGOJP_GAME)
#   python win.py shot NAME [W]    back-buffer capture -> capture/NAME.png (optional width)
#   python win.py key K [K..]      tap keys (DIK names: enter esc space up down left right tab f1.. a..z 0..9)
#   python win.py hold K MS
#   python win.py move DX DY       relative mouse move (mickeys)
#   python win.py click [left|right]
#   python win.py lclick X Y | rclick X Y   move cursor (client coords) and click
#   python win.py wait MS
#   python win.py stop             kill the game, remove the DLL from the game folder
import sys, os, time, mmap, struct, subprocess, shutil, ctypes
ROOT = os.path.dirname(os.path.abspath(__file__))
C = 'L:/SteamLibrary/steamapps/common/'
# game -> (install dir, exe, steam appid)
GAMES = {'marvel': ('LEGO Marvel Super Heroes', 'LEGOMARVEL.exe', 249130),
         'hp1': ('LEGO Harry Potter', 'LEGOHarryPotter.exe', 21130),
         'hp2': ('LEGO Harry Potter Years 5-7', 'harry2.exe', 204120),
         'sw': ('Lego Star Wars Saga', 'LEGOStarWarsSaga.exe', 32440)}
GKEY = os.environ.get('LEGOJP_GAME') or open(os.path.join(ROOT, 'work', 'game.txt')).read().strip()
GAME = C + GAMES[GKEY][0]
PIDF = os.path.join(ROOT, 'work', 'pid.txt')
SHM_SIZE = 4384
O_WR, O_RD, O_CMD, O_REQ, O_DONE, O_PATH, O_FRAME, O_BUSY = 4, 8, 12, 4108, 4112, 4116, 4376, 4380

DIK = {'esc': 1, 'enter': 0x1c, 'space': 0x39, 'tab': 0x0f, 'back': 0x0e, 'up': 0xc8, 'down': 0xd0,
       'left': 0xcb, 'right': 0xcd, 'lshift': 0x2a, 'lctrl': 0x1d, 'lalt': 0x38, 'pgup': 0xc9, 'pgdn': 0xd1,
       'home': 0xc7, 'end': 0xcf, 'del': 0xd3, 'minus': 0x0c, 'equals': 0x0d}
for i, c in enumerate('1234567890'): DIK[c] = 2 + i
for row, start in (('qwertyuiop', 0x10), ('asdfghjkl', 0x1e), ('zxcvbnm', 0x2c)):
    for i, c in enumerate(row): DIK[c] = start + i
for i in range(10): DIK['f%d' % (i + 1)] = 0x3b + i
DIK['f11'] = 0x57; DIK['f12'] = 0x58

def shm():
    m = mmap.mmap(-1, SHM_SIZE, tagname='LEGOJP_TESTIO')
    if struct.unpack_from('<I', m, 0)[0] != 0x504a4c44:
        raise SystemExit('game (test DLL) not running')
    return m

def push(m, *cmds):
    for c in cmds:
        while True:
            wr, rd = struct.unpack_from('<ii', m, O_WR)
            if wr - rd < 250: break
            time.sleep(0.02)
        c = list(c) + [0] * (4 - len(c))
        struct.pack_into('<4i', m, O_CMD + (wr & 255) * 16, *c)
        struct.pack_into('<i', m, O_WR, wr + 1)

def settle(m, timeout=30):
    t = time.time()
    while time.time() - t < timeout:
        wr, rd = struct.unpack_from('<ii', m, O_WR)
        busy = struct.unpack_from('<i', m, O_BUSY)[0]
        if wr == rd and not busy: return
        time.sleep(0.03)

def frame(m): return struct.unpack_from('<i', m, O_FRAME)[0]

def tap(m, k, hold=60, gap=80):
    code = DIK[k] if k in DIK else int(k, 0)
    push(m, (1, code), (6, hold), (2, code), (6, gap))

def shot(name, width=None):
    from PIL import Image
    m = shm()
    settle(m)
    bmp = os.path.join(ROOT, 'work', 'shot.bmp')
    os.makedirs(os.path.join(ROOT, GKEY, 'capture'), exist_ok=True)
    if os.path.exists(bmp): os.remove(bmp)
    p = bmp.encode('mbcs') + b'\0'
    m[O_PATH:O_PATH + len(p)] = p
    req = struct.unpack_from('<i', m, O_REQ)[0] + 1
    struct.pack_into('<i', m, O_REQ, req)
    t = time.time()
    while struct.unpack_from('<i', m, O_DONE)[0] != req:
        if time.time() - t > 15: raise SystemExit('shot timeout (game paused/minimized?)')
        time.sleep(0.05)
    im = Image.open(bmp).convert('RGB')
    if width: im = im.resize((int(width), int(im.height * int(width) / im.width)), Image.LANCZOS)
    out = os.path.join(ROOT, GKEY, 'capture', name + '.png')
    im.save(out)
    print(out, im.size)

def start():
    exe = os.path.join(GAME, GAMES[GKEY][1])
    if os.path.exists(os.path.join(GAME, 'dinput8.dll')) and not os.path.exists(os.path.join(ROOT, 'work', 'dll_is_ours')):
        raise SystemExit('dinput8.dll already in the game folder (not ours)')
    rel = 'rel' in sys.argv[2:]     # rel: 配布版 <game>/build/dinput8.dll で起動（試験機能なし）
    shutil.copy(os.path.join(ROOT, GKEY, 'build', 'dinput8.dll') if rel else os.path.join(ROOT, 'build', 'test', 'dinput8.dll'), os.path.join(GAME, 'dinput8.dll'))
    open(os.path.join(ROOT, 'work', 'dll_is_ours'), 'w').write(GKEY)
    open(os.path.join(GAME, 'steam_appid.txt'), 'w').write(str(GAMES[GKEY][2]))   # 直接起動用（stop で消す）
    env = dict(os.environ)
    env['LEGOJP_TEST'] = '1'
    env['LEGOJP_LOG'] = os.path.join(ROOT, 'work', 'log.txt')
    pk = os.path.join(ROOT, GKEY, 'build', 'pack.bin')
    if os.path.exists(pk) and 'nopack' not in sys.argv: env['LEGOJP_PACK'] = pk
    args = []
    for a in sys.argv[2:]:
        if '=' in a:
            k, v = a.split('=', 1); env[k] = v
        elif a not in ('nopack', 'rel'): args.append(a)
    p = subprocess.Popen([exe] + args, cwd=GAME, env=env)
    open(PIDF, 'w').write(str(p.pid))
    print('pid', p.pid)

def stop():
    try:
        pid = int(open(PIDF).read())
        subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True)
    except Exception as e:
        print(e)
    time.sleep(1)
    for f in ('dinput8.dll', 'steam_appid.txt'):
        try: os.remove(os.path.join(GAME, f))
        except OSError as e: print(e)
    try: os.remove(os.path.join(ROOT, 'work', 'dll_is_ours'))
    except OSError: pass

def game_hwnd():
    import ctypes.wintypes as W
    u = ctypes.windll.user32
    pid = int(open(PIDF).read())
    hw = []
    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def cb(h, l):
        p = W.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(p))
        b = ctypes.create_unicode_buffer(64); u.GetWindowTextW(h, b, 64)
        if p.value == pid and u.IsWindowVisible(h) and 'LEGO' in b.value.upper(): hw.append(h)
        return True
    u.EnumWindows(cb, 0)
    if not hw: raise SystemExit('game window not found')
    return hw[0]

def mouse_to(x, y):
    """cursor position comes from WM_MOUSEMOVE (client coords = 1280x1024 virtual)"""
    h = game_hwnd()
    for k in range(3):
        ctypes.windll.user32.PostMessageW(h, 0x200, 0, (int(y) << 16) | (int(x) & 0xffff))
        time.sleep(0.05)

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    c = a[0]
    if c == 'start': start()
    elif c == 'stop': stop()
    elif c == 'shot': shot(a[1], a[2] if len(a) > 2 else None)
    elif c == 'key':
        m = shm()
        for k in a[1:]: tap(m, k)
        settle(m)
    elif c == 'hold':
        m = shm(); code = DIK[a[1]]
        push(m, (1, code), (6, int(a[2])), (2, code), (6, 60)); settle(m)
    elif c == 'move':
        m = shm(); push(m, (3, int(a[1]), int(a[2])), (6, 40)); settle(m)
    elif c == 'click':
        m = shm(); b = 1 if (len(a) > 1 and a[1] == 'right') else 0
        push(m, (4, b), (6, 60), (5, b), (6, 80)); settle(m)
    elif c == 'mouse':
        mouse_to(a[1], a[2]); time.sleep(0.2)
    elif c == 'lclick' or c == 'rclick':
        mouse_to(a[1], a[2]); time.sleep(0.2)
        m = shm(); b = 1 if c == 'rclick' else 0
        push(m, (4, b), (6, 80), (5, b), (6, 150)); settle(m)
    elif c == 'type':
        # text entry uses WM_KEYDOWN (virtual key codes)
        h = game_hwnd()
        for ch in ' '.join(a[1:]):
            vk = ctypes.windll.user32.VkKeyScanW(ord(ch)) & 0xff
            ctypes.windll.user32.PostMessageW(h, 0x100, vk, 1)
            time.sleep(0.08)
            ctypes.windll.user32.PostMessageW(h, 0x101, vk, 0xc0000001)
            time.sleep(0.08)
    elif c == 'vk':
        h = game_hwnd()
        for k in a[1:]:
            vk = int(k, 0)
            ctypes.windll.user32.PostMessageW(h, 0x100, vk, 1); time.sleep(0.08)
            ctypes.windll.user32.PostMessageW(h, 0x101, vk, 0xc0000001); time.sleep(0.08)
    elif c == 'wait':
        m = shm(); push(m, (6, int(a[1]))); settle(m)
    elif c == 'frame':
        print(frame(shm()))
    else: print(__doc__)

if __name__ == '__main__':
    main()
