## 例の拡張 sessions は、セッションを1本も読めなければ生成を止める
id: 08
branch-slug: sessions-fail-loud
status: close
type: fix
対象: examples/plugins/sessions.py, tests/test_example_sessions.py, docs/guarantees.md
内容: 例の拡張 `examples/plugins/sessions.py` は、`ccreel` が無いときや、すべての config dir で `list` が失敗したときも、警告を1行出すだけで生成を続ける。定期実行の `PATH` に ccreel が無いと、`publish --if-changed` はセッションのページが無いサイトを黙って配信する。ccreel の `list --json` の形が変わって要る項目が欠けた場合も、同じ結果になる。すべての config dir で読めなかったときは生成を始める前に止め、前回の配信を残す。
対象外: 本体（`codeview/` 配下）の変更。ccreel 側で JSON の形を固定するテスト。`show` の失敗の扱い（今のまま、そのセッションだけ `Could not read this session`）。一部の config dir だけが失敗したときの扱い（今のまま、警告して飛ばす）
仮定: 「止める」は、`codeview build` が `error:` を出して非0で終わり、`public/` に触れないこととする。本体は拡張の `css()` の呼び出しで起きた `PluginError` / `ConfigError` だけを `error:` にして生成前に止めるので、一覧の取得を `css()` の時点で済ませる（設定の検査を `css()` で行っているのと同じ理由）。`publish` は指紋を取る時点で同じ例外が上がり、push せずに非0で終わる（本体を変えないので、こちらは `error:` ではなくトレースバックになってよい）。`list` が成功して0件を返すのは正常で、止めない
確認: `nix develop -c pytest -q` が通る。新しいテストは既存の `tests/test_example_sessions.py` と同じく、`site` フィクスチャで生成器を別プロセスで呼び、偽の `ccreel` で確かめる
人が見るもの: なし

---

### 保証
- 新たに宣言する保証（例の拡張 `examples/plugins/sessions.py`）:
  - `ccreel` が無いとき、またはすべての config dir で `list` が失敗したときは、`codeview build` が `error:` と失敗した理由（config dir と ccreel の標準エラーか例外の文）を出して非0で終わり、`public/` を作らない
  - `list` の1行に `id`・`repo`・`title`・`prompts`・`started`・`updated` のどれかが欠けていれば、その config dir の `list` の失敗として扱う（すべての config dir がそうなら上と同じく止まる）
  - 上の場合、`codeview publish --if-changed` は push せずに非0で終わる
  - `list` が成功して0件のときは止めず、セッションのページを書かずに生成を終える（今の振る舞い）
- 変更する保証（台帳 §5）:
  - 「`ccreel` が無いとき、またはいずれかの config dir で `list` が失敗したときは、警告を出してそこを飛ばし、生成は止めない」を、「一部の config dir で `list` が失敗したときは、警告を出してそこを飛ばし、生成は止めない。すべての config dir で失敗したとき（`ccreel` が無いときを含む）は止める」に改める
- 維持する保証: 台帳 §5 のほかの項目すべて（`show` に失敗したセッションのページ、設定の誤りで `error:`、指紋、使い回し、相対リンク など）。台帳 §1 の「拡張を設定しなければ…」「読み込めない拡張を設定したときは…」。本体に触れないので、§1〜§4 のテストはそのまま通る

### examples/plugins/sessions.py

- `_sessions()` で、config dir ごとの失敗を集める。成功した config dir が1つも無ければ、`codeview.plugins.PluginError` を上げる。メッセージは英文で、失敗した config dir ごとの理由を含める（`ConfigError` / `PluginError` のメッセージは、そのまま利用者に出す英文にする規約）
- 行の検査: 上の6項目が無い行があれば、その config dir の失敗にする。今は `updated` と `started` の `KeyError` だけを拾っている
- `css()` で `_sessions(ctx)` を呼び、生成前に失敗を表に出す。`_cache` があるので、`side()` / `build()` / `fingerprint()` で二度は呼ばない
- モジュールと `_sessions()` の docstring の「生成は止めない」を、新しい振る舞いに合わせて直す

### tests/test_example_sessions.py

- `test_build_survives_missing_ccreel` は、止まることを確かめるテストに置き換える（`error:`・非0・`public/` が無い）
- すべての config dir で `list` が失敗する（不正な JSON・非0で終わる）場合と、要る項目が欠けた行の場合を足す
- `list` が0件のときに止まらないことを足す
- `publish --if-changed` が push しないことは、`tests/test_publish.py` の既存の作り（配信先のリモートと `site.run("-m", "codeview", "publish", "--if-changed")`）を参考に、このファイルの中で確かめる
- `test_build_survives_one_failing_config_dir` はそのまま残す

### docs/guarantees.md

§5 の箇条と表を、上の「新たに宣言する保証」と「変更する保証」に合わせて直す。
