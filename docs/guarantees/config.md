# config

## 設定ファイルと拡張の読み込み

| 保証 | 対応テスト |
|---|---|
| 設定ファイルが無いときは、`error:` を出して非0で終わり、`public/` を作らない | `test_missing_config_stops_before_build` |
| 設定の書式が誤っているときは、`error:` を出して非0で終わり、`public/` を作らない | `test_broken_config_stops_before_build` |
| 読み込めない拡張を設定したときは、そのモジュール名を出して非0で終わり、`public/` を作らない | `test_unknown_plugin_stops_before_build` |
| アカウントの `issues` に `[plugins] modules` に無いモジュールを挙げると、`error:` を出して非0で終わり、`public/` を作らない | `test_issue_source_must_be_listed_plugin` |
| `issues` に挙げた拡張が `issues()` を持たなければ、`no issues()` を出して非0で終わり、`public/` を作らない | `test_issue_source_needs_issues_function` |

## `[scan.repos]`

| 保証 | 対応テスト |
|---|---|
| `[scan.repos."<slug>"]` に `skip_exts` と `exclude_prefixes` 以外のキーがあれば、`error:` を出して非0で終わり、`public/` を作らない | `test_repo_scan_unknown_key_stops_before_build` |
| `[scan.repos]` の slug ごとの値が表でなければ、`error:` を出して非0で終わり、`public/` を作らない | `test_repo_scan_must_be_a_table_per_repo` |
| 走査対象に無い slug を `[scan.repos]` に書いても build は止まらず、その slug を標準エラーに出す | `test_repo_scan_unknown_slug_warns_and_continues` |

## `[[accounts]]`

| 保証 | 対応テスト |
|---|---|
| `[[accounts]]` が3つ以上なら、`1 to 2` を含むエラーで非0で終わり、`public/` を作らない | `test_at_most_two_accounts` |
| `issues` が `github` でないアカウントに `gh_config_dir` を書くと、非0で終わる | `test_gh_config_dir_only_for_github` |
| `check_every_hours` は正の整数だけを受け付け、それ以外は設定の誤りとして止める | `test_check_every_hours_must_be_positive_integer` |
