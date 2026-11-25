# release/LEGOLOTR_JP.zip = dinput8.dll + 読んでください.txt + OFL.txt（中身は release/pkg に置く）
import os, zipfile, shutil
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
REL = os.path.join(ROOT, 'release')
PKG = os.path.join(REL, 'pkg')
dll = os.path.join(ROOT, 'build', 'dinput8.dll')   # 配布版（build.bat 引数なし）。試験版 build/test は入れない
if b'LOTRJP_TESTIO' in open(dll, 'rb').read(): raise SystemExit('試験版の DLL です')
shutil.copy(dll, os.path.join(PKG, 'dinput8.dll'))
out = os.path.join(REL, 'LEGOLOTR_JP.zip')
if os.path.exists(out): os.remove(out)
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in ('dinput8.dll', '読んでください.txt', 'OFL.txt'):
        z.write(os.path.join(PKG, f), f)
with zipfile.ZipFile(out) as z:
    for i in z.infolist(): print(i.filename, i.file_size, hex(i.flag_bits))
print(os.path.getsize(out), 'bytes')
