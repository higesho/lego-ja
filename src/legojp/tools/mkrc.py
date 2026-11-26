# python mkrc.py <game> <version>  -> src/rc/<game>.rc (pack resource + VERSIONINFO)
import sys, os
ROOT = os.path.dirname(os.path.abspath(__file__))
TITLES = {
    'hp1': ('LEGO ハリー・ポッター 第1章-4章', 'LEGOHP1_JP'),
    'hp2': ('LEGO ハリー・ポッター 第5章-7章', 'LEGOHP2_JP'),
    'marvel': ('LEGO マーベル スーパー・ヒーローズ', 'LEGOMARVEL_JP'),
    'sw': ('LEGO スター・ウォーズ コンプリート サーガ', 'LEGOSW_JP'),
    'bat1': ('LEGO バットマン ザ・ビデオゲーム', 'LEGOBAT1_JP'),
    'bat2': ('LEGO バットマン2 DC スーパーヒーローズ', 'LEGOBAT2_JP'),
    'bat3': ('LEGO バットマン3 ザ・ゲーム ゴッサムから宇宙へ', 'LEGOBAT3_JP'),
    'hobbit': ('LEGO ホビット', 'LEGOHOBBIT_JP'),
}
game, ver = sys.argv[1], sys.argv[2]
v = [int(x) for x in ver.split('.')] + [0] * (4 - len(ver.split('.')))
title, internal = TITLES[game]
rc = '''#pragma code_page(65001)
#include <winver.h>
1 LEGOJP "..\\\\%(game)s\\\\build\\\\pack.bin"

1 VERSIONINFO
FILEVERSION %(c)s
PRODUCTVERSION %(c)s
FILEOS 0x40004L
FILETYPE VFT_DLL
BEGIN
  BLOCK "StringFileInfo"
  BEGIN
    BLOCK "041104B0"
    BEGIN
      VALUE "CompanyName", "higesho"
      VALUE "ProductName", "%(title)s 日本語化パッチ（非公式）"
      VALUE "FileDescription", "%(title)s 日本語化パッチ（非公式）"
      VALUE "FileVersion", "%(d)s"
      VALUE "ProductVersion", "%(ver)s"
      VALUE "InternalName", "%(internal)s"
      VALUE "OriginalFilename", "dinput8.dll"
      VALUE "Comments", "https://higesho.github.io/lego-ja/%(game)s/"
    END
  END
  BLOCK "VarFileInfo"
  BEGIN
    VALUE "Translation", 0x0411, 1200
  END
END
''' % dict(game=game, c=','.join(map(str, v)), d='.'.join(map(str, v)), ver=ver, title=title, internal=internal)
os.makedirs(os.path.join(ROOT, 'src', 'rc'), exist_ok=True)
open(os.path.join(ROOT, 'src', 'rc', game + '.rc'), 'w', encoding='utf-8').write(rc)
print(rc.splitlines()[2])
