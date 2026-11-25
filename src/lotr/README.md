# LEGO ロード・オブ・ザ・リング 日本語化の組み立て

Steam 版 LEGO The Lord of the Rings を日本語にする `dinput8.dll` のソースと道具です。

## しくみ

- `dinput8.dll` はシステムの dinput8.dll にすべての関数を渡す代理の DLL です。
- ゲームが `GAME.DAT` を開いて索引を読んだとき、差し替えるファイル（`stuff\text\text.csv`、`gui\font\font_nxg.ft2`、`font_rus_nxg.ft2`）の項目を書き換え、
  ファイルの末尾より後ろの「ない場所」を指すようにします。ゲームがそこを読むと、DLL の中の日本語版のデータを返します。
- 差し替えるファイルの元の大きさが合わないときは差し替えません（英語のまま動きます）。
- text.csv は各言語の列をすべて日本語にします。フォントは元の字形を左上に残したまま、日本語の字形を足したテクスチャ（DXT5）に作り直します。

## ファイル

- `proxy.c` `lotrjp.c` `dat.c` … DLL 本体。`build.bat` で `../build/dinput8.dll`（配布版）を作ります。`build.bat test` は試験版（`testio.c` 入り、窓表示・入力の注入・画面の取得）です。
- `tools/ttdat.py` … GAME*.DAT の索引の読み取り
- `tools/tcsv.py` … text.csv の読み書き（元のバイト並びを保つ）
- `tools/ft2.py` `tools/dxt.py` `tools/mkfont.py` … フォント（.ft2）の読み書きと日本語の字形の追加
- `tools/mkpack.py` `tools/build_text.py` … 訳を当てて DLL に入れるデータ（LZMS 圧縮）を作る
- `tools/make_zip.py` … 配布物をまとめる
- `tools/win.py` … 試験版を起動して操作・画面を取る

必要なもの: Python 3（Pillow、NumPy）、Visual Studio（x86 の C コンパイラ）、Steam 版のゲームのファイル、訳の表、Noto Serif JP。
ゲームのファイルと訳の表はここには入っていないので各自用意してください。
