## PR記録: feat: Mermaid を CDN から読まず生成物に同梱する
issue: 02 (02_vendor-mermaid.md)
PR: https://github.com/yktsnet/codeview/pull/14

## 変更内容
- mermaid 10.9.8 の UMD 版 `dist/mermaid.min.js` を `codeview/assets/` に同梱し、版と LICENSE 本文を `LICENSE.mermaid` に写した
- `build.build_mermaid()` が内容のハッシュ入りの `public/mermaid.<hash>.js` を毎回書き、その href を `MERMAID_HREF` に持つ
- `render_markdown()` が返すスクリプトを、同梱ファイルを読む `<script src>` と、`mermaid.initialize` / `mermaid.run(...).catch(...)` を呼ぶ通常のインラインスクリプトに置き換えた（初期化の内容は従来どおり）
- `pyproject.toml` の package-data に `assets/*` を足し、`nix build` の成果物に入るようにした
- テストの見本サイトの環境から `GH_CONFIG_DIR` を外した（端末に設定があると `test_two_accounts_use_their_own_gh_config` が落ちるため。ご指示で本 Issue の中で直した）

## 保証
- Mermaid の図を含む Markdown のページは、外部のホストからスクリプトを読まない → `tests/test_build.py` `test_mermaid_page_loads_only_bundled_script`
- 維持する保証（台帳 1 の全項目）→ 既存テストが通る。mermaid のファイルは `public/` に置き、`functions/` には置かない

## 静的確認結果
- `nix develop -c pytest -q`: 27 件が通る
- `nix build`: 成果物に `codeview/assets/mermaid.min.js` と `LICENSE.mermaid` が入る
- 手元でこのリポの README を build して配ると、Publishing の図が SVG に描画され、Mermaid の外部配信元へのリクエストは無かった

## 検証手順
ネットワークを切った状態で `codeview build && codeview serve` を開き、README（Publishing の図）の Mermaid が描画されること。

## 確認者の判定
| 確認 | 判定 |
|---|---|
| `nix develop -c pytest -q` が通る | 合 |
| `nix build` の成果物に `assets/mermaid.min.js` がある | 合 |
| 同梱が mermaid 10 系の UMD 単一ファイル（仮定） | 合 |

| 保証 | 判定 |
|---|---|
| Mermaid ページは外部ホストからスクリプトを読まない | 合 |
| 台帳 1 の維持 | 合 |
| 台帳の更新 | 合 |

範囲の外: `tests/conftest.py` の変更と Issue の `対象` への追記（user 判断で本 Issue 内に含めた）。

---

## Mermaid を CDN から読まず生成物に同梱する
id: 02
branch-slug: vendor-mermaid
status: close
parent: codeview-26
type: feat
対象: codeview/render.py, codeview/build.py, codeview/assets/mermaid.min.js (新規), codeview/assets/LICENSE.mermaid (新規), pyproject.toml, tests/test_build.py, tests/conftest.py, docs/guarantees.md
内容: Markdown の Mermaid 図は、いまは jsdelivr から ESM を import して描いている（`codeview/render.py:219`）。そのため生成物をオフラインで読むと図が出ない。版を固定した mermaid の単一ファイルを本体に同梱し、build が `public/` へ書き出して、ページはそれを読むようにする。
対象外: リンクの相対パス化（03 で扱う）。mermaid の版を 11 系へ上げること。build のときに図を SVG へ描いておくこと（mermaid-cli は Node と headless Chrome が要り、依存の方針から外れる）。
仮定: 同梱するのは mermaid 10 系の最新パッチの UMD 版 `dist/mermaid.min.js`（単一ファイル、約 3MB）とする。いまの `mermaid@10` と同じ系統なので描画は変わらない。リポが約 3MB 増えるのは許容する。
確認: `nix develop -c pytest -q` が通る。`nix build` が通り、`result` 内にインストールされた `codeview/assets/mermaid.min.js` が存在する。
人が見るもの: ネットワークを切った状態で `codeview build && codeview serve` を開き、README（Publishing の図）の Mermaid が描画されること。

---

### 保証
- 新たに宣言する保証:
  - Mermaid の図を含む Markdown のページは、外部のホストからスクリプトを読まない。読むスクリプトは `public/` に書き出したファイルである
- 維持する保証: 台帳 1（`tests/test_build.py`）の全項目。特に「拡張を設定しなければ、`functions/` には `_middleware.js` だけを書き」（mermaid のファイルは `public/` 側に置き、`functions/` には置かない）と「長い Markdown の目次」

### codeview/assets/
- `mermaid.min.js` は npm の `mermaid@10.<最新パッチ>/dist/mermaid.min.js` を取得してそのまま置く。版はファイル名ではなく `LICENSE.mermaid` の先頭行（例: `mermaid 10.9.x — MIT License`）に書き、その下に mermaid の LICENSE 本文を写す
- ESM 版（`mermaid.esm.min.mjs`）は使わない。チャンクに分かれていて単一ファイルにならず、`type="module"` のスクリプトは `file://` で開いたページから読めない（03 で `file://` を通すため）

### pyproject.toml
- `[tool.setuptools.package-data]` で `codeview = ["assets/*"]` を足し、`nix build` の成果物に入るようにする

### codeview/build.py
- `style.build_style()`（`codeview/style.py:477`）と同じ形の関数を build.py に置く。内容のハッシュをファイル名に入れて `public/mermaid.<hash>.js` に書き、その href をモジュール変数に持つ。読み出しは `importlib.resources` で行う
- 書き出しは Mermaid を含むページの有無に関わらず毎回行ってよい（配信ブランチは毎回作り直すので、blob が同じなら git の転送量は増えない）

### codeview/render.py
- `render_markdown()` が返すスクリプトを、`<script src="<上の href>"></script>` と、`mermaid.initialize` / `mermaid.run` を呼ぶ通常の（module でない）インラインスクリプトに置き換える。トップレベルの `await` は使えないので、`mermaid.run(...).catch(...)` の形にする
- 初期化の内容（`startOnLoad: false`, `theme: 'dark'`, `.mermaid` の要素を描く）はいまと同じにする

### tests/test_build.py
- 見本のリポに ```` ```mermaid ```` を含む Markdown をコミットして build し、そのページについて次を確かめるテストを足す
  - `https://` を含む `src` / `import` が無い
  - `<script src="...">` が指すファイルが `public/` に存在する

### docs/guarantees.md
- 台帳 1 の箇条と表に、上の新しい保証と対応テストを足す
