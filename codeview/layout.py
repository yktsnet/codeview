"""layout — HTML layout templates and sidebar components."""

from __future__ import annotations

import html
import posixpath
import re
import time
from datetime import datetime

from .render import human, render_markdown


def get_style_href() -> str:
    from .style import STYLE_HREF
    return STYLE_HREF


# <script> は開きタグだけを書き換える。本文の JS には触れない
_TAG = re.compile(r"(<script\b[^>]*>)(.*?)(</script>)|(<[a-zA-Z][^>]*>)", re.S)
_LINK_ATTR = re.compile(r'(\s(?:href|src)=")(/[^"]*)"')


def relativize(doc: str, path: str) -> str:
    """タグ内の `href` / `src` のうち `/` 始まりのものを、`path` のページからの相対パスにする。

    `path` はそのページ自身のサイト内パス。`/` で終わる先はディレクトリなので
    `index.html` まで書く（file:// ではディレクトリを開けない）。`//` 始まりは外部 URL。
    エスケープ済みのコード（`&lt;a href=...`）は `<` から始まらないので書き換わらない。
    """
    here = posixpath.dirname(path)

    def link(m: re.Match) -> str:
        target = m.group(2)
        if target.startswith("//"):
            return m.group(0)
        target, sep, frag = target.partition("#")
        if target.endswith("/"):
            target += "index.html"
        rel = posixpath.relpath(target, here)
        return f'{m.group(1)}{rel}{sep}{frag}"'

    def tag(m: re.Match) -> str:
        if m.group(4) is not None:
            return _LINK_ATTR.sub(link, m.group(4))
        return _LINK_ATTR.sub(link, m.group(1)) + m.group(2) + m.group(3)

    return _TAG.sub(tag, doc)


def page(
    title: str,
    side: str,
    main: str,
    detail: bool,
    extra_script: str = "",
    home: bool = False,
    width: str = "",
    readme: bool = False,
    path: str = "",
) -> str:
    """path はこのページ自身のサイト内パス。渡すとリンクを相対パスに直す。"""
    cls = (
        ' class="detail"' if detail
        else ' class="home"' if home
        else ' class="readme"' if readme
        else ""
    )
    doc = (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title>"
        f'<link rel=stylesheet href="{get_style_href()}">'
        f"</head><body{cls}>"
        f'<aside id="side">{side}</aside>'
        f'<main id="main"><div class="wrap {width}">{main}</div></main>'
        f"{extra_script}"
        "</body></html>"
    )
    return relativize(doc, path) if path else doc


def crumb(slug: str, rel_parts: list[str], is_file: bool, home: bool = False) -> str:
    """home は先頭にトップへのリンクを足し、本文側（スマホ）に置く版にする。"""
    links = ['<a href="/">codeview</a>'] if home else []
    name = slug.split("/")[-1]
    if len(rel_parts) == 0 and not is_file:
        links.append(f"<span>{html.escape(name)}</span>")
    else:
        links.append(f'<a href="/{slug}/">{html.escape(name)}</a>')
    acc = []
    for i, part in enumerate(rel_parts):
        acc.append(part)
        last = i == len(rel_parts) - 1
        if last:
            links.append(f"<span>{html.escape(part)}</span>")
        else:
            links.append(f'<a href="/{slug}/{"/".join(acc)}/">{html.escape(part)}</a>')
    cls = "crumb mcrumb" if home else "crumb"
    return f'<nav class="{cls}">' + '<span class="sep">/</span>'.join(links) + "</nav>"


def file_head(
    fname: str, size_label: str, abs_path: str, copy_body: bool, issues=()
) -> str:
    """ファイル名クリックで絶対パスをコピーできるヘッダ。

    コードのページには折り返しの切り替えも置く。JS が無いと押しても効かないので、
    hidden で出しておき FILE_SCRIPT が見せる。
    """
    btn = (
        '<button class="hact" id="wrap" type="button" aria-pressed="true" hidden>'
        "Wrap: on</button>"
        '<button class="hact" id="copy-body" type="button">Copy file</button>'
        if copy_body
        else ""
    )
    links = "".join(
        f'<a class="hissue" href="{html.escape(i.href, quote=True)}">'
        f"Issue: {html.escape(i.repo)} #{html.escape(i.ref)}</a>"
        for i in issues
    )
    return (
        f'<div class="head" data-path="{html.escape(abs_path, quote=True)}">'
        f'<h2><button class="hpath" id="copy-path" type="button" title="Copy path">'
        f"{html.escape(fname)}</button></h2>"
        f'<span class="meta">{html.escape(size_label)}</span>{links}'
        f'<span class="hbtns">{btn}</span>'
        f'<span class="flash" id="flash" role="status" hidden></span></div>'
    )


def pager(prev: tuple[str, str] | None, nxt: tuple[str, str] | None) -> str:
    """同じディレクトリの前後のファイルへのリンク。どちらも無ければ出さない。"""
    if not prev and not nxt:
        return ""

    def cell(item, cls, arrow_l, arrow_r):
        if not item:
            return f'<span class="{cls}"></span>'
        name, href = item
        return (
            f'<a class="{cls}" href="{html.escape(href, quote=True)}" rel="{cls}">'
            f"{arrow_l}{html.escape(name)}{arrow_r}</a>"
        )
    return (
        '<nav class="pager">'
        + cell(prev, "prev", "← ", "")
        + cell(nxt, "next", "", " →")
        + "</nav>"
    )


FILE_SCRIPT = r"""
<script>
(() => {
  const head = document.querySelector('.head[data-path]');
  if (!head) return;
  const path = head.dataset.path;
  const flash = document.getElementById('flash');
  let timer = null;

  async function copy(text, label) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      document.execCommand('copy'); ta.remove();
    }
    flash.textContent = label;
    flash.hidden = false;
    clearTimeout(timer);
    timer = setTimeout(() => { flash.hidden = true; }, 1400);
  }

  document.getElementById('copy-path').onclick = () => copy(path, 'Copied path');

  // インライン行番号は本文と同じテキストノードに混ざるので、行ごとに剥がして戻す
  function source() {
    const plain = document.querySelector('pre.plain');
    if (plain) return plain.textContent;
    const lines = document.querySelectorAll('.hl [id^="ln-"]');
    if (!lines.length) return null;
    return [...lines].map((ln) => {
      const c = ln.cloneNode(true);
      c.querySelectorAll('.linenos').forEach((e) => e.remove());
      return c.textContent.replace(/\n$/, '');
    }).join('\n') + '\n';
  }

  const body = document.getElementById('copy-body');
  if (body) body.onclick = () => {
    const text = source();
    if (text !== null) copy(text, 'Copied file');
  };

  // replaceState では :target が付け替わらないので、JS があるときは .hit で示す
  document.body.classList.add('lnjs');
  function mark(n) {
    document.querySelectorAll('.hl .hit').forEach((e) => e.classList.remove('hit'));
    const ln = document.getElementById('ln-' + n);
    if (ln) ln.classList.add('hit');
    return ln;
  }
  function fromHash() {
    const m = location.hash.match(/^#ln-(\d+)$/);
    if (m) mark(m[1]);
  }
  fromHash();
  window.addEventListener('hashchange', fromHash);

  document.addEventListener('click', (ev) => {
    const no = ev.target.closest('.linenos');
    if (!no) return;
    const n = no.textContent.trim();
    if (!n) return;
    copy(path + ':' + n, 'Copied ' + n);
    if (mark(n)) history.replaceState(null, '', '#ln-' + n);
  });

  const wrap = document.getElementById('wrap');
  if (wrap) {
    const KEY = 'codeview.wrap';
    let on = true;
    try { on = localStorage.getItem(KEY) !== '0'; } catch {}
    const apply = () => {
      document.body.classList.toggle('nowrap', !on);
      wrap.textContent = on ? 'Wrap: on' : 'Wrap: off';
      wrap.setAttribute('aria-pressed', String(on));
    };
    apply();
    wrap.hidden = false;
    wrap.onclick = () => {
      on = !on;
      try { localStorage.setItem(KEY, on ? '1' : '0'); } catch {}
      apply();
    };
  }
})();
</script>
"""


def side_head(crumb_html: str = "") -> str:
    return '<div id="side-head"><h1><a href="/">codeview</a></h1>' f"{crumb_html}</div>"


def listing(slug: str, parent: str, children: list[tuple[str, str, int]], current: str | None = None) -> str:
    rows = []
    base = f"/{slug}/" + (f"{parent}/" if parent else "")
    for child, kind, size in sorted(
        children, key=lambda c: (c[1] != "dir", c[0].lower())
    ):
        href = f"{base}{child}/" if kind == "dir" else f"{base}{child}.html"
        on = " on" if kind == "file" and child == current else ""
        meta = (
            f'<span class="m">{size:,}</span>'
            if kind == "dir"
            else f'<span class="m">{human(size)}</span>'
        )
        rows.append(
            f'<a class="item {kind}{on}" href="{href}">'
            f'<span class="t">{html.escape(child)}</span>{meta}</a>'
        )
    return '<div id="list">' + "".join(rows) + "</div>"


def index_side(counts, board, extra: str = "") -> str:
    """トップページの左メニュー。extra は拡張が足す塊で、先頭に置く。"""
    blocks = [extra] if extra else []
    rows = "".join(
        f'<a class="item acct" href="/issues/{account}/">'
        f'<span class="t">{account}</span>'
        f'<span class="m">{len(board.issues[account]):,}</span></a>'
        for account in board.issues
    )
    blocks.append(f'<h2 class="dhead">issues</h2>{rows}')
    for group, items in counts.items():
        rows = "".join(
            f'<a class="item" href="/{slug}/">'
            f'<span class="t">{html.escape(name)}</span>'
            f'<span class="m">{n:,}</span></a>'
            for slug, name, n in items
        )
        blocks.append(f'<h2 class="dhead">{html.escape(group)}</h2>{rows}')
    return side_head("") + '<div id="list">' + "".join(blocks) + "</div>"


def build_index(
    counts: dict[str, list[tuple[str, str, int]]],
    out_root,
    board,
    homes: list[str] | None = None,
    side_extra: str = "",
) -> None:
    """トップページ。homes は拡張が返した右側の HTML。無ければ案内文だけを出す。"""
    from .style import write
    side = index_side(counts, board, side_extra)
    if not homes:
        total = sum(n for items in counts.values() for _, _, n in items)
        repo_count = sum(len(items) for items in counts.values())
        stats = f"{repo_count} repos / {total:,} files"
        main = f'<p class="empty">{stats}<br>Select a repository</p>'
        write(
            out_root / "index.html",
            page("codeview", side, main, detail=False, path="/index.html"),
        )
        return
    # script は main の中ではなく、ほかのページと同じくページ末尾に置く
    joined = "".join(homes)
    scripts = "".join(_SCRIPT.findall(joined))
    main = _SCRIPT.sub("", joined)
    write(
        out_root / "index.html",
        page(
            "codeview",
            side,
            main,
            detail=False,
            extra_script=scripts,
            home=True,
            path="/index.html",
        ),
    )


_SCRIPT = re.compile(r"<script\b.*?</script>", re.S)


TIME_SCRIPT = r"""
<script>
(() => {
  // 相対時刻は組み立て時の値なので、開いた時点の時刻で言い直す
  const ago = (ts) => {
    const d = Date.now() / 1000 - ts;
    if (d < 60) return 'just now';
    if (d < 3600) return Math.floor(d / 60) + 'm ago';
    if (d < 86400) return Math.floor(d / 3600) + 'h ago';
    if (d < 30 * 86400) return Math.floor(d / 86400) + 'd ago';
    return null;
  };
  document.querySelectorAll('time[data-ts]').forEach((t) => {
    t.textContent = ago(+t.dataset.ts) || 'on ' + t.title.slice(0, 10);
  });
})();
</script>
"""


def _ago(ts: int, now: float) -> str:
    """TIME_SCRIPT と同じ区切りで、組み立て時の相対時刻を返す。"""
    d = now - ts
    if d < 60:
        return "just now"
    if d < 3600:
        return f"{int(d // 60)}m ago"
    if d < 86400:
        return f"{int(d // 3600)}h ago"
    if d < 30 * 86400:
        return f"{int(d // 86400)}d ago"
    return f"on {datetime.fromtimestamp(ts):%Y-%m-%d}"


def _time(ts: int, now: float) -> str:
    if not ts:
        return ""
    return (
        f'<time data-ts="{ts}" title="{datetime.fromtimestamp(ts):%Y-%m-%d %H:%M}">'
        f"{_ago(ts, now)}</time>"
    )


def _issue_row(issue) -> str:
    esc = html.escape
    sub = [esc(issue.repo), f"#{esc(issue.ref)}"]
    if issue.kind:
        sub.append(esc(issue.kind))
    sub_html = " · ".join(sub)
    for w in issue.waits:
        sub_html += (
            f' · <a class="wait" href="{esc(w.href, quote=True)}">'
            f"waits on {esc(w.repo)} #{esc(w.ref)}</a>"
        )
    sub_html += f' · <time>{datetime.fromtimestamp(issue.updated):%Y-%m-%d}</time>'
    return (
        '<div class="issue">'
        f'<div class="i-top"><a class="i-title" href="{esc(issue.href, quote=True)}">'
        f"{esc(issue.title)}</a>"
        f'<span class="badge {issue.state.lower()}">{issue.state}</span></div>'
        f'<div class="i-sub">{sub_html}</div></div>'
    )


def _issue_dir(issue) -> str:
    return issue.href.rsplit("/", 1)[0] + "/"


def issues_side(board, account: str, repo_dir: str | None = None, current=None) -> str:
    """Issue の画面の左。アカウントの切り替え → リポ → 選んだリポの Issue。"""
    esc = html.escape
    tabs = "".join(
        f'<a{" class=on" if a == account else ""} href="/issues/{a}/">{a}</a>'
        for a in board.issues
    )
    head = side_head(
        '<nav class="crumb"><span>issues</span></nav>' f'<div class="tabs">{tabs}</div>'
    )
    issues = board.issues[account]
    if not issues:
        return head + '<div id="list"><p class="empty">No open issues</p></div>'

    groups: dict[str, list] = {}
    for issue in issues:
        groups.setdefault(_issue_dir(issue), []).append(issue)
    order = sorted(groups, key=lambda d: (-len(groups[d]), groups[d][0].repo))

    all_on = " on" if repo_dir is None and current is None else ""
    rows = [
        f'<a class="item acct{all_on}" href="/issues/{account}/">'
        f'<span class="t">All</span><span class="m">{len(issues):,}</span></a>'
    ]
    for d in order:
        on = " on" if d == repo_dir and current is None else ""
        rows.append(
            f'<a class="item dir{on}" href="{esc(d, quote=True)}">'
            f'<span class="t">{esc(groups[d][0].repo)}</span>'
            f'<span class="m">{len(groups[d]):,}</span></a>'
        )
        if d != repo_dir:
            continue
        for issue in groups[d]:
            on = " on" if issue is current else ""
            rows.append(
                f'<a class="item iss{on}" href="{esc(issue.href, quote=True)}" '
                f'title="{esc(issue.title, quote=True)}">'
                f'<span class="n">#{esc(issue.ref)}</span>'
                f'<span class="t">{esc(issue.title)}</span></a>'
            )
    return head + '<div id="list">' + "".join(rows) + "</div>"


def _list_main(back: str, back_label: str, heading: str, issues, fails=()) -> str:
    esc = html.escape
    fail_html = "".join(f'<p class="fail">fetch failed: {esc(r)}</p>' for r in fails)
    body = (
        "".join(_issue_row(i) for i in issues)
        if issues
        else '<p class="empty">No open issues</p>'
    )
    return (
        f'<a id="back" href="{back}">← {esc(back_label)}</a>'
        f'<div class="head"><h2>{heading}</h2>'
        f'<span class="meta count">{len(issues):,} open</span></div>'
        f'{fail_html}<div id="issues">{body}</div>'
    )


def _target_href(issue, path: str, out_root) -> str | None:
    """`対象:` のパスのうち、生成物にページがあるものだけ飛び先を返す。"""
    path = path.strip("/")
    if not path or ".." in path.split("/"):
        return None
    base = out_root / issue.slug
    if (base / (path + ".html")).is_file():
        return f"/{issue.slug}/{path}.html"
    if (base / path / "index.html").is_file():
        return f"/{issue.slug}/{path}/"
    return None


def _card(author: str, ts: int, verb: str, body_html: str, now: float) -> str:
    return (
        '<div class="card"><div class="chead">'
        f'<b class="who">{html.escape(author)}</b>'
        f'<span class="verb">{verb}</span>{_time(ts, now)}</div>'
        f'<div class="cbody">{body_html}</div></div>'
    )


def issue_main(issue, refs: dict[str, str], out_root, now: float) -> tuple[str, str]:
    """Issue ページの右側。本文とコメントのカードを古い順に並べる。"""
    esc = html.escape
    safe = not issue.trusted
    scripts = []

    def md(text: str) -> str:
        if not text.strip():
            return '<p class="nobody">No description provided.</p>'
        body, script = render_markdown(
            text.encode(), safe=safe, refs=refs if safe else None
        )
        if 'class="mermaid"' in body:
            scripts.append(script)
        return body

    sub = [
        f'<span class="badge {issue.state.lower()}">{issue.state}</span>',
        f"<span>{esc(issue.repo)}</span>",
    ]
    sub += [f'<span class="ilabel">{esc(name)}</span>' for name in issue.labels]
    for w in issue.waits:
        sub.append(
            f'<a class="wait" href="{esc(w.href, quote=True)}">'
            f"waits on {esc(w.repo)} #{esc(w.ref)}</a>"
        )

    links = ""
    if issue.source:
        parts = []
        for path in issue.targets:
            href = _target_href(issue, path, out_root)
            parts.append(
                f'<a href="{esc(href, quote=True)}">{esc(path)}</a>'
                if href
                else f"<span>{esc(path)}</span>"
            )
        name = issue.source.rsplit("/", 1)[-1].removesuffix(".html")
        rows = []
        if parts:
            rows.append(f'<div><span class="k">Targets</span>{" ".join(parts)}</div>')
        rows.append(
            '<div><span class="k">Issue file</span>'
            f'<a href="{esc(issue.source, quote=True)}">{esc(name)}</a></div>'
        )
        links = '<div class="ilinks">' + "".join(rows) + "</div>"

    cards = [_card(issue.author, issue.created, "opened", md(issue.body), now)]
    cards += [
        _card(c.author, c.created, "commented", md(c.body), now)
        for c in issue.comments
    ]
    main = (
        f'<a id="back" href="{esc(_issue_dir(issue), quote=True)}">← {esc(issue.repo)}</a>'
        '<div class="ihead">'
        f'<h2 class="ititle">{esc(issue.title)} <span class="inum">#{esc(issue.ref)}</span></h2>'
        f'<div class="isub">{"".join(sub)}</div></div>'
        f'{links}<div class="thread">{"".join(cards)}</div>'
    )
    return main, scripts[0] if scripts else ""


def issues_pages(board, out_root) -> None:
    """アカウントごとの一覧、リポごとの一覧、未消化の Issue ごとのページを書く。"""
    from .style import write
    now = time.time()
    for account, issues in board.issues.items():
        write(
            out_root / "issues" / account / "index.html",
            page(
                f"issues / {account}",
                issues_side(board, account),
                _list_main(
                    "/", "codeview", f"issues / {html.escape(account)}", issues,
                    board.failed[account],
                ),
                detail=True,
                width="w-issue",
                path=f"/issues/{account}/index.html",
            ),
        )

        by_dir: dict[str, list] = {}
        for issue in issues:
            by_dir.setdefault(_issue_dir(issue), []).append(issue)
        for d, rows in by_dir.items():
            heading = f"issues / {html.escape(account)} / {html.escape(rows[0].repo)}"
            write(
                out_root / d.lstrip("/") / "index.html",
                page(
                    f"issues / {account} / {rows[0].repo}",
                    issues_side(board, account, d),
                    _list_main(f"/issues/{account}/", account, heading, rows),
                    detail=True,
                    width="w-issue",
                    path=d + "index.html",
                ),
            )

            refs = {i.ref: i.href for i in rows}
            for issue in rows:
                main, script = issue_main(issue, refs, out_root, now)
                write(
                    out_root / issue.href.lstrip("/"),
                    page(
                        f"{issue.repo} #{issue.ref} {issue.title}",
                        issues_side(board, account, d, issue),
                        main,
                        detail=True,
                        extra_script=script + TIME_SCRIPT,
                        width="w-issue",
                        path=issue.href,
                    ),
                )
