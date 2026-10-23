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
