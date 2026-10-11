# 規約

- 依存は `pygments` と `markdown` だけに保つ。HTTP は `urllib`、外部コマンドは `git` と `gh` を `subprocess` で呼ぶ
- 設定の誤りは `config.ConfigError`、拡張の読み込みの失敗は `plugins.PluginError` で止める。既定値で続行しない。未知のキーも誤りとして扱う
- `ConfigError` / `PluginError` のメッセージは、そのまま利用者に出す英文にする
- `config.load()` と `plugins.load()` はプロセス内でキャッシュする。テストはケースごとに別プロセスで生成器を呼ぶ
- 各コマンドは `main(argv) -> int` を持ち、`codeview/__main__.py` の `COMMANDS` に1行の説明を足す
- 拡張の口（`plugins.py` の docstring にある関数群）は公開 API である。名前と引数を変えるときは利用者側の拡張が壊れる
- 生成するページは JavaScript なしでも読める静的 HTML にする。CSS は `style.py` に1枚で持ち、内容のハッシュをファイル名に入れる
- GitHub の Issue の本文は他人の文章を含むので、生の HTML を出さない（`Issue.trusted = False`）
- 配信ブランチは親を持たない単一コミットとして毎回作り直す。作業ツリーと index には触らない
