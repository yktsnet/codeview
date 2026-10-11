# codeview

@context/conventions.md
@context/structure.md
@context/domain.md

## フェーズ

Issueドリブン期。

## コマンド

```bash
nix develop                 # python（pygments・markdown・pytest）・git・gh が入る
nix build                   # ./result/bin/codeview
codeview build              # 作業ディレクトリの codeview.toml を読み、public/ と functions/ を書く
codeview serve              # public/ を手元で配る（Functions は動かない）
```

`codeview publish`（配信ブランチへの force push）と `codeview cf-setup`（Cloudflare のリソース作成）は外部に副作用があるので、Agent は実行しない。

## アーキテクチャの要点

- 走査対象のリポの HEAD を `git ls-tree` / `git cat-file --batch` で読む。作業ツリーの未コミットの変更は出ない
- 生成物は全リポのコードを含む。本体のリポに `deploy` ブランチや生成物を載せない
- 本体は設定を書かない。利用者が自分のリポに `codeview.toml` と拡張を置き、そこで `codeview` を動かす

## 検証手段

```bash
nix develop -c pytest -q
```

テストは見本のリポ群・設定・偽の `gh` を一時ディレクトリに作り、生成器を別プロセスで回す（`tests/conftest.py`）。ネットワークも Cloudflare も使わない。
