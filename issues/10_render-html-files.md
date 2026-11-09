## HTML ファイルを描画して見せる
id: 10
branch-slug: render-html-files
status: open
type: feat
対象: codeview/build.py（`file_body` の分岐）, codeview/render.py, codeview/style.py（iframe とソース切り替えの見た目）, tests/test_build.py, docs/guarantees.md（§1 の箇条と表）, README.md・README.en.md（機能の説明に1行）
目的: リポに置いた `.html` の資料（提案資料・レポートなど）を、clone してブラウザで開かずに codeview の中で読めるようにする。いまは `.html` もハイライトしたソースとして出るので、GitHub と同じく中身を見るには手元で開くしかない。
内容: `.html` と `.htm` のファイルページは、描画した結果を sandbox 付きの iframe（`srcdoc`）で本文に出し、同じページでソースも読めるようにする。sandbox には `allow-same-origin` を付けない。
対象外: HTML 内の相対リンク・相対パスの画像やスクリプトの解決（`srcdoc` の中では解決しない。今回は描画できるものだけを出す）。iframe の高さを中身に合わせて自動で伸ばすこと。埋め込み README としての `.html` の描画。`.svg` の扱い（いまのままコードとして描く）。
仮定: sandbox は `allow-scripts` を付け、`allow-same-origin` は付けない。資料には開閉などで JavaScript を使うものがあり、それが動かないと読めない。一方で origin を不透明にすれば、HTML の中のスクリプトは codeview の Cookie・vault の Function・親ページに触れない。HTML の中から外部のホスト（CDN のフォントやスクリプト）を読むのは止めない。止めると描画が崩れる資料が多く、codeview 自身のページが外部を読むわけではない。
確認: 下の「確認」の節を見る
人が見るもの: 実際の資料（`~/github-client/indx/proposal/workplan.html`）を codeview-local で開き、描画の読みやすさ・iframe の高さ・ソースへの切り替えの使い心地を見る

---

### 保証
- 新たに宣言する保証:
  - `.html` と `.htm` のファイルページは、ファイルの中身をそのまま `srcdoc` に入れた `<iframe>` を本文に出す。iframe の `sandbox` 属性は `allow-scripts` を含み、`allow-same-origin` を含まない
  - 同じページで、ハイライトしたソースも読める。JavaScript が無くても読める形（`<details>` など）で出す
  - ヘッダのメタ情報（行数・サイズ・言語）と Copy file は、ほかのコードのページと同じく出る。Copy file が写すのはソースである
  - 大きすぎるファイル（`MAX_BYTES` 超）とバイナリは、いまと同じく `Too large to display` / `Binary` を出し、iframe を出さない
- 維持する保証（台帳 §1 から）:
  - ファイルのページは、ヘッダに行数と（ハイライトできれば）言語を出し、本文側にトップからのパンくずを置き、同じディレクトリの前後のファイルへのリンクを出す
  - `.svg` のページはコードとして描く
  - `--incremental` を付けて作った出力は、付けずに作り直したものと同じになる
  - Markdown 本文は生の HTML のうち許したものだけを描き、`.md` の描画は変わらない

### 確認
1. `nix develop -c pytest -q` が通る
2. 新しいテスト（`tests/test_build.py`）が、`.html` を含むリポを build し、そのファイルページについて次を確かめる
   - `<iframe` があり、`srcdoc` を HTML の実体参照から戻すと元のファイルの中身と一致する
   - `sandbox` 属性に `allow-scripts` があり、`allow-same-origin` が無い
   - ハイライトしたソースが同じページにある
3. `.htm` でも 2 と同じになる
4. `MAX_BYTES` を超える `.html` のページに iframe が無く、`Too large to display` が出る
5. `.svg` のページに iframe が無い（既存のコード表示のまま）
6. `--incremental` の出力が、付けない build と同じになる既存のテストが通る
7. `docs/guarantees.md` の §1 に新しい保証の箇条と、表にテストの行がある
8. README（日本語・英語）の機能の説明に、HTML を描画して見せることが1行ある

### codeview/build.py
`file_body` の分岐で、`is_text` を通ったあと、拡張子が `.html` / `.htm` のときに新しい描画へ回す。`MAX_BYTES` とバイナリの判定はいまの順のまま先に当てる。メタ情報と `copy_body` はコードのページと同じにする。

### codeview/render.py
iframe とソースを並べた本文を返す関数を足す。`srcdoc` の値は `html.escape(text, quote=True)` で属性用に逃がす。iframe の高さは CSS で決める（画面の高さに対する固定値で、中はスクロールする）。
