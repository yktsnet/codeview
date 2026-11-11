# incremental

## `build --incremental` が作り直すリポ

| 保証 | 対応テスト |
|---|---|
| `build --incremental` は、前回の `--incremental` から入力が変わったリポだけを作り直す | `test_incremental_build_matches_full_build`, `test_incremental_build_copies_images_like_full_build` |
| `build --incremental` は、Markdown が GitHub の URL で指す他のリポが変わったとき、指している側のリポも作り直す | `test_incremental_build_matches_full_build` |
| `build --incremental` は、リポ単位の設定（`[scan.repos]`）が変わったリポを作り直す | `test_repo_scan_change_rebuilds_incrementally` |
| `build --incremental` は、拡張が返した Issue の `targets` が変われば、リポの HEAD が同じでも、そのリポのページを作り直す | `test_incremental_build_follows_issue_targets` |
| `build --incremental` は、リポの置き場所が変わったリポを作り直す | `test_incremental_build_follows_repo_location` |
| `build --incremental` は、リポの属するアカウントが変わったリポを作り直す | `test_incremental_build_follows_account` |
| `build --incremental` は、本体のコードが変わったとき、すべてのリポを作り直す | `test_incremental_build_follows_code` |
| `build --incremental` は、`[scan.repos]` 以外の設定が変わったとき、すべてのリポを作り直す | `test_incremental_build_follows_other_config` |
| `build --incremental` は、Issue の一覧が変わったとき、何も書かずには終わらない | `test_incremental_build_follows_issue_list` |

## `build --incremental` の出力

| 保証 | 対応テスト |
|---|---|
| `build --incremental` の出力は、付けずに作り直したものと同じになる | `test_incremental_build_matches_full_build`, `test_incremental_build_copies_images_like_full_build`, `test_repo_scan_change_rebuilds_incrementally` |
| `build --incremental` は消えたリポのページを残さない | `test_incremental_build_matches_full_build` |
| `build --incremental` の記録は `public/` の外に置く | `test_incremental_build_skips_when_nothing_changed` |

## `build --incremental` の見送りと使い回し

| 保証 | 対応テスト |
|---|---|
| `build --incremental` は、リポ・Issue・拡張の `fingerprint()` のどれも変わっていなければ、何も書かずに終わる | `test_incremental_build_skips_when_nothing_changed` |
| `build --incremental` は、拡張の `fingerprint()` だけが変わったとき、リポのページを使い回す | `test_incremental_build_follows_plugin_fingerprint` |
| `build --incremental` は、拡張の `fingerprint()` だけが変わったとき、拡張のページを書き直す | `test_incremental_build_follows_plugin_fingerprint` |
