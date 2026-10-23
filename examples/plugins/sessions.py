"""sessions — Claude Code のセッションを ccreel から読み、一覧と本文のページを足す拡張の例。

使い方: このファイルを `codeview.toml` の隣へ写し、設定に挙げる。

    [plugins]
    modules = ["sessions"]

    [plugins.sessions]
    days = 14

ccreel (https://github.com/yktsnet/ccreel) が要る。`list --json` と `show --json` を外部コマンドとして呼ぶ。
設定は `[plugins.sessions]`:
    ccreel       ccreel のコマンド（既定 "ccreel"）。定期実行の PATH に無いときはパスで渡す
    config_dirs  読む config dir の列（既定 ["~/.claude"]）
    days         載せる期間。この日数のうちに更新されたもの（既定 30）
    every_hours  配信の指紋を変える間隔（既定 3）
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

CSS = """
/* ---------- sessions ---------- */
#sq {
  flex: 1 1 14rem; min-width: 0; padding: .3rem .6rem;
  border: 1px solid var(--line); border-radius: var(--r-sm);
  background: var(--card); color: var(--fg); font: .85rem var(--mono);
}
#sq[hidden] { display: none; }
.issue[hidden] { display: none; }
.thread::before { display: none; }
.thread { gap: 2rem; }
.thread > .card {
  border: none; border-radius: 0; background: transparent;
  padding: 1.2rem 0 0;
  border-top: 1px solid var(--line-soft);
}
.thread > .card:first-child { border-top: none; padding-top: 0; }
.thread > .card > .chead {
  background: transparent; border-bottom: none;
  padding: 0 0 .5rem;
  color: var(--faint); font-size: .8rem;
}
.thread > .card > .chead .who {
  color: var(--accent); font-weight: 600;
}
.thread > .card > .cbody { padding: 0; }
.prompt {
  margin: .4rem 0 .9rem; padding: .1rem 0 .1rem .8rem;
  border-left: 2px solid var(--line);
  color: var(--fg);
  white-space: pre-wrap; overflow-wrap: anywhere;
}
.reply { margin-top: .6rem; }
.resume code { color: var(--fg); overflow-wrap: anywhere; }
#copy-cmd {
  margin-left: .5rem; padding: 0 .6rem; border: 1px solid var(--line); border-radius: var(--r-sm);
  background: var(--btn); color: var(--mute); font: 500 .72rem/1.8 var(--mono); cursor: pointer;
}
#copy-cmd[hidden] { display: none; }
#copy-cmd:hover { background: var(--btn-hover); color: var(--fg); }
"""

FILTER_SCRIPT = r"""
<script>
(() => {
  const q = document.getElementById('sq');
  if (!q) return;
  const rows = [...document.querySelectorAll('#issues .issue')];
  const none = document.getElementById('none');
  const day = (ms) => { const d = new Date(ms); d.setHours(0, 0, 0, 0); return d.getTime(); };
  const today = day(Date.now());
  // fzf と同じく、語の文字がこの順に現れれば当たりとする
  const fuzzy = (hay, needle) => {
    let i = 0;
    for (const c of hay) if (c === needle[i] && ++i === needle.length) return true;
    return false;
  };
  const match = (row, tok) => {
    if (tok.length > 1 && tok[0] === '@') return row.dataset.repo.startsWith(tok.slice(1));
    if (tok.length > 1 && tok[0] === '#') return row.dataset.issue === tok.slice(1).replace(/^0+/, '');
    const m = /^\*(\d+)$/.exec(tok);
    if (m) return Math.round((today - day(row.dataset.ts * 1000)) / 86400000) === +m[1];
    return fuzzy(row.dataset.q, tok);
  };
  const apply = () => {
    const toks = q.value.toLowerCase().split(/\s+/).filter(Boolean);
    let n = 0;
    for (const r of rows) {
      r.hidden = !toks.every((t) => match(r, t));
      if (!r.hidden) n++;
    }
    none.hidden = n > 0;
  };
  q.hidden = false;
  q.value = new URLSearchParams(location.search).get('q') || '';
  q.addEventListener('input', apply);
  apply();
})();
</script>
"""

COPY_SCRIPT = r"""
<script>
(() => {
  const b = document.getElementById('copy-cmd');
  if (!b || !navigator.clipboard) return;
  b.hidden = false;
  b.addEventListener('click', () => {
    navigator.clipboard.writeText(document.getElementById('cmd').textContent).then(() => {
      b.textContent = 'Copied';
      setTimeout(() => { b.textContent = 'Copy'; }, 1500);
    });
  });
})();
</script>
"""

# 本文のページは public/ の外に置いて使い回す。本体は生成のたびに public/ を空にする
CACHE_INDEX = "index.json"

# 1回の生成のあいだ、side と build と fingerprint で同じ一覧を使う
_cache: dict[str, list[dict]] = {}


def _opts(ctx) -> dict:
    where = "config: [plugins.sessions]"
    opts = {"ccreel": "ccreel", "config_dirs": ["~/.claude"], "days": 30, "every_hours": 3, **ctx.options}

    def fail(msg: str):
        from codeview.config import ConfigError

        raise ConfigError(f"{where}: {msg}")

    if not isinstance(opts["ccreel"], str) or not opts["ccreel"]:
        fail("'ccreel' must be a non-empty string")
    dirs = opts["config_dirs"]
    if not isinstance(dirs, list) or not dirs or not all(isinstance(d, str) and d for d in dirs):
        fail("'config_dirs' must be a non-empty list of strings")
    for key in ("days", "every_hours"):
        if isinstance(opts[key], bool) or not isinstance(opts[key], int) or opts[key] <= 0:
            fail(f"'{key}' must be a positive integer")
    unknown = set(opts) - {"ccreel", "config_dirs", "days", "every_hours"}
    if unknown:
        fail(f"unknown key '{sorted(unknown)[0]}'")
    return opts


def _ccreel(opts: dict, config_dir: str, *args: str) -> str:
    cmd = [os.path.expanduser(opts["ccreel"]), *args, "--config-dir", os.path.expanduser(config_dir)]
    return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120).stdout


def _ts(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def _sessions(ctx) -> list[dict]:
    """config dir をまとめた新しい順の一覧。ccreel が無い・失敗した config dir は警告して飛ばし、生成は止めない。"""
    if "list" in _cache:
        return _cache["list"]
    opts = _opts(ctx)
    rows: list[dict] = []
    for config_dir in opts["config_dirs"]:
        found: list[dict] = []
        try:
            out = _ccreel(opts, config_dir, "list", "--json", "--limit", "0", "--since", f"{opts['days']}d")
            for line in out.splitlines():
                if line.strip():
                    row = json.loads(line)
                    row["ts"] = _ts(row["updated"])
                    row["started_ts"] = _ts(row["started"])
                    row["config_dir"] = config_dir
                    found.append(row)
        except (OSError, subprocess.SubprocessError, ValueError, KeyError) as e:
            detail = getattr(e, "stderr", None) or str(e)
            print(f"warning: sessions: ccreel list failed for {config_dir}, skip: {detail.strip()}", file=sys.stderr)
            continue
        rows += found
    rows.sort(key=lambda r: r["ts"], reverse=True)
    _cache["list"] = rows
    return rows


def _dir_label(ctx, r: dict) -> str | None:
    """config dir が複数のときだけ、どこのセッションかを示す名前を返す。"""
    if len(_opts(ctx)["config_dirs"]) < 2:
        return None
    return Path(r["config_dir"]).name


def _turns(opts: dict, r: dict) -> list[dict] | None:
    sid = r["id"]
    try:
        out = _ccreel(opts, r["config_dir"], "show", sid, "--json", "--max-chars", "20000", "--max-total", "0")
        return [json.loads(line) for line in out.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        detail = getattr(e, "stderr", None) or str(e)
        print(f"warning: sessions: ccreel show {sid} failed: {detail.strip()}", file=sys.stderr)
        return None


def _time(ts: int) -> str:
    # 本体の TIME_SCRIPT が開いた時点の相対時刻に書き換える。JS が無ければ日時のまま読める
    stamp = f"{datetime.fromtimestamp(ts):%Y-%m-%d %H:%M}"
    return f'<time data-ts="{ts}" title="{stamp}">{stamp}</time>'


def _issue_href(public: Path, repo: str, num: str) -> str | None:
    """取り込み元の拡張が書いた Issue のページ。番号は先頭の 0 を無視して比べる。消化済みならページは無い。"""
    for page in sorted(public.glob(f"issues/*/{repo}/*.html")):
        if page.stem.isdigit() and int(page.stem) == int(num):
            return "/" + page.relative_to(public).as_posix()
    return None


def _repo_slug(ctx, name: str) -> str | None:
    return next((r.slug for r in ctx.repos if r.path.name == name), None)


def css(ctx) -> str:
    # 本体が最初に呼ぶ口なので、設定の誤りをここで ConfigError にして、public/ に触れる前に止める
    _opts(ctx)
    return CSS


def side(ctx) -> str:
    rows = _sessions(ctx)
    if not rows:
        return ""
    return (
        '<h2 class="dhead">sessions</h2>'
        f'<a class="item acct" href="/sessions/"><span class="t">Claude Code</span>'
        f'<span class="m">{len(rows):,}</span></a>'
    )


def _side(rows: list[dict]) -> str:
    from codeview.layout import side_head

    esc = html.escape
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["repo"]] = counts.get(r["repo"], 0) + 1
    items = [
        '<a class="item acct" href="/sessions/"><span class="t">All</span>'
        f'<span class="m">{len(rows):,}</span></a>'
    ]
    # JS が無ければ絞り込まれず全件が出る
    items += [
        f'<a class="item dir" href="/sessions/index.html?q=@{esc(repo, quote=True)}">'
        f'<span class="t">{esc(repo)}</span><span class="m">{n:,}</span></a>'
        for repo, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    return side_head('<nav class="crumb"><span>sessions</span></nav>') + '<div id="list">' + "".join(items) + "</div>"


def _page_side() -> str:
    """本文のページの左。件数を出すと1本増えるたびに全ページが変わり、使い回せなくなる。"""
    from codeview.layout import side_head

    return (
        side_head('<nav class="crumb"><a href="/sessions/">sessions</a></nav>')
        + '<div id="list"><a class="item acct" href="/sessions/"><span class="t">All sessions</span></a></div>'
    )


def _row(r: dict, label: str | None) -> str:
    esc = html.escape
    title = r["title"] or r.get("first_prompt") or "(no title)"
    title = " ".join(title.split())
    sub = [esc(r["repo"])]
    if r.get("issue"):
        sub.append(f"#{esc(r['issue'])}")
    if label:
        sub.append(esc(label))
    sub += [f"{r['prompts']} prompts", _time(r["ts"])]
    q = " ".join((title, r.get("first_prompt", ""), r["repo"], label or "")).lower()
    return (
        f'<div class="issue" data-repo="{esc(r["repo"].lower(), quote=True)}" '
        f'data-issue="{esc(r.get("issue", "").lstrip("0"), quote=True)}" data-ts="{r["ts"]}" '
        f'data-q="{esc(q, quote=True)}">'
        f'<div class="i-top"><a class="i-title" href="/sessions/{esc(r["id"])}.html">{esc(title)}</a></div>'
        f'<div class="i-sub">{" · ".join(sub)}</div></div>'
    )


def _list_main(ctx, rows: list[dict]) -> str:
    return (
        '<a id="back" href="/">← codeview</a>'
        '<div class="head"><h2>sessions</h2>'
        '<input id="sq" type="search" autocomplete="off" placeholder="@repo #issue *0 words" hidden>'
        f'<span class="meta count">{len(rows):,} sessions</span></div>'
        f'<div id="issues">{"".join(_row(r, _dir_label(ctx, r)) for r in rows)}</div>'
        '<p class="empty" id="none" hidden>No matching sessions</p>'
    )


def _turn_card(t: dict, script_collector: list[str]) -> str:
    from codeview.render import render_markdown

    esc = html.escape
    ts = _ts(t["time"]) if t.get("time") else None
    when = _time(ts) if ts else ""
    head = f'<div class="chead"><b class="who">turn {t["turn"]}</b>{when}</div>'
    prompt = f'<div class="prompt">{esc(t["prompt"])}</div>'

    text = "\n\n".join(m["text"] for m in t.get("messages", []) if m.get("kind") == "text" and m.get("text"))
    if text.strip():
        body, script = render_markdown(text.encode(), safe=True)
        if 'class="mermaid"' in body:
            script_collector.append(script)
        reply = f'<div class="reply">{body}</div>'
    else:
        reply = ""

    return f'<div class="card">{head}<div class="cbody">{prompt}{reply}</div></div>'


def _session_main(r: dict, deps: dict, turns: list[dict] | None) -> tuple[str, str]:
    esc = html.escape
    title = r["title"] or r.get("first_prompt") or "(no title)"
    title = " ".join(title.split())
    scripts: list[str] = []
    sub = [f"<span>{esc(r['repo'])}</span>"]
    if r.get("issue"):
        href = deps["issue_href"]
        sub.append(
            f'<a class="wait" href="{esc(href, quote=True)}">#{esc(r["issue"])}</a>'
            if href
            else f"<span>#{esc(r['issue'])}</span>"
        )
    label = deps["label"]
    if label:
        sub.append(f'<span class="ilabel">{esc(label)}</span>')
    if r.get("branch"):
        sub.append(f'<span class="ilabel">{esc(r["branch"])}</span>')
    sub.append(f"<span>{r['prompts']} prompts</span>")

    links = [
        '<div class="resume"><span class="k">Resume</span>'
        f'<code id="cmd">ccreel resume {esc(r["id"])}</code>'
        '<button id="copy-cmd" type="button" hidden>Copy</button></div>'
    ]
    slug = deps["slug"]
    if slug:
        links.append(f'<div><span class="k">Repo</span><a href="/{esc(slug)}/">{esc(r["repo"])}</a></div>')

    if turns is None:
        thread = '<p class="empty">Could not read this session</p>'
    else:
        cards = [_turn_card(t, scripts) for t in turns]
        thread = f'<div class="thread">{"".join(cards)}</div>'

    main = (
        '<a id="back" href="/sessions/">← sessions</a>'
        f'<div class="ihead"><h2 class="ititle">{esc(title)}</h2>'
        f'<div class="isub">{"".join(sub)}{_time(r["started_ts"])}<span>→</span>{_time(r["ts"])}</div></div>'
        f'<div class="ilinks">{"".join(links)}</div>{thread}'
    )
    return main, scripts[0] if scripts else ""


def _cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "codeview" / "sessions"


def _code_digest() -> str:
    """この拡張と本体のソースの指紋。どちらかが変われば、作ったページを全部作り直す。"""
    import codeview

    h = hashlib.sha256(Path(__file__).read_bytes())
    root = Path(codeview.__file__).resolve().parent
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" not in path.parts:
            h.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes())
    return h.hexdigest()


def _key(r: dict, deps: dict, style: str, code: str) -> str:
    """本文のページの中身を決めるものを全部入れる。同じ鍵なら同じページになる。"""
    parts = [r, deps, style, code]
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _load_index(cache: Path) -> dict:
    try:
        data = json.loads((cache / CACHE_INDEX).read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_cache(cache: Path, index: dict, keep: set[str]) -> None:
    """一覧から消えたセッションの分を消し、索引を書き換える。失敗しても生成は止めない。"""
    try:
        for f in cache.glob("*.html"):
            if f.stem not in keep:
                f.unlink()
        tmp = cache / (CACHE_INDEX + ".tmp")
        tmp.write_text(json.dumps({k: v for k, v in index.items() if k in keep}))
        tmp.replace(cache / CACHE_INDEX)
    except OSError as e:
        print(f"warning: sessions: could not update the cache: {e}", file=sys.stderr)


def build(ctx) -> None:
    from codeview.layout import TIME_SCRIPT, get_style_href, page
    from codeview.style import write

    rows = _sessions(ctx)
    if not rows:
        return
    opts = _opts(ctx)
    write(
        ctx.public / "sessions" / "index.html",
        page(
            "sessions",
            _side(rows),
            _list_main(ctx, rows),
            detail=True,
            extra_script=TIME_SCRIPT + FILTER_SCRIPT,
            width="w-issue",
            path="/sessions/index.html",
        ),
    )

    cache = _cache_dir()
    try:
        cache.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"warning: sessions: no cache, rebuild all: {e}", file=sys.stderr)
    index = _load_index(cache)
    style, code = get_style_href(), _code_digest()
    plans = []
    for r in rows:
        deps = {
            "issue_href": _issue_href(ctx.public, r["repo"], r["issue"]) if r.get("issue") else None,
            "slug": _repo_slug(ctx, r["repo"]),
            "label": _dir_label(ctx, r),
        }
        key = _key(r, deps, style, code)
        hit = index.get(r["id"]) == key and (cache / f"{r['id']}.html").is_file()
        plans.append((r, deps, key, hit))

    todo = [p for p in plans if not p[3]]
    # 1本ずつ ccreel を起動するので、待ち時間を重ねる
    with ThreadPoolExecutor(max_workers=8) as pool:
        all_turns = list(pool.map(lambda p: _turns(opts, p[0]), todo))
    fresh = {p[0]["id"]: turns for p, turns in zip(todo, all_turns)}

    for r, deps, key, hit in plans:
        path = f"/sessions/{r['id']}.html"
        cached = cache / f"{r['id']}.html"
        if hit:
            try:
                write(ctx.public / path.lstrip("/"), cached.read_text())
                continue
            except OSError:
                fresh[r["id"]] = _turns(opts, r)
        turns = fresh[r["id"]]
        main, script = _session_main(r, deps, turns)
        doc = page(
            f"{r['repo']} {r['title']}",
            _page_side(),
            main,
            detail=True,
            extra_script=script + TIME_SCRIPT + COPY_SCRIPT,
            width="w-issue",
            path=path,
        )
        write(ctx.public / path.lstrip("/"), doc)
        # 読めなかったセッションは使い回さず、次の生成で読み直す
        if turns is not None:
            try:
                cached.write_text(doc)
                index[r["id"]] = key
            except OSError:
                index.pop(r["id"], None)
        else:
            index.pop(r["id"], None)
    _save_cache(cache, index, {r["id"] for r in rows})
    print(f"sessions: {len(rows)} pages ({len(todo)} rebuilt)", file=sys.stderr)


def fingerprint(ctx) -> str:
    """最新の更新を every_hours ごとの枠に丸める。枠の中で何度話しても配信は増えない。"""
    rows = _sessions(ctx)
    if not rows:
        return "sessions none"
    span = _opts(ctx)["every_hours"] * 3600
    return f"sessions {max(r['ts'] for r in rows) // span}"
