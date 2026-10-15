## リポごとに除外する拡張子とパスを足せるようにする
id: 05
branch-slug: repo-scan-overrides
status: open
type: feat
対象: codeview/config.py, codeview/build.py, tests/test_build.py, tests/conftest.py, docs/guarantees.md, README.md, README.en.md
内容: `[scan]` の `skip_exts` と `exclude_prefixes` は全リポに一律で効く。画像の多いリポ（hi）だけ画像を出さず、他のリポでは出す、という使い分けができない。06 で画像を出力に戻す前に、リポ単位で除外を足す設定を設ける。
対象外: 画像を出力に戻すこと（06）。`skip_dirs` のリポ単位の設定。全体の `[scan]` の意味を変えること
仮定: リポの指定には、生成物のパスと同じ slug（`<group>/<name>`、`path` のルートは `<group>`。`build.py` の `slugged` と同じ値）を使う。設定に書いた slug が走査対象に無くても止めず、標準エラーに警告を出す（リポを外した直後に build が通らなくなるのを避ける）
確認: `nix develop -c pytest -q` が通る。新しいテストで、リポ単位の設定を書いたリポだけでそのファイルのページが出ず、同じ拡張子・パスでも他のリポでは出ることを確かめる
人が見るもの: 実際の `codeview.toml` への設定の追記（06 の後に全体の `skip_exts` から画像の拡張子を外し、hi にだけ足す）

---

### 保証
- 新たに宣言する保証:
  - `[scan.repos."<slug>"]` に書いた `skip_exts` と `exclude_prefixes` は、その slug のリポにだけ、全体の `[scan]` の値に足して効く。他のリポのページは変わらない
  - リポ単位で除外したファイルは、全体で除外したファイルと同じく、Markdown のリンク先にならない（リンクにせず文字だけ残す）
  - `[scan.repos."<slug>"]` に `skip_exts` と `exclude_prefixes` 以外のキーがあれば、`error:` を出して非0で終わり、`public/` を作らない
  - 走査対象に無い slug を書いても build は止まらず、その slug を標準エラーに出す
- 維持する保証（台帳 1）:
  - `exclude_prefixes` に前方一致するパス、`skip_exts` の拡張子、未コミットのファイルはページにしない
  - 設定の書式が誤っているときは `error:` を出して非0で終わり、`public/` を作らない
  - リンク先がリポ内にページを持たないとき（HEAD に無い・除外した・リポの外）は、リンクにせず文字だけを残す
  - `--incremental` の出力は、付けずに作り直したものと同じになる（設定は入力の `global` に含まれるので、リポ単位の設定を変えても作り直される）

### codeview/config.py
- `[scan]` の既知キー（`_unknown` の呼び出し、205行付近）に `repos` を足す
- `Config` に `repo_scan: dict[str, RepoScan]`（slug → その追加分）を持たせる。`RepoScan` は `skip_exts`（小文字にそろえる）と `exclude_prefixes` の2つ。読み込みと検証は既存の `_table` / `_strs` / `_unknown` に合わせる

### codeview/build.py
- `_page_entries()`（88行）は今リポを知らない。slug を受け取り、全体の値にそのリポの追加分を足して判定する。呼び出し元は `build_repo()` だけ
- 走査対象に無い slug の警告は `main()` で `slugged` が決まった後に出す。文言は英語（例: `warning: [scan.repos] no such repo: <slug>`）

### tests/test_build.py・tests/conftest.py
- `conftest.py` の見本は `own/alpha` に `logo.png` を持ち、全体の `skip_exts = [".png"]` で落としている。既存のテストを崩さないよう、新しいテストは設定を書き換えて使う（`site.write_config`）
- 台帳 1 の対応表に新しいテストを足す

### README.md・README.en.md
- 設定の表（`[scan]` の行、63行付近）にリポ単位の上書きを足し、hi のような画像の多いリポだけ画像を外す例を1つ載せる
