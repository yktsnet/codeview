## README と周辺の md から重複と細部を削る
id: 01
branch-slug: trim-docs
status: close
type: cleanup
対象: README.md、README.en.md、CLAUDE.md、docs/guarantees.md
内容: README が使う人に要らない細部と、同じ事実の繰り返しで長くなっている。導入して使い始めるのに要る情報だけを残し、日英を同じ構成で縮める。周辺の md も重複を除く
対象外: コードとテストの変更。`context/` の3本（実装者向けの正本なので細部を持ってよい）。`.claude/skills/pr-workflow/SKILL.md`（dotfiles の写し）。README の H2 の追加
仮定: 削った細部の受け皿は作らない（`docs/usage.md` などを新設しない）。コードと `--help` で分かることは README から消してよい
確認: README.md と README.en.md の H2 の並びが一致し、日英で同じ事実を述べている。README.md が 196 行から 120 行以下になっている。下の「残すもの」がすべて残っている。`nix develop -c pytest -q` が通る
人が見るもの: GitHub 上で README を読み、冗長さが取れたか（読み味）

---

### 保証
- 保証: なし（ドキュメントのみ。振る舞いを変えない。台帳は末尾の注記だけを直し、保証の本文と表には触れない）

### 残すもの（README）

- H1 直下のコアメッセージ1文と CI バッジ
- 導入（Nix / pip）、最小の `codeview.toml`、`build` / `serve`
- 設定の節の表（`[[roots]]` / `[scan]` / `[[accounts]]` / `[publish]` / `[plugins]`）
- 拡張の関数の表
- 配信するリポを private にする警告、`publish` の3つの使い方、`cf-setup` の前提、`*.pages.dev` を `_middleware.js` で塞ぐこと
- 保証台帳へのリンク、License

### README.md / README.en.md で削るもの

同じ事実が何度も出ている。1か所に寄せる。

- 「HEAD だけを読む・未コミットは出ない」が What You Get・`--if-changed` の段落・Scope・Tech Stack・Design Decisions の5か所にある → Scope の1か所に寄せる
- 「20,000 ファイル」が Scope と Publishing にある → Scope だけにする
- Tech Stack の Reason と Design Decisions が同じ理由を言っている → どちらか一方にまとめる（片方の H2 を消してよい）
- 概要の2段落目（「GitHub の web やモバイルアプリは…」）はコアメッセージの言い換え → 1文に縮めるか消す

使う人に要らない細部:

- What You Get の「表示幅」の箇条（px の値）を消す
- 「コピー」の箇条はクリックする場所の列挙をやめ、1文にする
- `--if-changed` の指紋の内訳（何から作るか）を消し、「前回から変化が無ければ何もしない。定期実行向け」程度にする
- `cf-setup` の段落は「`git config user.email` だけを許可する」と「最後に出る確認を済ませてから使う」に絞る
- 2アカウントの設定例は `[[accounts]]` の2ブロックだけにする（`[[roots]]` と `[scan]` は最小の例と表で足りる）
- `ctx` の説明段落を1文にする
- Local Development のテストの説明（CLAUDE.md と重複）を消し、コマンドだけにする

### CLAUDE.md

- 「アーキテクチャの要点」の3点は `context/domain.md` と `context/conventions.md` に同じことがある。import しているので節ごと消す
- 「検証手段」の下のテストの説明は `context/structure.md` の `tests/` と重複する。コマンドだけにする

### docs/guarantees.md

- `## About` の末尾の文（「地位は design-decisions.md 相当のドキュメントと同格」）を消す。このリポに design-decisions.md は無く、何と何が同格か読めない
