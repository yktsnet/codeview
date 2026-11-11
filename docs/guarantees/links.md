# links

## 生成したページのリンクの形

| 保証 | 対応テスト |
|---|---|
| 本体が書くページの `href` / `src` は、外部 URL・ページ内アンカーを除いて `/` で始まらない相対パスである | `test_links_are_relative_and_resolve`（`tests/test_build.py`） |
| 本体が書くページの相対パスは、ページの位置から解決すると `public/` 内に実在するファイルを指す（ディレクトリへのリンクは `index.html` まで書く） | `test_links_are_relative_and_resolve`（`tests/test_build.py`） |
| 拡張の `side()` / `home()` が返す HTML 内の `/` 始まりのリンクも、相対パスに直る | `test_extension_home_and_side_links_are_relative` |

## Markdown 本文のリポ内リンク

| 保証 | 対応テスト |
|---|---|
| リポのファイルを描いた Markdown の本文で、リポ内のファイルを指す相対リンクは、そのファイルのページへのリンクになる | `test_markdown_links_point_to_generated_pages` |
| リポ内のファイルを指すリンクの `#` 以降のアンカーは残す | `test_markdown_links_point_to_generated_pages`, `test_markdown_links_resolve_from_md_location_in_subdirectory` |
| リポ内のディレクトリを指すリンクは、そのディレクトリのページ（`index.html`）へのリンクになる | `test_markdown_links_point_to_generated_pages` |
| `/` 始まりのリンクはリポのルートを基準に解決する | `test_markdown_links_point_to_generated_pages`, `test_markdown_links_resolve_from_md_location_in_subdirectory` |
| リンクの解決の基準は `.md` の位置で、ファイルページでも、ディレクトリのページに埋め込んだ README でも、同じ先を指す | `test_markdown_links_point_to_generated_pages`, `test_markdown_links_resolve_from_md_location_in_subdirectory` |
| リンク先がリポ内にページを持たないとき（HEAD に無い・除外した・リポの外）は、リンクにせず文字だけを残す | `test_markdown_links_point_to_generated_pages`, `test_markdown_links_resolve_from_md_location_in_subdirectory` |
| リポ単位で除外したファイルも、全体で除外したファイルと同じく、Markdown のリンク先にならない（リンクにせず文字だけ残す） | `test_repo_scan_adds_to_global_for_that_repo_only` |

## Markdown 本文の GitHub の URL

| 保証 | 対応テスト |
|---|---|
| 走査対象のリポのトップを指す GitHub の URL は、リポのページへのリンクになる | `test_github_urls_point_to_generated_pages` |
| `blob` / `tree` の GitHub の URL は、ref が HEAD のブランチ名と一致すれば、そのファイルやディレクトリのページへのリンクになる | `test_github_urls_point_to_generated_pages` |
| ページへのリンクにした GitHub の URL の `#` 以降のアンカーは残す | `test_github_urls_point_to_generated_pages` |
| GitHub の Issue の URL は、取り込んだ Issue で、読んでいる文書と同じアカウントのものだけ、その Issue のページへのリンクになる | `test_github_urls_point_to_generated_pages` |
| 対応するページが無い GitHub の URL（別の ref・HEAD に無いパス・取り込んでいない Issue・別のアカウントの Issue・Pull Request など）は、外部 URL のまま残す | `test_github_urls_point_to_generated_pages` |
| リポ単位で除外したファイルを指す GitHub の URL は、外部 URL のまま残す | `test_repo_scan_excluded_file_is_not_a_github_link_target` |

## Markdown 本文の画像

| 保証 | 対応テスト |
|---|---|
| リポのファイルを描いた Markdown の本文で、リポ内のコピーした画像を指す `![]()` と生の HTML の `<img>` の src は、その画像への相対パスになる | `test_images_are_copied_and_shown` |
| 画像の src の解決の基準と `/` 始まりの扱いはリンクと同じで、ファイルページでも埋め込み README でも同じ先を指す | `test_images_are_copied_and_shown` |
| 指す先の画像が無い（HEAD に無い・除外した・5 MiB 超・リポの外）`![]()` と `<img>` は、画像にせず `[alt]` の文字にする | `test_images_are_copied_and_shown` |
| リポ外の URL を指す `![]()` と `<img>` は、画像にせず `[alt]` の文字にする | `test_images_are_copied_and_shown` |
