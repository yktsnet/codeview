# sessions（例の拡張 `examples/plugins/sessions.py`）

## セッションの一覧と本文のページ

| 保証 | 対応テスト |
|---|---|
| `[plugins.sessions]` の `config_dirs` ごとに `ccreel list --json --limit 0 --since <days>d --config-dir <dir>` を呼ぶ | `test_list_and_session_pages`, `test_passes_config_dir_and_period` |
| すべての config dir の一覧をまとめて、新しい順に `public/sessions/index.html` へ書く | `test_list_and_session_pages`, `test_merges_config_dirs` |
| 各セッションの本文を `ccreel show <id> --json` から `public/sessions/<id>.html` に書く | `test_list_and_session_pages`, `test_merges_config_dirs` |
| 本文のページには、発言と応答のテキストを出す | `test_list_and_session_pages` |
| 本文のページは応答の Markdown を、生の HTML・`<script>` を出さずに描く | `test_reply_markdown_is_safe` |
| 本文のページには、`ccreel resume <id>` の行を出す | `test_list_and_session_pages` |
| トップの左メニューに、`sessions` へのリンクと件数を出す | `test_top_menu_links_sessions_without_titles` |
| トップには、セッションのタイトルを出さない | `test_top_menu_links_sessions_without_titles` |
| セッションのページの左の一覧には、件数を出さない | `test_session_page_side_has_no_counts` |
| 生成したページの `href` / `src` は、本体のページと同じく相対パスで、`public/` 内に実在する先を指す | `test_links_are_relative_and_resolve`（`tests/test_example_sessions.py`） |

## セッションから Issue とリポへのリンク

| 保証 | 対応テスト |
|---|---|
| セッションの `issue` が一覧にある Issue を指せば、先頭の 0 を無視して、その Issue のページへのリンクにする | `test_links_to_issue_and_repo` |
| セッションの `repo` が走査対象のリポなら、リポのページへリンクする | `test_links_to_issue_and_repo` |
| セッションの `issue` が一覧に無い Issue を指すときは、リンクにしない | `test_unlinked_when_issue_or_repo_is_missing` |
| セッションの `repo` が走査対象に無いときは、リンクにしない | `test_unlinked_when_issue_or_repo_is_missing` |

## `ccreel` の失敗と設定の誤り

| 保証 | 対応テスト |
|---|---|
| `show` に失敗したセッションも本文のページを作り、`Could not read this session` を出す | `test_unreadable_session_still_gets_a_page` |
| 一部の config dir で `list` が失敗したときは、警告を出してそこを飛ばし、生成は止めない | `test_build_survives_one_failing_config_dir` |
| すべての config dir で `list` が失敗したとき（`ccreel` が無いときを含む）は、`codeview build` が `error:` と config dir ごとの理由を出して非0で終わり、`public/` を作らない | `test_build_stops_without_ccreel`, `test_build_stops_when_every_list_fails` |
| すべての config dir で `list` が失敗したとき、`codeview publish --if-changed` は push せずに非0で終わる | `test_publish_if_changed_does_not_push_when_list_fails` |
| `list` の1行に `id`・`repo`・`title`・`prompts`・`started`・`updated` のどれかが欠けていれば、その config dir の `list` の失敗として扱う | `test_build_stops_when_a_list_row_lacks_a_field` |
| `list` が成功して0件のときは止めず、セッションのページを書かずに生成を終える | `test_build_with_empty_list_is_not_an_error` |
| `[plugins.sessions]` に `ccreel`・`config_dirs`・`days`・`every_hours` 以外のキーや型の誤りがあれば、`error:` を出して非0で終わる | `test_rejects_bad_options` |

## セッションのページの作り直し

| 保証 | 対応テスト |
|---|---|
| `fingerprint()` は最新の更新時刻を `every_hours` の区間に丸め、区間の中の更新では変わらない | `test_fingerprint_moves_only_across_windows`, `test_fingerprint_follows_every_hours` |
| 2回目の生成では、中身の変わらないセッションの `show` を呼ばずにページを使い回す | `test_second_build_reuses_unchanged_pages` |
| 更新されたセッションのページは作り直す | `test_updated_session_is_rebuilt` |
| Issue の状態が変わったセッションのページは作り直す | `test_issue_link_follows_issue_state` |
| 一覧から消えたセッションのキャッシュは消す | `test_expired_sessions_leave_the_cache` |
| `show` を呼び直すのは、セッションが更新されたときだけである | `test_updated_session_is_rebuilt`, `test_rebuilt_page_reuses_cached_show`, `test_issue_link_follows_issue_state` |
| Issue の状態や本体のコードが変わってページだけを作り直すときは、キャッシュした `show` の出力を使う | `test_rebuilt_page_reuses_cached_show` |
