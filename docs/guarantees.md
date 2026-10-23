# Guarantee Ledger

## Guarantees

### 1. `tests/test_build.py` — codeview build (CLI)

- `children` のルートでは直下の git リポをすべて走査し、各リポの HEAD にあるファイルをページにする。トップにはリポへのリンクが並ぶ
- `exclude_prefixes` に前方一致するパス、`skip_exts` の拡張子、未コミットのファイルはページにしない
- `[scan.repos."<slug>"]` に書いた `skip_exts` と `exclude_prefixes` は、その slug のリポにだけ、全体の `[scan]` の値に足して効く。他のリポのページは変わらない
- リポ単位で除外したファイルも、全体で除外したファイルと同じく、Markdown のリンク先にならない（リンクにせず文字だけ残す）
- `[scan.repos."<slug>"]` に `skip_exts` と `exclude_prefixes` 以外のキーがあれば、`error:` を出して非0で終わり、`public/` を作らない
- 走査対象に無い slug を `[scan.repos]` に書いても build は止まらず、その slug を標準エラーに出す
- `skip_dirs` に挙げたディレクトリと、`.git` がファイルであるディレクトリ（worktree）は走査しない
- `path` のルートでは、そのリポ1つだけを走査する
- README を持つディレクトリのページには、一覧の下に README を描く。README の無いディレクトリは案内文を出す
- 拡張を設定しなければ、`functions/` には `_middleware.js` だけを書き、トップはリポの一覧と件数だけになる
- 設定ファイルが無いときは `error:` を出して非0で終わり、`public/` を作らない
- 設定の書式が誤っているときは `error:` を出して非0で終わり、`public/` を作らない
- 読み込めない拡張を設定したときは、そのモジュール名を出して非0で終わり、`public/` を作らない
- `functions/_middleware.js` は、ホストが `*.pages.dev` のリクエストに 404 を返す
- ファイルのページは、ヘッダに行数と（ハイライトできれば）言語を出し、本文側にトップからのパンくずを置き、同じディレクトリの前後のファイル（左の一覧と同じ並び）へのリンクを出す。ファイルが1つのディレクトリでは前後を出さない
- Markdown のページは、見出し（h1〜h3、表題1つの h1 を除く）が4つ以上あれば、先頭に畳める目次を出す
- Mermaid の図を含む Markdown のページは、外部のホストからスクリプトを読まない。読むスクリプトは `public/` に書き出したファイルである
- 本体が書くページの `href` / `src` は、外部 URL・ページ内アンカーを除いて `/` で始まらない相対パスである
- その相対パスは、ページの位置から解決すると `public/` 内に実在するファイルを指す（ディレクトリへのリンクは `index.html` まで書く）
- 拡張の `side()` / `home()` が返す HTML 内の `/` 始まりのリンクも、同じく相対パスに直る
- リポのファイルを描いた Markdown の本文で、リポ内のファイルを指す相対リンクは、そのファイルのページへのリンクになる。`#` 以降のアンカーは残す
- リポ内のディレクトリを指すリンクは、そのディレクトリのページ（`index.html`）へのリンクになる
- `/` 始まりのリンクは、リポのルートを基準に解決する
- 上の解決は、ファイルページの本文でも、ディレクトリのページに埋め込んだ README でも、同じ先を指す（基準になるのは `.md` の位置であって、表示するページの位置ではない）
- リンク先がリポ内にページを持たないとき（HEAD に無い・除外した・リポの外）は、リンクにせず文字だけを残す
- 本文にある走査対象のリポの GitHub の URL は、生成したページに対応すれば、そのページへのリンクになる。リポのトップはリポのページ、`blob` / `tree` は、ref が HEAD のブランチ名と一致すれば、そのファイルやディレクトリのページになる。`#` 以降のアンカーは残す
- GitHub の Issue の URL は、取り込んだ Issue で、読んでいる文書と同じアカウントのものだけ、その Issue のページへのリンクになる
- 対応するページが無い GitHub の URL（別の ref・HEAD に無いパス・取り込んでいない Issue・別のアカウントの Issue・Pull Request など）は、外部 URL のまま残す
- 対象の拡張子（`.png` `.jpg` `.jpeg` `.gif` `.webp` `.ico` `.svg`）の画像のうち、除外していない 5 MiB 以下のものは、`public/<slug>/<リポ内パス>` にそのままコピーする。除外した画像と 5 MiB を超える画像はコピーしない
- 画像ファイルのページは、その画像を `<img>` で表示する（5 MiB を超えるときは `Too large to display`）。`.svg` のページはコードとして描く
- リポのファイルを描いた Markdown の本文で、リポ内のコピーした画像を指す `![]()` と生の HTML の `<img>` の src は、その画像への相対パスになる。解決の基準と `/` 始まりの扱いはリンクと同じで、ファイルページでも埋め込み README でも同じ先を指す
- 指す先の画像が無い（HEAD に無い・除外した・5 MiB 超・リポの外）`![]()` と `<img>`、およびリポ外の URL を指すものは、画像にせず `[alt]` の文字にする
- `--incremental` を付けると、前回の `--incremental` から入力が変わったリポだけを作り直す。出力は、付けずに作り直したものと同じになる。入力には、リポの HEAD・置き場所・アカウント・そのリポのファイルを対象に挙げた Issue・本体と設定のほか、Markdown が GitHub の URL を含むリポでは他のリポの中身と Issue の一覧も含む
- `--incremental` で、どのリポも Issue も変わっていなければ、何も書かずに終わる。記録は `public/` の外に置く

| 保証（要約） | 対応テスト |
|---|---|
| `children` の走査とトップのリンク | `test_scans_children_and_skips` |
| 除外パス・拡張子・未コミットを出さない | `test_scans_children_and_skips` |
| リポ単位の除外は、そのリポにだけ全体の値へ足して効く（除外したファイルはリンク先にならない） | `test_repo_scan_adds_to_global_for_that_repo_only` |
| リポ単位で除外したファイルは GitHub の URL のリンク先にならない | `test_repo_scan_excluded_file_is_not_a_github_link_target` |
| リポ単位の設定の未知のキー・表でない値 | `test_repo_scan_unknown_key_stops_before_build`、`test_repo_scan_must_be_a_table_per_repo` |
| 走査対象に無い slug は警告だけ | `test_repo_scan_unknown_slug_warns_and_continues` |
| リポ単位の設定を変えると `--incremental` も作り直す | `test_repo_scan_change_rebuilds_incrementally` |
| `skip_dirs` と worktree を走査しない | `test_scans_children_and_skips` |
| `path` は1リポだけ | `test_scans_single_repo_path` |
| ディレクトリページの README | `test_readme_on_directory_page` |
| 拡張なしの出力 | `test_no_plugins_means_plain_top` |
| ファイルページの行数・言語・パンくず・前後のリンク | `test_file_page_navigation` |
| 長い Markdown の目次 | `test_long_markdown_gets_toc` |
| Mermaid の図のページは同梱のスクリプトだけを読む | `test_mermaid_page_loads_only_bundled_script` |
| リンクは相対パスで、実在するファイルを指す | `test_links_are_relative_and_resolve` |
| 拡張の `side()` / `home()` のリンクも相対パスに直る | `test_extension_home_and_side_links_are_relative` |
| Markdown 本文のリポ内リンクは生成したページを指す（ファイル・ディレクトリ・`/` 始まり・アンカー・ファイルページと埋め込み README の一致） | `test_markdown_links_point_to_generated_pages` |
| サブディレクトリの `.md` でも、リンクの解決の基準は `.md` の位置で、ファイルページと埋め込み README が同じ先を指す | `test_markdown_links_resolve_from_md_location_in_subdirectory` |
| ページの無い先へのリンクは文字になる | `test_markdown_links_point_to_generated_pages` |
| GitHub の URL は、対応するページがあればそこへ向き、無ければ外部 URL のまま残る | `test_github_urls_point_to_generated_pages` |
| `--incremental` の出力は全体の作り直しと同じ（他のリポの変化・消えたリポを含む） | `test_incremental_build_matches_full_build` |
| `--incremental` は変化が無ければ何も書かない | `test_incremental_build_skips_when_nothing_changed` |
| 画像はコピーされ、画像ファイルのページと Markdown 本文（`![]()` と生の `<img>`）に表示される。指す先の無い画像・リポ外の画像は文字になる | `test_images_are_copied_and_shown` |
| `--incremental` でも画像は全体の作り直しと同じ出力になる | `test_incremental_build_copies_images_like_full_build` |
| 設定ファイルが無い | `test_missing_config_stops_before_build` |
| 設定の書式誤り | `test_broken_config_stops_before_build` |
| 読み込めない拡張 | `test_unknown_plugin_stops_before_build` |
| `*.pages.dev` を 404 で塞ぐ | `test_middleware_blocks_pages_dev` |

### 2. `tests/test_issues.py` — codeview build (GitHub の Issue)

- GitHub の Issue のページには本文とコメントを出し、コメントは古い順に並べる。GitHub の URL へのリンクは出さない
- ただし本文の GitHub の URL が生成したページに対応するとき（台帳 1 と同じ規則。Issue は同じアカウントのものだけ）は、そのページへのリンクにする
- GitHub の Issue の本文とコメントに含まれる生の HTML は、タグとして出さずエスケープする
- あるリポの Issue の取得に失敗しても build は止まらない。一覧に `fetch failed: <リポ>` を出し、標準エラーにも出す。他のリポの Issue は出る
- アカウントごとに Issue の一覧を分け、`gh_config_dir` を設定したアカウントのリポは、その config dir で `gh` を呼ぶ
- Issue のページの戻るリンク・左の一覧・CSS は、相対パスで `public/` 内の実在するファイルを指す

| 保証（要約） | 対応テスト |
|---|---|
| 本文とコメント（古い順） | `test_github_issue_page_comments_oldest_first` |
| Issue のページのリンクは相対パス | `test_issue_pages_link_relatively` |
| 本文の GitHub の URL は、対応するページがあればそこへ向く | `test_github_urls_in_issue_body_point_to_generated_pages` |
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
- `--incremental` では、拡張が返した Issue の `targets` が変われば、リポの HEAD が同じでも、そのリポのページを作り直す

| 保証（要約） | 対応テスト |
|---|---|
| 設定の隣の拡張と `ctx.options` | `test_issue_source_next_to_config` |
| `waits` のリンクと一覧外の依存 | `test_issue_source_next_to_config` |
| `--incremental` は Issue の対象の変化でもリポを作り直す | `test_incremental_build_follows_issue_targets` |
| `trusted` でない本文のエスケープ | `test_issue_source_next_to_config` |
| `targets` のファイルから Issue へのリンク | `test_issue_source_next_to_config` |
| 未登録の取り込み元 | `test_issue_source_must_be_listed_plugin` |
| `issues()` を持たない拡張 | `test_issue_source_needs_issues_function` |
| アカウントは2つまで | `test_at_most_two_accounts` |
| `gh_config_dir` は GitHub だけ | `test_gh_config_dir_only_for_github` |

### 4. `tests/test_publish.py` — codeview publish (変更の検出と出力先)

- 走査対象に動きが無ければ、変更なしと判定する
- 走査対象のリポに新しいコミットがあれば、変更ありと判定する
- GitHub の Issue だけが更新されても、変更なしと判定する。指紋を取るときに GitHub へ問い合わせない
- 走査対象のリポの未コミットの変更は、変更として扱わない
- `publish --dry-run` は、設定ファイルのあるリポの直下に `public/` と `functions/` を書き、push せずに終わる
- `publish` は配信ブランチを親を持たない単一コミットとして push し、その木には `public/` と `functions/` だけを載せる
- `publish --if-changed` は、前回の配信から変更が無ければ push せずに終わる。Issue だけの更新でも push しない
- `check_every_hours` を持つアカウントのリポの変化は、前回そのアカウントを見てから間隔が経つまで見ない。定期実行の起動のずれを見込み、間隔より5分短い時間が経っていれば見て、変化があれば配信する。間隔の無いアカウントの変化は、次の実行で配信する
- 旧形式の状態ファイルは無いものとして扱い、配信する
- `check_every_hours` は正の整数だけを受け付け、それ以外は設定の誤りとして止める

| 保証（要約） | 対応テスト |
|---|---|
| 動きが無ければ変更なし | `test_fingerprint_stable_without_changes` |
| 新しいコミット | `test_fingerprint_changes_with_head` |
| Issue の更新は無視 | `test_fingerprint_ignores_github_issue_update` |
| 未コミットは無視 | `test_fingerprint_ignores_uncommitted` |
| `--dry-run` の出力先 | `test_publish_writes_into_the_config_repo` |
| 単一コミットに生成物だけ | `test_publish_pushes_single_commit_of_assets` |
| `--if-changed` の見送り | `test_publish_if_changed_skips_without_changes` |
| Issue だけの更新は見送り | `test_publish_if_changed_skips_issue_only_change` |
| アカウントごとの間隔 | `test_publish_checks_account_at_its_interval` |
| 旧形式の状態 | `test_publish_if_changed_republishes_over_old_state` |
| 間隔の値の検証 | `test_check_every_hours_must_be_positive_integer` |

### 5. `tests/test_example_sessions.py` — 例の拡張 `examples/plugins/sessions.py`

- `[plugins.sessions]` の `config_dirs` ごとに `ccreel list --json --limit 0 --since <days>d --config-dir <dir>` を呼び、全部をまとめて新しい順に `public/sessions/index.html` へ一覧を書く。各セッションの本文を `ccreel show <id> --json` から `public/sessions/<id>.html` に書く
- 本文のページには発言と応答のテキストを出し、応答の Markdown は生の HTML・`<script>` を出さずに描く。`ccreel resume <id>` の行を出す
- セッションの `issue` が一覧にある Issue を指せば、先頭の 0 を無視してその Issue のページへのリンクにする。`repo` が走査対象のリポならリポのページへリンクする。どちらも無ければリンクにしない
- `show` に失敗したセッションも本文のページは作り、`Could not read this session` を出す。`ccreel` が無いとき、またはいずれかの config dir で `list` が失敗したときは、警告を出してそこを飛ばし、生成は止めない
- トップの左メニューに `sessions` への入口と件数を出し、トップにセッションの題は出さない
- `ccreel`・`config_dirs`・`days`・`every_hours` 以外のキーや、型の誤りは `error:` を出して非0で終わる
- `fingerprint()` は最新の更新時刻を `every_hours` の枠に丸め、枠の中の更新では変わらない
- 2回目の生成では、中身の変わらないセッションの `show` を呼ばずにページを使い回し、更新されたセッション・Issue の状態が変わったセッションは作り直す。一覧から消えたセッションのキャッシュは消す
- 生成したページの `href` / `src` は、本体のページと同じく相対パスで、`public/` 内に実在する先を指す

| 保証（要約） | 対応テスト |
|---|---|
| `list` の呼び出しと一覧、本文を `show` から書く | `test_list_and_session_pages`、`test_passes_config_dir_and_period`、`test_merges_config_dirs` |
| 応答の Markdown は生の HTML を出さずに描く | `test_reply_markdown_is_safe` |
| `ccreel resume` の行 | `test_list_and_session_pages` |
| Issue（先頭の 0 を無視）とリポへのリンク | `test_links_to_issue_and_repo` |
| 対応する先が無ければリンクにしない | `test_unlinked_when_issue_or_repo_is_missing` |
| `show` に失敗したセッションのページ | `test_unreadable_session_still_gets_a_page` |
| `list` の失敗・`ccreel` が無いときは警告して続ける | `test_build_survives_one_failing_config_dir`、`test_build_survives_missing_ccreel` |
| トップの入口と件数 | `test_top_menu_links_sessions_without_titles` |
| 設定の誤り | `test_rejects_bad_options` |
| 指紋は `every_hours` の枠で動く | `test_fingerprint_moves_only_across_windows` |
| 変わらないセッションはページを使い回す（件数を左に出さないのは、セッションが1本増えても、ほかのページの内容が変わらないようにするため） | `test_second_build_reuses_unchanged_pages`、`test_session_page_side_has_no_counts` |
| 更新されたセッションは作り直す | `test_updated_session_is_rebuilt` |
| Issue の状態が変わったら作り直す | `test_issue_link_follows_issue_state` |
| 一覧から消えたセッションのキャッシュを消す | `test_expired_sessions_leave_the_cache` |
| リンクは相対パスで、実在するファイルを指す | `test_links_are_relative_and_resolve` |

## Gaps

以下は保証すべきと思われるが、対応するテストが無い。

- 生成物が 20,000 ファイルを超えたとき、`publish` が push せずに非0で終わること。見本に 2 万件のファイルを作るとテストが重くなりすぎるため見送った

## About

対象は `codeview` コマンド（`build` / `publish`）の外から見える振る舞い、`codeview.toml` の検証、拡張の口、例の拡張 `examples/plugins/sessions.py`。`serve`・`cf-setup`・`cf-status` とページの見た目は対象外。**ここに載っていない振る舞いは約束ではなく、予告なく変わりうる。**
