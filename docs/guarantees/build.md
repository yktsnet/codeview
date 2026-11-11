# build

## 走査（`[[roots]]`・`[scan]`）

| 保証 | 対応テスト |
|---|---|
| `children` のルートは直下の git リポをすべて走査する | `test_scans_children_and_skips` |
| 走査したリポは HEAD にあるファイルをページにする | `test_scans_children_and_skips` |
| トップには、走査したリポへのリンクが並ぶ | `test_scans_children_and_skips` |
| `exclude_prefixes` に前方一致するパスはページにしない | `test_scans_children_and_skips` |
| `skip_exts` の拡張子のファイルはページにしない | `test_scans_children_and_skips` |
| 未コミットのファイルはページにしない | `test_scans_children_and_skips` |
| `skip_dirs` に挙げたディレクトリは走査しない | `test_scans_children_and_skips` |
| `.git` がファイルであるディレクトリ（worktree）は走査しない | `test_scans_children_and_skips` |
| `path` のルートはそのリポ1つだけを走査する | `test_scans_single_repo_path` |
| `[scan.repos."<slug>"]` に書いた `skip_exts` と `exclude_prefixes` は、その slug のリポにだけ、全体の `[scan]` の値に足して適用される | `test_repo_scan_adds_to_global_for_that_repo_only` |

## トップと出力のファイル

| 保証 | 対応テスト |
|---|---|
| トップの左上には、生成した時刻を `built <time data-ts>` で出す | `test_index_shows_build_time_only_on_top` |
| 生成した時刻は、`CODEVIEW_BUILT_AT` があればその値にする | `test_index_shows_build_time_only_on_top` |
| 生成した時刻は、`SOURCE_DATE_EPOCH` から決めない | `test_build_time_ignores_source_date_epoch` |
| 生成した時刻の、JavaScript が無いときに読める文字は `YYYY-MM-DD HH:MM` で、JavaScript があれば相対時刻に書き換える | `test_index_shows_build_time_only_on_top` |
| 生成した時刻はトップ以外のページに出さない | `test_index_shows_build_time_only_on_top` |
| 拡張を設定しなければ、`functions/` には `_middleware.js` だけを書く | `test_no_plugins_means_plain_top` |
| 拡張を設定しなければ、トップはリポの一覧と件数だけになる | `test_no_plugins_means_plain_top` |
| `functions/_middleware.js` は、ホストが `*.pages.dev` のリクエストに 404 を返す | `test_middleware_blocks_pages_dev` |

## ディレクトリのページと左の一覧

| 保証 | 対応テスト |
|---|---|
| README のあるディレクトリのページには、一覧の下に README を描く | `test_readme_on_directory_page` |
| 直下にファイルが無いディレクトリのページには、案内文を出す | `test_guide_on_directory_page_without_files` |
| README の無いディレクトリのページには、一覧の先頭のファイルを README と同じ位置に描く | `test_readme_on_directory_page` |
| 左の一覧で、中身がディレクトリ1つだけのディレクトリは、その子のディレクトリと連ねて `a/b/c` の1行にまとめる | `test_dir_only_chains_collapse_into_one_row` |
| 左の一覧のディレクトリの連なりは、中身がディレクトリ1つだけでなくなるところで止まる | `test_dir_only_chains_collapse_into_one_row` |
| 左の一覧のまとめた行は連なりの最も深いディレクトリのページへリンクする | `test_dir_only_chains_collapse_into_one_row` |
| 左の一覧のまとめた行の件数は連なりの最も深いディレクトリの下のファイル数である | `test_dir_only_chains_collapse_into_one_row` |
| まとめた途中のディレクトリ（`a/`、`a/b/`）のページも書く | `test_dir_only_chains_collapse_into_one_row` |
| パンくずはまとめた途中のディレクトリへリンクする | `test_dir_only_chains_collapse_into_one_row` |

## ファイルのページ

| 保証 | 対応テスト |
|---|---|
| ファイルのページはヘッダに行数と（ハイライトできれば）言語を出す | `test_file_page_navigation` |
| ファイルのページは本文側にトップからのパンくずを置く | `test_file_page_navigation` |
| ファイルのページは同じディレクトリの前後のファイル（左の一覧と同じ並び）へのリンクを出す | `test_file_page_navigation` |
| ファイルが1つのディレクトリのファイルのページには、前後のリンクを出さない | `test_file_page_navigation` |
| ファイルのページはヘッダの「行数 · サイズ」に続けて、そのファイルに触れた最後のコミットの日時を出す | `test_file_header_shows_last_modified_not_in_listing` |
| ファイルのページのヘッダに静的に書く日付は、生成時の現在時刻に左右されない | `test_file_header_shows_last_modified_not_in_listing` |
| ファイルのページのヘッダの日時は、`<time>` の `data-ts` に epoch 秒を持ち、JavaScript があれば相対時刻に書き換える | `test_file_header_shows_last_modified_not_in_listing` |
| 左の一覧とディレクトリのページには、日付を出さない | `test_file_header_shows_last_modified_not_in_listing` |
| Markdown のページは、見出し（h1〜h3、表題1つの h1 を除く）が4つ以上あれば、先頭に畳める目次を出す | `test_long_markdown_gets_toc` |
| Mermaid の図を含む Markdown のページは、外部のホストからスクリプトを読まない | `test_mermaid_page_loads_only_bundled_script` |
| Mermaid の図を含む Markdown のページが読むスクリプトは、`public/` に書き出したファイルである | `test_mermaid_page_loads_only_bundled_script` |

## 画像と HTML のファイル

| 保証 | 対応テスト |
|---|---|
| 対象の拡張子（`.png` `.jpg` `.jpeg` `.gif` `.webp` `.ico` `.svg`）の画像のうち、除外していない 5 MiB 以下のものは、`public/<slug>/<リポ内パス>` にそのままコピーする | `test_images_are_copied_and_shown` |
| 除外した画像と 5 MiB を超える画像はコピーしない | `test_images_are_copied_and_shown` |
| 画像ファイルのページはその画像を `<img>` で表示する | `test_images_are_copied_and_shown` |
| 5 MiB を超える画像のページは画像を出さず `Too large to display` を出す | `test_images_are_copied_and_shown` |
| `.svg` のページはコードとして描く | `test_images_are_copied_and_shown`, `test_html_file_page_renders_in_sandboxed_iframe` |
| `.html` と `.htm` のファイルページは、ファイルの中身をそのまま `srcdoc` に入れた `<iframe>` を本文に出す | `test_html_file_page_renders_in_sandboxed_iframe` |
| `.html` と `.htm` のファイルページの iframe の `sandbox` 属性は、`allow-scripts` を含む | `test_html_file_page_renders_in_sandboxed_iframe` |
| `.html` と `.htm` のファイルページの iframe の `sandbox` 属性は、`allow-same-origin` を含まない | `test_html_file_page_renders_in_sandboxed_iframe` |
| `.html` と `.htm` のファイルページでは、ハイライトしたソースも JavaScript なしで（`<details>` で）読める | `test_html_file_page_renders_in_sandboxed_iframe` |
| `.html` と `.htm` のファイルページのヘッダのメタ情報と Copy file は、ほかのコードのページと同じで、Copy file が写すのはソースである | `test_html_file_page_renders_in_sandboxed_iframe` |
| 512 KiB を超える `.html`・`.htm` のファイルページは、iframe を出さず `Too large to display` を出す | `test_html_file_page_renders_in_sandboxed_iframe` |
| バイナリの `.html`・`.htm` のファイルページは、iframe を出さず `Binary` を出す | `test_html_file_page_renders_in_sandboxed_iframe` |
