# publish

## 変更の判定（ハッシュ）

| 保証 | 対応テスト |
|---|---|
| 走査対象に動きが無ければ、変更なしと判定する | `test_fingerprint_stable_without_changes` |
| 走査対象のリポに新しいコミットがあれば、変更ありと判定する | `test_fingerprint_changes_with_head` |
| GitHub の Issue だけが更新されても、変更なしと判定する | `test_fingerprint_ignores_github_issue_update` |
| 変更の判定のハッシュを取るときに、GitHub へ問い合わせない | `test_fingerprint_ignores_github_issue_update` |
| 走査対象のリポの未コミットの変更は、変更として扱わない | `test_fingerprint_ignores_uncommitted` |

## `publish` の出力と push

| 保証 | 対応テスト |
|---|---|
| `publish --dry-run` は、設定ファイルのあるリポの直下に `public/` と `functions/` を書き、push せずに終わる | `test_publish_writes_into_the_config_repo` |
| `publish` は、配信ブランチを親を持たない単一コミットとして push する | `test_publish_pushes_single_commit_of_assets` |
| `publish` が push するコミットのツリーには、`public/` と `functions/` だけを載せる | `test_publish_pushes_single_commit_of_assets` |
| `publish` は `build --incremental` で生成し、前回の配信から変わったリポだけを作り直して、変わっていないリポのページは使い回す | `test_publish_rebuilds_only_changed_repos` |

## `publish --if-changed` の配信の判断

| 保証 | 対応テスト |
|---|---|
| `publish --if-changed` は、前回の配信から変更が無ければ push せずに終わる | `test_publish_if_changed_skips_without_changes` |
| `publish --if-changed` は Issue だけの更新では push しない | `test_publish_if_changed_skips_issue_only_change` |
| `check_every_hours` を持つアカウントのリポの変化は、前回そのアカウントを見てから間隔が経つまで見ない | `test_publish_checks_account_at_its_interval` |
| `check_every_hours` を持つアカウントは、定期実行の起動のずれを見込み、間隔より5分短い時間が経っていれば見て、変化があれば配信する | `test_publish_checks_account_at_its_interval`, `test_publish_check_allows_five_minutes_of_startup_drift` |
| 間隔の無いアカウントの変化は、次の実行で配信する | `test_publish_checks_account_at_its_interval` |
| 旧形式の状態ファイルは無いものとして扱い、配信する | `test_publish_if_changed_republishes_over_old_state` |
