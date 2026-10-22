# 構成

```
codeview/
  __main__.py    コマンドの振り分け（build / serve / publish / cf-setup / cf-status）
  config.py      codeview.toml の読み込みと検証
  repo.py        走査対象のリポの列挙、HEAD のファイルと blob の読み出し、remote からアカウントを決める
  issues.py      アカウントごとに未消化の Issue を集める（GitHub は gh、それ以外は拡張）
  plugins.py     拡張の読み込みと、決まった口での呼び出し
  render.py      コードのハイライト、Markdown の描画と無害化
  layout.py      ページの枠・一覧・トップ・Issue のページ
  style.py       CSS と functions/_middleware.js の中身
  build.py       生成の本体
  publish.py     build してから配信ブランチへ push する
  cloudflare.py  Cloudflare API と資格情報
  cf_setup.py    Pages プロジェクト・カスタムドメイン・Access を作る
  cf_status.py   Pages プロジェクトと直近のデプロイを表示する
tests/
  conftest.py    見本のリポ群・設定・偽の gh を作るフィクスチャ
  test_*.py      build・issues・plugins・publish の外から見た振る舞い
```

## データの流れ

1. `config.load()` が `CODEVIEW_CONFIG` か作業ディレクトリの `codeview.toml` を読む
2. `plugins.context()` が `[[roots]]` からリポを列挙し、slug を振る（リポ名が重なるときだけ `group/name`）
3. `issues.collect()` がアカウントごとに Issue を集め、ファイルから Issue への索引を作る
4. `build.build_repo()` がリポごとに HEAD のファイルをページにする
5. `layout.build_index()` と `issues_pages()` がトップと Issue のページを書き、拡張の `build()` が自前のページを足す
6. `publish` は指紋（アカウントごとの走査対象の HEAD・設定のリポの HEAD・本体の版・拡張の `fingerprint()`）を取り、`public/` と `functions/` を一時 index に載せて配信ブランチへ force push する。Cloudflare Pages がそのブランチを配る
