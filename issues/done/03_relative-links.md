## PR記録: feat: 生成するページのリンクを相対パスにして file:// で読めるようにする
issue: 03 (03_relative-links.md)
PR: https://github.com/yktsnet/codeview/pull/15

## 変更内容
- `layout.relativize()` を足し、`page()` に省略可能な `path`（そのページ自身のサイト内パス）を追加。渡されたときだけ、タグ内の `href` / `src` の `/` 始まりを相対パスに直す。`/` 終わりは `index.html` を補い、`//`・`#` 始まり・エスケープ済みコード・`<script>` 本文は触らない
- `layout.py` と `build.py` の `page()` 呼び出しすべてで `path` を渡す。内部のリンク（`Issue.href` など）は絶対パスのまま
- README / README.en.md に、サーバー無しで `public/index.html` を開けば読めることを追記
- `tests/test_plugins.py` の既存 assert 1 行を相対パスに直した（Issue の対象外だが、相対化で必然的に壊れるため承認を得て同 Issue で修正）

## 保証
- href/src は相対パス、実在ファイルを指す → `test_links_are_relative_and_resolve`
- 拡張の side()/home() のリンクも相対化 → `test_extension_home_and_side_links_are_relative`
- Issue ページのリンク → `test_issue_pages_link_relatively`

## 検証手順
`codeview build` 後に Finder から `public/index.html` を開いて辿れること、CSS、Mermaid の描画。`codeview serve` と Cloudflare でも同様。

## 確認者の判定
| 区分 | 判定 |
|---|---|
| pytest 30 passed | 合 |
| 全 HTML のリンクが相対で実在 | 合 |
| 人が見るもの（file://・serve・Cloudflare） | 判定できない |
| 保証（新規4項目・既存） | 合 |
| 範囲の外 | test_plugins.py 1 行（承認済み） |

---

## 生成するページのリンクを相対パスにして file:// で読めるようにする
id: 03
branch-slug: relative-links
status: close
parent: codeview-26
type: feat
対象: codeview/layout.py, codeview/build.py, tests/test_build.py, tests/test_issues.py, docs/guarantees.md, README.md, README.en.md
内容: 本体が書くページのリンク（`href` / `src`）は、いまは `/alpha/` のように `/` から始まる絶対パスである。そのため、サーバーなしで `public/index.html` を開くとリンクも CSS も切れる。リンクをページからの相対パスにし、ディレクトリへのリンクは `index.html` まで書く。こうすれば `public/` を丸ごと手元に置き、ファイルを開くだけで読める。Cloudflare Pages と `codeview serve` での表示は変えない。
対象外: 拡張が `build()` で自前に書くページのリンク（本体の `page()` を通らないものは触らない）。GitHub など外部への URL。ページ内アンカー（`#...`）。Mermaid の同梱（02 で扱う。本 Issue は 02 のマージ後に着手する）。
仮定: Cloudflare Pages は `/x/index.html` を `/x/` へ、`/a.html` を `/a` へリダイレクトする。これは今も `.html` のリンクで起きていることなので、許容する。`page()` は拡張の口（`plugins.py` の docstring）に含まれないので、引数を足してよい。ただし外部から呼ばれている場合に備えて、足す引数は省略可能にする。
確認: `nix develop -c pytest -q` が通る。新しいテストで、生成した全 HTML の `href` / `src` に `/` 始まりのものが無いこと、各相対リンクが `public/` 内の実在するファイルを指すことを確かめる。
人が見るもの: `codeview build` 後に Finder から `public/index.html` をブラウザで開き、トップ → リポ → ディレクトリ → ファイル → Issue と辿れること、CSS が当たっていること、README の Mermaid が描画されること。`codeview serve` と配信先（Cloudflare）でも同じように辿れること。

---

### 保証
- 新たに宣言する保証:
  - 本体が書くページの `href` / `src` は、外部 URL・ページ内アンカーを除いて `/` で始まらない相対パスである
  - その相対パスは、ページの位置から解決すると `public/` 内に実在するファイルを指す（ディレクトリへのリンクは `index.html` まで書く）
  - 拡張の `side()` / `home()` が返す HTML 内の `/` 始まりのリンクも、同じく相対パスに直る
- 維持する保証: 台帳 1〜3 の全項目。特に「トップにはリポへのリンクが並ぶ」「本文側にトップからのパンくずを置き、同じディレクトリの前後のファイルへのリンクを出す」「`targets` に挙げたファイルのページには、その Issue へのリンクを出す」「`waits` は一覧にある Issue へのリンクになる」。リンクの書き方は変わるが、どのページへ飛ぶかは変えない

### 方針
- 本体の内部では、リンクの先をいまと同じサイト内の絶対パス（`/alpha/`、`Issue.href` の `/issues/...` など）で持ち続ける。相対化は HTML を書き出す1か所で行う。`Issue.href` は拡張が読む可能性のあるデータなので、値を変えない
- その1か所は `layout.page()`（`codeview/layout.py:18`）とする。`page()` に、そのページ自身のサイト内パス（例: `/alpha/docs/guide.md.html`、`/alpha/index.html`）を受ける省略可能な引数を足す。渡されたときだけ、組み上げた HTML の `href="/..."` / `src="/..."` を相対パスへ書き換える
- 書き換えはタグの中の属性だけを対象にする。正規表現なら `<` で始まるタグの中の ` href="/` / ` src="/` に限る。エスケープ済みのコード（`&lt;a href="/x"&gt;`）の中の文字列は書き換えない（Python-Markdown のコードスパンは `"` をエスケープしないため、この区別が要る）
- `//` で始まるもの（プロトコル相対）は外部 URL として触らない
- 先が `/` で終わるものはディレクトリとして `index.html` を補う。トップへのリンク `/` は、`public/` 直下のページなら `index.html`、深いページなら `../../index.html` のようになる

### codeview/layout.py
- `page()` の呼び出し元（`build_index()`、`issues_pages()` など、`layout.py` 内のもの）すべてで、そのページのサイト内パスを渡す
- 相対化の関数は `layout.py` に1つだけ置き、`page()` から呼ぶ

### codeview/build.py
- `build_repo()` 内の `page()` の呼び出し（`codeview/build.py:162` 付近のファイルページ、`codeview/build.py:195` 付近のディレクトリページ）で、そのページのサイト内パスを渡す
- `page()` を呼んでいる箇所は `grep -n 'page(' codeview/*.py` で洗い、漏れなく渡す

### tests/test_build.py
- 既存のテストのうち `href="/alpha/"` などの絶対パスを前提にした assert（21, 59, 60, 62, 65 行目付近）を、相対パスの値に書き換える。指す先は変えない
- 新しいテストを足す。`public/` 以下の全 `.html` を読み、タグ内の `href` / `src` を拾って次を確かめる
  - `http:` / `https:` / `mailto:` / `#` / `//` で始まるものを除き、`/` で始まるものが無い
  - 残りをページの位置から解決し、`#` 以降を落とした先が `public/` 内の実在するファイルである
- 見本のサイトに拡張の `home()` で `/alpha/` へのリンクを返すものを足すか、既存の拡張の見本（`tests/test_plugins.py` の設定隣の拡張）を流用して、トップのそのリンクが相対パスに直ることを確かめる。流用のために test_plugins.py を触る必要が出たら、対象を増やさず test_build.py 側に見本を書く

### tests/test_issues.py
- GitHub の Issue のページ（`public/issues/<account>/...`）で、戻るリンク・左の一覧・CSS が相対パスで、実在するファイルを指すことを確かめる

### docs/guarantees.md
- 台帳 1 に上の新しい保証3つと対応テストを足す。台帳 2 に Issue のページのリンクの保証と対応テストを足す

### README.md / README.en.md
- `codeview serve` の説明（`README.md:49` 付近）の近くに、サーバーなしでも `public/index.html` を開けば読めることを1文で足す。拡張が `build()` で書くページのリンクは拡張側の責任であることも短く添える。英語版も同じ位置に同じ内容を書く
