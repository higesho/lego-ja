# python mkrelease.py <game> <version> <date>  -> release/<ZIP>.zip (dinput8.dll + 読んでください.txt + OFL.txt)
import sys, os, zipfile, shutil
ROOT = os.path.dirname(os.path.abspath(__file__))
LOTR_OFL = os.path.join(ROOT, 'OFL.txt')   # SIL OFL 1.1 の本文（先頭の説明は書き換える）

G = {
 'hp1': dict(
    name='LEGO ハリー・ポッター 第1章-4章', steam='LEGO® Harry Potter: Years 1-4', exe='LEGOHarryPotter.exe', zip='LEGOHP1_JP',
    font='Noto Serif JP', fontweight='Bold',
    what='ゲーム中のヒント、ホグワーツやダイアゴン横丁の案内、呪文やキャラクター・アイテムの名前、\nメニューや設定の画面まで、ゲームの中の文章を日本語にしています。\nこのゲームのせりふは声のない身ぶりなので、字幕はありません。',
    subs=None,
    tm='Harry Potter と関連する名前は Warner Bros. Entertainment Inc. の商標です。'),
 'hp2': dict(
    name='LEGO ハリー・ポッター 第5章-7章', steam='LEGO® Harry Potter: Years 5-7', exe='harry2.exe', zip='LEGOHP2_JP',
    font='Noto Serif JP', fontweight='Bold',
    what='ゲーム中のヒント、ホグワーツやダイアゴン横丁の案内、呪文やキャラクター・アイテムの名前、\nメニューや設定の画面まで、ゲームの中の文章を日本語にしています。',
    subs=None,
    tm='Harry Potter と関連する名前は Warner Bros. Entertainment Inc. の商標です。'),
 'marvel': dict(
    name='LEGO マーベル スーパー・ヒーローズ', steam='LEGO® MARVEL Super Heroes', exe='LEGOMARVEL.exe', zip='LEGOMARVEL_JP',
    font='Noto Sans JP', fontweight='Black',
    what='ムービーとゲーム中の字幕、ヒント、ニューヨークの人々の頼みごと、キャラクターやアイテムの名前、\nメニューや設定の画面まで、ゲームの中の文章を日本語にしています。\n声は英語のままで、字幕が日本語で出ます。',
    subs='字幕は最初はオフになっています。タイトルの「オプション」で「字幕」を「オン」にしてください。',
    extra='・日本語の Windows でこのゲームが起動直後に落ちる問題も、このパッチで起きなくなります。\n',
    tm='MARVEL と関連する名前は MARVEL の商標です。'),
 'sw': dict(
    name='LEGO スター・ウォーズ コンプリート サーガ', steam='LEGO® Star Wars™: The Complete Saga', exe='LEGOStarWarsSaga.exe', zip='LEGOSW_JP',
    font='Noto Sans JP', fontweight='Bold',
    what='ゲーム中のヒント、レベルやキャラクター・乗り物の名前、エクストラやショップ、\nメニューや設定の画面（映像設定・エフェクト設定を含む）まで、ゲームの中の文章を日本語にしています。',
    subs=None,
    tm='STAR WARS と関連する名前は Lucasfilm Ltd. の商標です。'),
}

def readme(g, ver, date, history):
    d = G[g]
    steps = ['この zip の中の dinput8.dll を、ゲームのフォルダ（%s があるフォルダ）に置きます。\n   Steam のライブラリでゲームを右クリック →「管理」→「ローカルファイルを閲覧」で開けます。' % d['exe'],
             'いつもどおり Steam から起動します。']
    if d['subs']: steps.append(d['subs'])
    title = '%s 日本語化パッチ v%s' % (d['name'], ver)
    s = '%s\n%s\n\n' % (title, '=' * min(70, len(title.encode('cp932'))))
    s += 'Steam 版「%s」（PC）を日本語で遊べるようにする、非公式のファンメイド日本語化パッチです。\n開発元・販売元とは関係ありません。\n\n' % d['steam']
    s += d['what'] + '\n\n'
    s += '■ 入れ方\n' + ''.join('%d. %s\n' % (i + 1, t) for i, t in enumerate(steps)) + '\n'
    s += '■ 外し方\nゲームのフォルダから dinput8.dll を消せば、英語版に戻ります。\nゲームのファイルは書き換えません。\n\n'
    s += '■ 遊ぶときの注意\n'
    s += '・Steam の言語設定や Windows の言語にかかわらず、日本語で表示されます。\n'
    s += '・セーブデータは英語版と共通です。パッチを入れたり外したりしても続きから遊べます。\n'
    s += d.get('extra', '')
    s += '・タイトルのロゴ、絵として描かれた文字、スタッフクレジットは英語のままです。\n'
    s += '・キーの名前（Enter、Backspace など）やエクストラのコード入力の文字は英語のままです。\n'
    s += '・ゲームのファイルが Steam 版と違うとき（ほかの MOD で GAME.DAT を差し替えたときなど）は、\n  合わないファイルは差し替えずに英語のまま動きます。\n'
    s += '・ほかの MOD やツールが dinput8.dll を使っているときは、同時には使えません。\n\n'
    s += '■ 更新履歴\n' + history + '\n'
    s += '■ クレジット\n'
    s += '・日本語の文字は %s（SIL Open Font License 1.1）から作った絵を dinput8.dll に入れて使っています。\n  ライセンスは同梱の OFL.txt をご覧ください。\n' % d['font']
    s += '・このパッチの使用は自己責任でお願いします。\n・配布物には原作のプログラムやデータは入っていません。\n\n'
    s += 'LEGO は LEGO Group の商標です。%s\nゲームの画像・文章の権利は原作の権利者にあります。\n\n' % d['tm']
    s += 'ご意見・誤訳の報告: https://github.com/higesho/lego-ja/issues\n'
    s += 'サイト: https://higesho.github.io/lego-ja/%s/\n' % g
    return s

def ofl(g):
    d = G[g]
    body = open(LOTR_OFL, encoding='utf-8-sig').read()
    i = body.index('This Font Software is licensed')
    cp = {'Noto Serif JP': 'Noto Serif JP: Copyright 2017-2023 Adobe (http://www.adobe.com/).',
          'Noto Sans JP': "Noto Sans JP: Copyright 2014-2021 Adobe (http://www.adobe.com/), with Reserved Font Name 'Source'."}[d['font']]
    head = ('The Japanese characters drawn by dinput8.dll are bitmap images rendered from\n%s (%s instance). No font file is included.\n\n%s\n\n'
            % (d['font'], d['fontweight'], cp))
    return head + body[i:]

if __name__ == '__main__':
    g, ver, date = sys.argv[1], sys.argv[2], sys.argv[3]
    d = G[g]
    dll = os.path.join(ROOT, g, 'build', 'dinput8.dll')
    data = open(dll, 'rb').read()
    if b'LEGOJP_TESTIO' in data: raise SystemExit('試験版の DLL です')
    pkg = os.path.join(ROOT, 'release', g); os.makedirs(pkg, exist_ok=True)
    hist = 'v%s（%s）\n・最初の公開。\n' % (ver, date)
    open(os.path.join(pkg, '読んでください.txt'), 'w', encoding='utf-8-sig', newline='\r\n').write(readme(g, ver, date, hist))
    open(os.path.join(pkg, 'OFL.txt'), 'w', encoding='utf-8-sig', newline='\r\n').write(ofl(g))
    shutil.copy(dll, os.path.join(pkg, 'dinput8.dll'))
    out = os.path.join(ROOT, 'release', d['zip'] + '.zip')
    if os.path.exists(out): os.remove(out)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in ('dinput8.dll', '読んでください.txt', 'OFL.txt'):
            z.write(os.path.join(pkg, f), f)
    print(out, os.path.getsize(out), 'bytes')
