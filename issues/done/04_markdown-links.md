## Markdown 本文のリポ内リンクを生成したページへ向ける
id: 04
branch-slug: markdown-links
status: close
type: fix
対象: codeview/render.py, codeview/build.py, tests/test_build.py, docs/guarantees.md
内容: リポのファイルを Markdown として描くとき、本文の相対リンク（`[guide](docs/guide.md)`、`[src](main.py)`、`[back](../README.md)`、`[d](docs/)`）は書いたままの href で出力される。生成物は `docs/guide.md.html` なので、リンク先が見つからない。`docs/` は file:// で開けず、`/` 始まりは `relativize()` がサイトのルートを基準に解決してしまう。リポ内を指すリンクを、そのファイルのページ（ディレクトリならそのディレクトリのページ）へ向ける。ファイルページの本文と、ディレクトリのページに埋め込む README の両方が対象である。
対象外: Issue のページの本文（`layout.issue_main()` から `render_markdown()` を呼ぶ経路。GitHub の Issue も拡張の Issue も、本文の相対リンクはリポのファイルを指すものとして扱わない）。画像（`<img>`）。外部 URL・`mailto:`・ページ内アンカー（`#...`）。拡張が `build()` で書くページ。
仮定: `/` 始まりのリンクは、GitHub と同じくリポのルートを基準に解決する。リンク先がリポ内にページを持たないとき（HEAD に無い・`exclude_prefixes` / `skip_exts` で除外した・リポの外を指す）は、Issue 本文の無害化と同じく `<a>` を外して文字だけ残す。`?` 以降の query は落とす。
確認: `nix develop -c pytest -q` が通る。新しいテストで、見本のリポの Markdown に下の詳細にある各種のリンクを書き、ファイルページとディレクトリのページの両方で、href が期待するページを指すことと、ページの無い先へのリンクが `<a>` でなくなることを確かめる。既存の `test_links_are_relative_and_resolve`（生成した全 HTML の相対リンクが実在するファイルを指す）も通る。
人が見るもの: `codeview build` 後に Finder から `public/index.html` を開き、README の中のリンクから別の `.md` やソースのページへ飛べること。

---

### 保証
- 新たに宣言する保証:
  - リポのファイルを描いた Markdown の本文で、リポ内のファイルを指す相対リンクは、そのファイルのページへのリンクになる。`#` 以降のアンカーは残す
  - リポ内のディレクトリを指すリンクは、そのディレクトリのページ（`index.html`）へのリンクになる
  - `/` 始まりのリンクは、リポのルートを基準に解決する
  - 上の解決は、ファイルページの本文でも、ディレクトリのページに埋め込んだ README でも、同じ先を指す（基準になるのは `.md` の位置であって、表示するページの位置ではない）
  - リンク先がリポ内にページを持たないときは、リンクにせず文字だけを残す
- 維持する保証: 台帳 1 の全項目。特に「README を持つディレクトリのページには、一覧の下に README を描く」「本体が書くページの `href` / `src` は、外部 URL・ページ内アンカーを除いて `/` で始まらない相対パスである」「その相対パスは、ページの位置から解決すると `public/` 内に実在するファイルを指す」。台帳 2 の全項目（Issue のページの本文の描き方は変えない）

### 方針
- 書き換え先は、本体の内部で使っているサイト内の絶対パス（`/{slug}/{path}.html`、`/{slug}/{dir}/`）にする。表示するページからの相対化は、既存の `layout.relativize()` が `page()` でまとめて行う。こうすれば、ファイルページと埋め込みの README で基準のパスが違っても、書き換える側では区別しなくてよい
- 解決の基準は、その `.md` のリポ内のディレクトリである。`posixpath.normpath` で `..` を畳み、リポの外へ出たらページの無い先として扱う
- `%20` などのパーセントエンコードは、ファイルの一覧と突き合わせる前に戻す。出力の href は、`build.py` の `file_href()` が作る形に揃える

### codeview/render.py
- `render_markdown()` に、リンクを解決するための省略可能な引数を足す。中身は、その `.md` のリポ内パス、slug、HEAD のファイルとディレクトリの集合である。形（個別の引数か、1つの小さなオブジェクトか）は実行者が決めてよい
- 引数が渡され、かつ `safe` でないときだけ、Treeprocessor で `<a>` の `href` を書き換える。scheme かホストを持つもの・`#` 始まり・`//` 始まりは触らない
- `safe=True` の経路と、引数を渡さない呼び出し（`layout.issue_main()`）の出力は変えない

### codeview/build.py
- `build_repo()` 内の `render_markdown()` の呼び出し2か所（`codeview/build.py:138` のファイルページ、`codeview/build.py:196` の埋め込み README）で、上の引数を渡す。埋め込み README では、`.md` のパスとして `rpath` を渡す
- ファイルとディレクトリの集合は、既に持っている `tree` / `entries` から作る。ページになるのは `entries` に残ったファイルなので、除外したファイルは集合に入れない

### tests/test_build.py
- 新しいテストを足す。見本のリポに、例えば `README.md`（ルート）と `docs/guide.md`・`docs/` 配下のファイルを置き、次のリンクを書く。期待値は、生成した HTML の href をページの位置から解決したリポ内のページとして確かめる
  - `docs/guide.md` → `docs/guide.md.html`
  - `docs/guide.md#usage` → 同上で、`#usage` が残る
  - ソースファイル（例: `main.py`）→ `main.py.html`
  - `docs/` と `docs` → `docs/index.html`
  - `/docs/guide.md`（ルート基準）→ `docs/guide.md.html`
  - `docs/guide.md` の中の `../README.md` → `README.md.html`
  - HEAD に無いファイル、`skip_exts` で除外したファイル（見本の設定は `.png`）、`../../x.md`（リポの外）→ `<a>` にならず文字が残る
  - `https://example.com/` と `#見出し` は変わらない
- ルートの `README.md` の上のリンクは、`alpha/README.md.html` と `alpha/index.html` の両方で同じ先へ解決されることを確かめる
- `test_links_are_relative_and_resolve`（`tests/test_build.py:169`）は、見本の Markdown に `[top](/)` と `[dir](/alpha/docs/)` を書いている。サイトのルートを基準にした書き方なので、新しい規則では `/alpha/docs/` がリポ内の `alpha/docs/` を指し、ページが無いので文字になる。このテストの目的（全 HTML の相対リンクが実在するファイルを指す）は変えない。見本のリンクは、新しい規則でもリンクとして残るもの（例: `[top](/)`・`[dir](/docs/)`）に書き換えてよい

### docs/guarantees.md
- 台帳 1 に、上の新しい保証と対応テストを足す
