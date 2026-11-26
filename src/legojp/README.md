# LEGO シリーズ 日本語化の組み立て（ハリー・ポッター、スター・ウォーズ、マーベル）

Steam 版の LEGO Harry Potter: Years 1-4、Years 5-7、LEGO Star Wars: The Complete Saga、LEGO MARVEL Super Heroes を
日本語にする `dinput8.dll` のソースと道具です。4 作品で同じソースを使い、作品ごとに中に入れるデータだけが違います。

## しくみ

- `dinput8.dll` はシステムの dinput8.dll にすべての関数を渡す代理の DLL です。
- ゲームが `GAME.DAT` を開いて索引を読んだとき、差し替えるファイルの項目を書き換え、ファイルの末尾より後ろの「ない場所」を指すようにします。
  ゲームがそこを読むと、DLL の中の日本語版のデータを返します。差し替えるファイルの元の大きさが合わないときは差し替えません（英語のまま動きます）。
- 差し替えるファイル
  - ハリー・ポッター、マーベル: `text.csv`（各言語の列をすべて日本語にする）と `font_nxg.ft2`
  - スター・ウォーズ: `ENGLISH.TXT`、`TRC.CSV`、`STARWARS_FONT_PC.FNT`
- フォントは元の字形を左上に残したまま、日本語の字形を足したテクスチャ（DXT5）に作り直します。
  作ったあと、足した字形が元の字形と重なっていないこと、テクスチャから読み戻した字形が描いた字形と同じであること、
  文章に出てくる文字がすべてフォントにあることを確かめます（`tools/mkfont2.py` の verify）。
- ゲームは Windows の言語で文章の言語を選ぶので、言語を問い合わせる関数には常に英語（米国）と答えます。
  マーベルは日本語の Windows で起動直後に落ちますが、これで起きなくなります。
- スター・ウォーズだけの処理
  - フォントのテクスチャを作るときに大きさを 2MB に決め打ちしているので、その値を大きくします。
  - PC 版の設定メニューの言葉（映像設定、エフェクト設定など 39 語）は exe の中の表にあるので、英語の表を日本語の文字列に向け直します。
  - exe は起動してから展開されるので、どちらも最初に DAT ファイルを開いたときに行います。

## ファイル

- `proxy.c` `legojp.c` `dat.c` … DLL 本体。`build.bat <作品>`（hp1 / hp2 / sw / marvel）で配布版を作ります。
  `rc/<作品>.rc` は中に入れるデータと版の情報です。`build.bat test` は試験版（`testio.c` 入り、窓表示・入力の注入・画面の取得）で、
  データは環境変数 `LEGOJP_PACK` で渡します。
- `tools/ttdat2.py` `tools/lz2k.py` … GAME*.DAT の索引の読み取りと LZ2K の展開
- `tools/textsrc.py` `tools/tcsv.py` … 文章のファイル（CSV と番号付きテキスト）の読み書き（元のバイト並びを保つ）
- `tools/ft2.py` `tools/swfnt.py` `tools/dxt.py` `tools/mkfont2.py` … フォント（.ft2、スター・ウォーズの .FNT）の読み書きと日本語の字形の追加
- `tools/extract.py` … 元のファイルを取り出して訳す文章を集める
- `tools/build.py` … 訳を当て、フォントを作り、DLL に入れるデータ（LZMS 圧縮）を作る
- `tools/glosscheck.py` … 用語集どおりの訳になっているかを確かめる
- `tools/mkrc.py` `tools/mkrelease.py` … 版の情報と配布物を作る
- `tools/win.py` `tools/readnames.py` … 試験版を起動して操作・画面を取る、読まれたファイルを調べる

必要なもの: Python 3（Pillow、NumPy）、Visual Studio（x86 の C コンパイラ）、Steam 版のゲームのファイル、訳の表、Noto Serif JP / Noto Sans JP。
ゲームのファイルと訳の表はここには入っていないので各自用意してください。
