# codeview

@context/conventions.md
@context/structure.md
@context/domain.md

## フェーズ

Issueドリブン期。

## コマンド

```bash
nix develop                   # python（pygments・markdown・pytest）・git・gh が入る
nix build                     # ./result/bin/codeview
codeview build                # 作業ディレクトリの codeview.toml を読み、public/ と functions/ を書く
codeview build --incremental  # 前回から入力の変わったリポだけを作り直す。変化が無ければ何もしない
codeview serve                # public/ を手元で配る（Functions は動かない）
```

`codeview publish`（配信ブランチへの force push）と `codeview cf-setup`（Cloudflare のリソース作成）は外部に副作用があるので、Agent は実行しない。

## 検証手段

```bash
nix develop -c pytest -q
```
