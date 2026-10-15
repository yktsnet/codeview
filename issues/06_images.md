## 画像をファイルのページと Markdown の本文に表示する
id: 06
branch-slug: images
status: open
depends: 05
type: feat
対象: codeview/render.py, codeview/build.py, codeview/style.py, tests/test_build.py, docs/guarantees.md
内容: 画像は生成物に出していない。画像ファイルのページは `Binary (サイズ)` と出るだけで、README の `![](docs/x.png)` や `<img src="docs/x.png">` は、書いたままの src で出力されるので画像が切れる。画像の多いリポは 05 の設定で外せるので、画像を生成物にコピーして、ファイルのページと Markdown の本文（ファイルのページと、ディレクトリのページに埋め込む README）に表示する。
対象外: Issue の本文の画像（safe の描画は今のまま `[alt]` の文字にする）。生の HTML の `<a href>` の書き換え。`<picture>` / `srcset`。リポ外（http/https）の画像の取得や同梱
仮定:
- 対象の拡張子は `.png` `.jpg` `.jpeg` `.gif` `.webp` `.ico` `.svg`。`.svg` のファイルのページは今のままコードとして描き、Markdown から埋め込めるよう元のファイルもコピーする
- 1枚 5 MiB を超える画像はコピーしない。ファイルのページは `Too large to display` を出し、本文の画像は `[alt]` の文字にする（Cloudflare Pages の上限は 1 ファイル 25 MiB）
- リポ外の URL（http/https）を指す画像は読み込まず、`[alt]` の文字にする。生成物を file:// でもネットに繋がずに読めるよう、Mermaid を同梱にしたのと同じ判断
確認: `nix develop -c pytest -q` が通る。新しいテストで、見本リポの画像について、ファイルのページに `<img>` が出ること、Markdown（`![]()` と生の `<img>` の両方）の src がページの位置からの相対パスで、`public/` 内に実在する画像ファイルを指すこと、ページの無い画像・リポ外の画像は `[alt]` の文字になることを確かめる
人が見るもの: 実際の `codeview.toml` で全体の `skip_exts` から画像の拡張子を外し、hi にだけ 05 の設定で足して build し、README の画像と画像ファイルのページを PC とスマホで見る。生成物のファイル数と容量の増え方

---

### 保証
- 新たに宣言する保証:
  - 対象の拡張子の画像（除外していないもの、5 MiB 以下）は、`public/<slug>/<リポ内パス>` にそのままコピーする
  - 画像ファイルのページは、その画像を `<img>` で表示する（`.svg` はコードとして描く）
  - リポのファイルを描いた Markdown の本文で、リポ内の画像を指す `![]()` と生の HTML の `<img>` の src は、コピーした画像を指す相対パスになる。解決の基準と `/` 始まりの扱いは、リンクと同じ（`.md` の位置が基準、`/` 始まりはリポのルート）
  - 指す先の画像が無い（HEAD に無い・除外した・5 MiB 超・リポの外）`<img>` と、リポ外の URL を指す `<img>` は、`[alt]` の文字にする
- 維持する保証（台帳 1・2）:
  - 本体が書くページの `href` / `src` は、外部 URL・ページ内アンカーを除いて `/` で始まらない相対パスで、ページの位置から解決すると `public/` 内に実在するファイルを指す
  - Markdown 本文のリポ内リンクの解決（ファイル・ディレクトリ・`/` 始まり・アンカー・ページの無い先は文字）と、ファイルページと埋め込み README が同じ先を指すこと
  - `exclude_prefixes`・`skip_exts`（05 のリポ単位を含む）で除外したファイルはページにしない。除外した画像はコピーもしない
  - GitHub の Issue の本文とコメントに含まれる生の HTML はエスケープする（Issue の本文の画像は今のまま出さない）
  - `--incremental` の出力は、付けずに作り直したものと同じになる

### codeview/render.py
- `LinkContext` に、コピーした画像のリポ内パスの集合を持たせ、画像の src を解決するメソッドを足す。リンクの `resolve()` と同じ規則で target を出し、集合にあれば `/{slug}/{target}`（`.html` を付けない）、無ければ None。`relativize()`（`layout.py:24`）が後で相対パスに直す
- `![]()` は Treeprocessor（`_ResolveLinks` と同じ段）で `img` を書き換える。None なら `_Sanitize` と同じく `<span class="noimg">[alt]</span>` にする
- 生の HTML の `<img>` は Treeprocessor から見えない（`md.htmlStash` に退避されている）。退避した塊を、`raw_html` の Postprocessor（優先度 30）より先に走る Postprocessor で書き換える。描き終えた HTML 全体を正規表現で書き換えると、`![]()` の解決済みの `/` 始まりの src をリポのルート基準でもう一度解決してしまうので、そうしない
- safe（Issue の本文）は変えない

### codeview/build.py
- `build_repo()`（138行）で、対象の拡張子のファイルは `is_text()` の判定より前に拡張子で分ける。5 MiB 以下なら `public/<slug>/<パス>` に bytes を書き、ファイルのページの本文を `<img>` にする。src は `/{slug}/{パス}` で書き、`relativize()` に任せる
- `links_for()` に画像の集合を渡す。集合は `entries` のうち、コピーした画像だけから作る
- 末尾のファイル数の警告（456行）は `public/` を数えているので、画像の分も含まれる。変えない

### codeview/style.py
- 画像ファイルのページの `<img>` に `max-width: 100%; height: auto;` を当て、透過画像が地の色に溶けないよう枠か背景を付ける。`.markdown-body img`（321行）は今のままでよい

### tests/test_build.py
- 見本リポに小さな画像（1x1 の PNG のバイト列で足りる）を置く。`conftest.py` の全体の `skip_exts = [".png"]` に当たるので、`.gif` などの別の拡張子で置くか、テストの中で設定を書き換える
- `_assert_relative_and_resolvable()`（157行）が `src` も見ているので、画像を含む見本で全ページに当てる
- 台帳 1 の対応表に新しいテストを足す
