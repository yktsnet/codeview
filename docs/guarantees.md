# Guarantee Ledger

## Guarantees

### 1. `tests/test_build.py` — codeview build (CLI)

- `children` のルートでは直下の git リポをすべて走査し、各リポの HEAD にあるファイルをページにする。トップにはリポへのリンクが並ぶ
- `exclude_prefixes` に前方一致するパス、`skip_exts` の拡張子、未コミットのファイルはページにしない
- `skip_dirs` に挙げたディレクトリと、`.git` がファイルであるディレクトリ（worktree）は走査しない
- `path` のルートでは、そのリポ1つだけを走査する
- README を持つディレクトリのページには、一覧の下に README を描く。README の無いディレクトリは案内文を出す
- 拡張を設定しなければ、`functions/` には `_middleware.js` だけを書き、トップはリポの一覧と件数だけになる
- 設定ファイルが無いときは `error:` を出して非0で終わり、`public/` を作らない
- 設定の書式が誤っているときは `error:` を出して非0で終わり、`public/` を作らない
- 読み込めない拡張を設定したときは、そのモジュール名を出して非0で終わり、`public/` を作らない
- `functions/_middleware.js` は、ホストが `*.pages.dev` のリクエストに 404 を返す

| 保証（要約） | 対応テスト |
|---|---|
| `children` の走査とトップのリンク | `test_scans_children_and_skips` |
| 除外パス・拡張子・未コミットを出さない | `test_scans_children_and_skips` |
| `skip_dirs` と worktree を走査しない | `test_scans_children_and_skips` |
| `path` は1リポだけ | `test_scans_single_repo_path` |
| ディレクトリページの README | `test_readme_on_directory_page` |
| 拡張なしの出力 | `test_no_plugins_means_plain_top` |
| 設定ファイルが無い | `test_missing_config_stops_before_build` |
| 設定の書式誤り | `test_broken_config_stops_before_build` |
| 読み込めない拡張 | `test_unknown_plugin_stops_before_build` |
| `*.pages.dev` を 404 で塞ぐ | `test_middleware_blocks_pages_dev` |

### 2. `tests/test_issues.py` — codeview build (GitHub の Issue)

- GitHub の Issue のページには本文とコメントを出し、コメントは古い順に並べる。GitHub の URL へのリンクは出さない
- GitHub の Issue の本文とコメントに含まれる生の HTML は、タグとして出さずエスケープする
- あるリポの Issue の取得に失敗しても build は止まらない。一覧に `fetch failed: <リポ>` を出し、標準エラーにも出す。他のリポの Issue は出る
- アカウントごとに Issue の一覧を分け、`gh_config_dir` を設定したアカウントのリポは、その config dir で `gh` を呼ぶ

| 保証（要約） | 対応テスト |
|---|---|
| 本文とコメント（古い順） | `test_github_issue_page_comments_oldest_first` |
| 生の HTML のエスケープ | `test_github_raw_html_is_escaped` |
| 取得の失敗で止まらない | `test_github_fetch_failure_does_not_stop_build` |
| アカウントごとの一覧と `gh_config_dir` | `test_two_accounts_use_their_own_gh_config` |

### 3. `tests/test_plugins.py` — 拡張と設定 (`issues()` / `[[accounts]]`)

- 設定ファイルの隣に置いた拡張モジュールを `issues` に挙げると、その `issues(ctx, account, repos)` が返す Issue を一覧とページに出す。`[plugins.<名前>]` の表は `ctx.options` で読める
- 拡張が返した Issue の `waits` は、一覧にある Issue へのリンクになる。一覧に無い先への依存は出さない
- 拡張が `trusted` を立てなければ、Issue の本文の HTML はエスケープする
- 拡張が返した Issue の `targets` に挙げたファイルのページには、その Issue へのリンクを出す
- アカウントの `issues` に `[plugins] modules` に無いモジュールを挙げると、`error:` を出して非0で終わり、`public/` を作らない
- `issues` に挙げた拡張が `issues()` を持たなければ、`no issues()` を出して非0で終わり、`public/` を作らない
- `[[accounts]]` が3つ以上なら、`1 to 2` を含むエラーで非0で終わり、`public/` を作らない
- `issues` が `github` でないアカウントに `gh_config_dir` を書くと、非0で終わる

| 保証（要約） | 対応テスト |
|---|---|
| 設定の隣の拡張と `ctx.options` | `test_issue_source_next_to_config` |
| `waits` のリンクと一覧外の依存 | `test_issue_source_next_to_config` |
| `trusted` でない本文のエスケープ | `test_issue_source_next_to_config` |
| `targets` のファイルから Issue へのリンク | `test_issue_source_next_to_config` |
| 未登録の取り込み元 | `test_issue_source_must_be_listed_plugin` |
| `issues()` を持たない拡張 | `test_issue_source_needs_issues_function` |
| アカウントは2つまで | `test_at_most_two_accounts` |
| `gh_config_dir` は GitHub だけ | `test_gh_config_dir_only_for_github` |

### 4. `tests/test_publish.py` — codeview publish (変更の検出と出力先)

- 走査対象にも Issue にも動きが無ければ、変更なしと判定する
- 走査対象のリポに新しいコミットがあれば、変更ありと判定する
- GitHub の Issue が更新されれば、変更ありと判定する
- 走査対象のリポの未コミットの変更は、変更として扱わない
- `publish --dry-run` は、設定ファイルのあるリポの直下に `public/` と `functions/` を書き、push せずに終わる
- `publish` は配信ブランチを親を持たない単一コミットとして push し、その木には `public/` と `functions/` だけを載せる
- `publish --if-changed` は、前回の配信から変更が無ければ push せずに終わる

| 保証（要約） | 対応テスト |
|---|---|
| 動きが無ければ変更なし | `test_fingerprint_stable_without_changes` |
| 新しいコミット | `test_fingerprint_changes_with_head` |
| Issue の更新 | `test_fingerprint_changes_with_github_issue_update` |
| 未コミットは無視 | `test_fingerprint_ignores_uncommitted` |
| `--dry-run` の出力先 | `test_publish_writes_into_the_config_repo` |
| 単一コミットに生成物だけ | `test_publish_pushes_single_commit_of_assets` |
| `--if-changed` の見送り | `test_publish_if_changed_skips_without_changes` |

## Gaps

以下は保証すべきと思われるが、対応するテストが無い。

- 生成物が 20,000 ファイルを超えたとき、`publish` が push せずに非0で終わること。見本に 2 万件のファイルを作るとテストが重くなりすぎるため見送った

## About

対象は `codeview` コマンド（`build` / `publish`）の外から見える振る舞い、`codeview.toml` の検証、拡張の口。`serve`・`cf-setup`・`cf-status` とページの見た目は対象外。**ここに載っていない振る舞いは約束ではなく、予告なく変わりうる。** 地位は design-decisions.md 相当のドキュメントと同格。
