# plugins

| 保証 | 対応テスト |
|---|---|
| 設定ファイルの隣に置いた拡張モジュールをアカウントの `issues` に挙げると、その `issues(ctx, account, repos)` が返す Issue を一覧とページに出す | `test_issue_source_next_to_config` |
| 拡張は `[plugins.<名前>]` の表を `ctx.options` で読める | `test_issue_source_next_to_config` |
| 拡張が返した Issue の `waits` のうち一覧にある Issue への依存は、Issue のページに `waits on <リポ> #<番号>` として出る | `test_issue_source_next_to_config` |
| 拡張が返した Issue の `waits` の表示は、待っている Issue のページへのリンクである | `test_issue_source_next_to_config` |
| 拡張が返した Issue の `waits` のうち一覧に無い Issue への依存は、出さない | `test_issue_source_next_to_config` |
| 拡張が `trusted` を立てなければ、Issue の本文の HTML はエスケープする | `test_issue_source_next_to_config` |
| 拡張が返した Issue の `targets` に挙げたファイルのページには、その Issue へのリンクを出す | `test_issue_source_next_to_config` |
