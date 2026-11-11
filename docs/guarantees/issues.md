# issues

## GitHub の Issue のページ

| 保証 | 対応テスト |
|---|---|
| GitHub の Issue のページには、本文とコメントを出す | `test_github_issue_page_comments_oldest_first` |
| GitHub の Issue のページのコメントは、古い順に並ぶ | `test_github_issue_page_comments_oldest_first` |
| GitHub の Issue のページには、GitHub の URL へのリンクを出さない | `test_github_issue_page_comments_oldest_first`, `test_github_urls_in_issue_body_point_to_generated_pages` |
| GitHub の Issue の本文の GitHub の URL は、生成したページに対応するとき（Markdown 本文と同じ規則。Issue は同じアカウントのものだけ）、そのページへのリンクになる | `test_github_urls_in_issue_body_point_to_generated_pages` |
| GitHub の Issue の本文とコメントに含まれる生の HTML は、タグとして出さずエスケープする | `test_github_raw_html_is_escaped` |
| Issue のページの戻るリンク・左の一覧・CSS は、相対パスで `public/` 内の実在するファイルを指す | `test_issue_pages_link_relatively` |

## GitHub の Issue の取得と一覧

| 保証 | 対応テスト |
|---|---|
| あるリポの Issue の取得に失敗しても build は止まらず、一覧に `fetch failed: <リポ>` を出す | `test_github_fetch_failure_does_not_stop_build` |
| Issue の取得に失敗したリポは、標準エラーにも出す | `test_github_fetch_failure_does_not_stop_build` |
| あるリポの Issue の取得に失敗しても、他のリポの Issue は一覧に出る | `test_github_fetch_failure_does_not_stop_build` |
| Issue の一覧はアカウントごとに分ける | `test_two_accounts_use_their_own_gh_config` |
| `gh_config_dir` を設定したアカウントのリポは、その config dir で `gh` を呼ぶ | `test_two_accounts_use_their_own_gh_config` |
