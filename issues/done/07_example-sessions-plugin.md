## PR記録: feat: ccreel のセッションを載せる拡張を、例として同梱する
issue: 07 (07_example-sessions-plugin.md)
PR: https://github.com/yktsnet/codeview/pull/24

## 変更内容
- `examples/plugins/sessions.py` を追加した。[ccreel](https://github.com/yktsnet/ccreel) の `list --json` / `show --json` から Claude Code のセッションを読み、一覧（`sessions/index.html`）と本文のページを足す拡張の例である。本体のパッケージには入れず、利用者が `codeview.toml` の隣へコピーして使う
- 元にした利用側の実装から `CODEVIEW_LOCAL` による無効化を外し、docstring に使い方と ccreel が要ることを足した
- 設定の誤りは、本体が最初に呼ぶ `css()` の口で検証する。生成を始める前に `error:` で止めるため
- `tests/test_example_sessions.py` を追加した。偽の `ccreel` と、Issue を返す小さな取り込み元をテストの中に置き、`site` フィクスチャで生成器を別プロセスで呼ぶ
- README.md / README.en.md: 冒頭の特長リストに拡張の1行を足した。Extensions 節には「例: Claude Code のセッションを載せる」の小節を足し、設定例を載せた（Issue の指示より広いが、user の依頼で採った）
- docs/guarantees.md に節 5 を足し、「About」の対象に例の拡張を足した。context/structure.md の構成の木に2ファイルを足した
- 本体（`codeview/`）は変えていない

## 保証
| 保証 | テスト（tests/test_example_sessions.py） |
|---|---|
| list の呼び出しと一覧、本文を show から書く | test_list_and_session_pages, test_passes_config_dir_and_period, test_merges_config_dirs |
| 応答の Markdown は生の HTML を出さずに描く / resume の行 | test_reply_markdown_is_safe, test_list_and_session_pages |
| Issue（先頭の 0 を無視）とリポへのリンク、先が無ければリンクにしない | test_links_to_issue_and_repo, test_unlinked_when_issue_or_repo_is_missing |
| show に失敗したセッションのページ | test_unreadable_session_still_gets_a_page |
| ccreel が無い・list の失敗は警告して続ける | test_build_survives_one_failing_config_dir, test_build_survives_missing_ccreel |
| トップの入口と件数、題は出さない | test_top_menu_links_sessions_without_titles |
| 設定の誤り | test_rejects_bad_options |
| 指紋は最新の更新時刻を every_hours の枠に丸める | test_fingerprint_moves_only_across_windows, test_fingerprint_follows_every_hours |
| ページの使い回し・更新・Issue の状態・一覧から消えた分 | test_second_build_reuses_unchanged_pages, test_session_page_side_has_no_counts, test_updated_session_is_rebuilt, test_issue_link_follows_issue_state, test_expired_sessions_leave_the_cache |
| href / src は相対パスで実在する | test_links_are_relative_and_resolve |

維持する保証（台帳 §1）は本体に触れないため、既存のテストがそのまま通る。

## 静的確認結果
- `nix develop -c pytest -q`: 72 passed
- 変更したファイル: README.en.md, README.md, context/structure.md, docs/guarantees.md, examples/plugins/sessions.py, tests/test_example_sessions.py, issues/done/07_example-sessions-plugin.md

## 確認者の判定
| 確認・保証 | 判定 |
|---|---|
| `nix develop -c pytest -q` が通る（72 passed） | 合 |
| 新しいテストは `site` から生成器を別プロセスで呼び、偽の ccreel を使う | 合 |
| list の呼び出し・新しい順・show から本文 | 合 |
| 発言と応答・safe に描く・resume の行 | 合 |
| Issue とリポのリンク・無ければリンクにしない | 合 |
| show の失敗・ccreel が無い・list の失敗で止まらない | 合 |
| トップの入口と件数・題を出さない | 合 |
| 未知のキーと型の誤りで `error:` を出し非0 | 合 |
| fingerprint は最新の更新時刻を every_hours の枠に丸める | 合 |
| 使い回し・作り直し・キャッシュの削除 | 合 |
| href / src が相対で実在する先を指す | 合 |
| 本体の台帳 §1 の維持 | 合 |
| `docs/guarantees.md` の更新 | 合 |

---

## ccreel のセッションを載せる拡張を、例として同梱する
id: 07
branch-slug: example-sessions-plugin
status: close
type: feat
対象: examples/plugins/sessions.py (新規), tests/test_example_sessions.py (新規), README.md, README.en.md, docs/guarantees.md, context/structure.md
内容: 拡張の口の実例として、Claude Code のセッションを [ccreel](https://github.com/yktsnet/ccreel) の JSON 出力から読み、一覧と本文のページを足す拡張を `examples/plugins/` に置く。README の Extensions 節から1行で案内し、読者が自分の設定の隣へ写して試せるようにする。
対象外: 本体（`codeview/` 配下）の変更。パッケージへの同梱（`codeview.contrib` のような import できる形）。ccreel 側の README への言及。非公開の利用側のリポが持つ写しを、この例へ切り替えること
仮定: 例は本体のパッケージに入れず、利用者が `codeview.toml` の隣へ写して使う（拡張の口は公開 API だが、例の中身は約束にしない）。元にする実装が持つ環境変数 `CODEVIEW_LOCAL` による無効化は、利用側の運用の都合なので例からは外す
確認: `nix develop -c pytest -q` が通る。新しいテストは本体のテストと同じく、`site` フィクスチャで生成器を別プロセスで呼び、偽の `ccreel` を PATH かオプションで渡して確かめる（実物の ccreel・実際の履歴は使わない）
人が見るもの: なし

---

### 保証
- 新たに宣言する保証（例の拡張 `examples/plugins/sessions.py`）:
  - `[plugins.sessions]` の `config_dirs` ごとに `ccreel list --json --limit 0 --since <days>d --config-dir <dir>` を呼び、全部をまとめて新しい順に `public/sessions/index.html` へ一覧を書く。各セッションの本文を `ccreel show <id> --json` から `public/sessions/<id>.html` に書く
  - 本文のページには発言と応答のテキストを出し、応答の Markdown は safe に描く（生の HTML・`<script>` を出さない）。`ccreel resume <id>` の行を出す
  - セッションの `issue` が一覧にある Issue のページを指せば、先頭の 0 を無視してリンクにする。`repo` が走査対象のリポならリポのページへリンクする。どちらも無ければリンクにしない
  - `show` に失敗したセッションも本文のページは作り、`Could not read this session` を出す。`ccreel` が無い・ある config dir の `list` が失敗したときは警告を出して飛ばし、生成は止めない
  - トップの左メニューに `sessions` への入口と件数を出し、トップにセッションの題は出さない
  - `ccreel`・`config_dirs`・`days`・`every_hours` 以外のキーや、型の誤りは `error:` を出して非0で終わる
  - `fingerprint()` は最新の更新時刻を `every_hours` の枠に丸め、枠の中の更新では変わらない
  - 2回目の生成では、中身の変わらないセッションの `show` を呼ばずにページを使い回し、更新されたセッション・Issue の状態が変わったセッションは作り直す。一覧から消えたセッションの写しは消す
  - 生成したページの `href` / `src` は、本体のページと同じく相対パスで、`public/` 内に実在する先を指す
- 維持する保証: 台帳 §1 の「拡張を設定しなければ、`functions/` には `_middleware.js` だけを書き、トップはリポの一覧と件数だけになる」「読み込めない拡張を設定したときは、そのモジュール名を出して非0で終わる」「本体が書くページの `href` / `src` は相対パスで、実在するファイルを指す」。本体に触れないので、既存のテストはそのまま通る

### 元にする実装

非公開の利用側のリポに、同じ拡張とテストがある（`plugins/sessions.py` 503行・`tests/test_sessions.py` 279行）。相談者が中身を確かめ、ホスト名・ユーザー名などの実値が無いことを見た。実行者はその場所を user に尋ね、写してから次を直す。

- `CODEVIEW_LOCAL`（`LOCAL_ENV`・`_local()`）と、それに関わる分岐・テスト（`test_local_build_has_no_sessions`）を外す
- モジュールの docstring に、`codeview.toml` の隣へ写して `[plugins] modules = ["sessions"]` に挙げる使い方と、ccreel が要ることを足す
- テストは元のテストの `FAKE_CCREEL`（引数を `calls.log` に残す偽のコマンド）と `SESSIONS` の作りを踏襲する。元のテストは利用側の別の拡張（`issue_files`）が書く Issue のページを前提にしているので、このリポでは `tests/test_plugins.py` の `SOURCE` と同じく、Issue を返す小さな取り込み元をテストの中に置いて代える。拡張は `examples/plugins/sessions.py` を設定の隣へ写して読ませる

### README.md / README.en.md

`## Extensions` の表の下に1〜2文で、実例として `examples/plugins/sessions.py` があり、ccreel の `list --json` / `show --json` からセッションのページを足すことを書く。ccreel へはリンクを張る。日本語版と英語版で同じ内容にする。

### docs/guarantees.md

`examples/plugins/sessions.py` の節を足し、上の新たに宣言する保証と対応テストの表を載せる。「About」の対象に例の拡張を足す。

### context/structure.md

構成の木に `examples/plugins/sessions.py` と `tests/test_example_sessions.py` を足す。
