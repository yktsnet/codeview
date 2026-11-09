## PR記録: feat: Render HTML files in a sandboxed iframe
issue: 10 (10_render-html-files.md)
PR: https://github.com/yktsnet/codeview/pull/42

## 変更内容
`.html` と `.htm` のファイルページでは、描画した結果を sandbox 付きの iframe（`srcdoc`）で本文に出し、ハイライトしたソースを同じページの `<details>` に置く。sandbox は `allow-scripts` だけで、`allow-same-origin` は付けない。iframe の高さは画面の 80% に固定し、中でスクロールする。メタ情報と Copy file（写すのはソース）はコードのページと同じ。`MAX_BYTES` 超とバイナリの扱いは変えない。README（日本語・英語）と保証台帳 §1 を更新した。

UTF-8 でない HTML は文字化けする（コード表示と同じ読み方）。user と相談して今回は見送った。

## 保証
- `.html` / `.htm` を srcdoc の iframe で出し、sandbox は allow-scripts を含み allow-same-origin を含まない → `tests/test_build.py::test_html_file_page_renders_in_sandboxed_iframe`
- ソースを `<details>` で同じページに出し、Copy file はそのソースを写す → 同上
- メタ情報 → 同上
- MAX_BYTES 超・バイナリは iframe を出さない → 同上
- 維持: `.svg` のコード表示（同上・`test_images_are_copied_and_shown`）、ナビゲーション（`test_file_page_navigation`）、`--incremental`（`test_incremental_build_matches_full_build`）

## 静的確認結果
- `nix develop -c pytest -q`: 89 passed
- 変更ファイル: README.en.md / README.md / codeview/build.py / codeview/render.py / codeview/style.py / docs/guarantees.md / tests/test_build.py

## 確認者の判定
| # | 項目 | 判定 |
|---|---|---|
| 1 | pytest が通る | 合 |
| 2 | `.html` の iframe・srcdoc・sandbox・ソース | 合 |
| 3 | `.htm` も同じ | 合 |
| 4 | MAX_BYTES 超は iframe なしで Too large | 合 |
| 5 | `.svg` に iframe が無い | 合 |
| 6 | `--incremental` の既存テストが通る | 合 |
| 7 | 台帳 §1 に箇条と表の行がある | 合 |
| 8 | README の両方に1行ある | 合 |

保証（Copy file の中身・バイナリを含む）もすべて合。

## 手戻り
| 何が起きたか | 失ったもの | 原因の分類 | 仕組みで防げたか |
|---|---|---|---|
| 確認者が「否」を出した。Copy file が写す中身と、バイナリの `.html` に iframe を出さないことをテストで固定していなかったので、テストを足した | 1回。約5分 | 実装者の不注意 | 防げない |

---

## HTML ファイルを描画して見せる
id: 10
branch-slug: render-html-files
status: close
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
