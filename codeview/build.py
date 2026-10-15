"""ローカルの git リポジトリ群を静的 HTML のコードブラウザに変換する。

出力先は環境変数 `CODEVIEW_OUT`、無ければ作業ディレクトリ。その下に public/ と functions/ を書く。
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import html
import json
import os
import shutil
import sys
from importlib import resources
from pathlib import Path

from codeview import config, plugins
from codeview.issues import collect
from codeview.layout import (
    FILE_SCRIPT,
    build_index,
    crumb,
    file_head,
    issues_pages,
    listing,
    page,
    pager,
    side_head,
)
from codeview.render import (
    MAX_BYTES,
    GitHubLinks,
    GitHubRepo,
    LinkContext,
    human,
    is_text,
    line_count,
    render_code_lang,
    render_markdown,
)
from codeview.repo import (
    account_of,
    branch,
    head,
    markdown_mentions,
    owner_repo,
    read_blobs,
    remote_host,
    tracked_blobs,
)
from codeview.style import MIDDLEWARE, build_style, write

# GitHub と同じく、ディレクトリに README があれば一覧の下に描く。Markdown を優先する
README_ORDER = (".md", ".markdown", "", ".txt", ".rst")
MERMAID_HREF = "/mermaid.js"


def build_mermaid(out_root: Path) -> str:
    global MERMAID_HREF
    data = resources.files("codeview").joinpath("assets/mermaid.min.js").read_bytes()
    digest = hashlib.sha256(data).hexdigest()[:10]
    MERMAID_HREF = f"/mermaid.{digest}.js"
    target = out_root / f"mermaid.{digest}.js"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return MERMAID_HREF


def _lines(data: bytes) -> str:
    n = line_count(data)
    return f"{n:,} line" + ("" if n == 1 else "s")


def _readme_of(children: dict) -> str | None:
    found = {}
    for child, (kind, _) in children.items():
        stem, dot, ext = child.partition(".")
        if kind == "file" and stem.lower() == "readme":
            found.setdefault((dot + ext).lower(), child)
    for ext in README_ORDER:
        if ext in found:
            return found[ext]
    return None


def _page_entries(repo: Path, slug: str) -> list[tuple[str, str]]:
    """ページにする (パス, blob sha)。HEAD のファイルから除外パスと除外拡張子を落とす。

    除外は全体の `[scan]` に、そのリポの `[scan.repos."<slug>"]` の分を足したもの。
    """
    cfg = config.load()
    extra = cfg.repo_scan.get(slug, config.RepoScan())
    prefixes = cfg.exclude_prefixes + extra.exclude_prefixes
    exts = cfg.skip_exts + extra.skip_exts
    return [
        (path, sha)
        for path, sha in tracked_blobs(repo)
        if not path.startswith(prefixes) and not path.lower().endswith(exts)
    ]


def github_links(repos: list[plugins.Repo], board) -> GitHubLinks:
    """走査対象のうち GitHub にあるリポと、GitHub から取り込んだ Issue の索引を作る。

    remote が github.com でなくても（ssh の別名など）、Issue を GitHub から取るアカウントの
    リポは GitHub にあるとみなす。
    """
    accounts = {a.name: a for a in config.load().accounts}
    found: dict[str, GitHubRepo] = {}
    by_slug: dict[str, str] = {}
    for group, path, slug in repos:
        account = account_of(group, path)
        on_github = remote_host(path) == "github.com" or (
            account is not None and accounts[account].issues == "github"
        )
        if not on_github:
            continue
        try:
            key = owner_repo(path).lower()
        except RuntimeError:
            continue
        files = frozenset(p for p, _ in _page_entries(path, slug))
        dirs = {""}
        for f in files:
            parts = f.split("/")[:-1]
            dirs.update("/".join(parts[: i + 1]) for i in range(len(parts)))
        found[key] = GitHubRepo(slug, account, branch(path), files, frozenset(dirs))
        by_slug[slug] = key

    issues: dict[tuple[str, str], tuple[str, str]] = {}
    for name, rows in board.issues.items():
        if accounts[name].issues != "github":
            continue
        for issue in rows:
            key = by_slug.get(issue.slug)
            if key is not None:
                issues[(key, issue.ref)] = (name, issue.href)
    return GitHubLinks(found, issues)


def build_repo(
    repo: Path,
    slug: str,
    out_root: Path,
    by_file: dict,
    github: GitHubLinks | None = None,
    account: str | None = None,
) -> int:
    entries = _page_entries(repo, slug)
    blobs = read_blobs(repo, [sha for _, sha in entries])
    name = slug.split("/")[-1]
    home = str(Path.home())
    local_root = str(repo)
    if local_root == home or local_root.startswith(home + "/"):
        local_root = "~" + local_root[len(home):]

    tree = {}
    dir_files = {}
    for path, sha in entries:
        parts = path.split("/")
        for depth in range(len(parts)):
            parent = "/".join(parts[:depth])
            child = parts[depth]
            if depth == len(parts) - 1:
                tree.setdefault(parent, {})[child] = ("file", len(blobs.get(sha, b"")))
            else:
                tree.setdefault(parent, {})[child] = ("dir", 0)
                full = "/".join(parts[: depth + 1])
                dir_files[full] = dir_files.get(full, 0) + 1

    def children_of(parent):
        prefix = f"{parent}/" if parent else ""
        return [
            (c, k, dir_files.get(prefix + c, 0) if k == "dir" else s)
            for c, (k, s) in tree.get(parent, {}).items()
        ]

    # 前後のファイルへのリンクは、左の一覧と同じ並び（名前の大小を無視）で決める
    siblings: dict[str, list[str]] = {}
    for parent_dir, kids in tree.items():
        siblings[parent_dir] = sorted(
            (c for c, (k, _) in kids.items() if k == "file"), key=str.lower
        )

    # ページになるのは entries に残ったファイルだけ。除外したものは Markdown のリンク先にしない
    file_set = frozenset(path for path, _ in entries)
    dir_set = frozenset(tree)

    def links_for(md_path: str) -> LinkContext:
        return LinkContext(slug, md_path, file_set, dir_set)

    def file_href(parent_dir: str, child: str) -> str:
        return f"/{slug}/" + (f"{parent_dir}/" if parent_dir else "") + f"{child}.html"

    for path, sha in entries:
        data = blobs.get(sha, b"")
        parts = path.split("/")
        parent = "/".join(parts[:-1])
        fname = parts[-1]

        extra_script = ""
        copy_body = False
        width = "w-md"
        meta = [human(len(data))]
        if len(data) > MAX_BYTES:
            body = f'<p class="empty">Too large to display ({human(len(data))})</p>'
        elif not is_text(data):
            body = f'<p class="empty">Binary ({human(len(data))})</p>'
        elif fname.lower().endswith((".md", ".markdown")):
            body, extra_script = render_markdown(
                data, links=links_for(path), github=github, account=account
            )
            meta.insert(0, _lines(data))
        else:
            body, lang = render_code_lang(path, data)
            copy_body = True
            width = "w-code"
            meta[:0] = [_lines(data)] + ([lang] if lang else [])

        files = siblings.get(parent, [])
        i = files.index(fname)
        prev = (files[i - 1], file_href(parent, files[i - 1])) if i > 0 else None
        nxt = (
            (files[i + 1], file_href(parent, files[i + 1]))
            if i + 1 < len(files)
            else None
        )
        main = (
            crumb(slug, parts, True, home=True)
            + file_head(
                fname,
                " · ".join(meta),
                f"{local_root}/{path}",
                copy_body,
                by_file.get((slug, path), ()),
            )
            + body
            + pager(prev, nxt)
        )
        side = side_head(crumb(slug, parts, True)) + listing(
            slug, parent, children_of(parent), current=fname
        )
        write(
            out_root / slug / (path + ".html"),
            page(
                f"{slug}/{path}",
                side,
                main,
                detail=True,
                extra_script=extra_script + FILE_SCRIPT,
                width=width,
                path=f"/{slug}/{path}.html",
            ),
        )

    for parent in tree:
        rel_parts = parent.split("/") if parent else []
        title = f"{name}/{parent}" if parent else name
        side = side_head(crumb(slug, rel_parts, False)) + listing(
            slug, parent, children_of(parent)
        )
        readme = _readme_of(tree.get(parent, {}))
        extra_script = ""
        if readme is None:
            main = f'<p class="empty">{html.escape(title)}<br>Select a file</p>'
        else:
            rpath = f"{parent}/{readme}" if parent else readme
            data = blobs.get(dict(entries).get(rpath, ""), b"")
            if readme.lower().endswith((".md", ".markdown")):
                body, extra_script = render_markdown(
                    data, links=links_for(rpath), github=github, account=account
                )
            else:
                body = '<pre class="plain">' + html.escape(data.decode("utf-8", "replace")) + "</pre>"
            main = (
                f'<div class="readme-head"><a href="/{slug}/{rpath}.html">'
                f"{html.escape(readme)}</a></div>{body}"
            )
        write(
            out_root / slug / parent / "index.html",
            page(
                title,
                side,
                main,
                detail=False,
                extra_script=extra_script,
                width="w-md" if readme else "",
                readme=readme is not None,
                path=f"/{slug}/" + (f"{parent}/" if parent else "") + "index.html",
            ),
        )
    return len(entries)


# 差分 build の記録。出力先の直下に置き、public/ には入れない（配信に載せない）
STATE_NAME = ".codeview-build.json"


def _digest(obj) -> str:
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def _code_digest() -> str:
    """本体のソースと同梱物の指紋。版の番号は開発中に動かないので、中身で見る。"""
    root = Path(__file__).resolve().parent
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in (".py", ".js") and "__pycache__" not in path.parts:
            h.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes())
    return h.hexdigest()


def _github_digest(github: GitHubLinks) -> str:
    return _digest(
        {
            "repos": {
                k: [r.slug, r.account, r.branch, sorted(r.files)]
                for k, r in github.repos.items()
            },
            "issues": [[*k, *v] for k, v in sorted(github.issues.items())],
        }
    )


def _issues_digest(issues) -> str:
    return _digest([dataclasses.asdict(i) for i in issues])


def _load_state(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _clear(public: Path, keep: set[str]) -> None:
    """public/ から、残すリポ（slug）のページ以外を消す。"""
    if not public.is_dir():
        return
    tops = {slug.split("/")[0] for slug in keep}
    for child in public.iterdir():
        if child.name in tops:
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    # group/name の slug は、同じグループの残さないリポだけを消す
    for top in tops:
        for child in (public / top).iterdir():
            if child.is_dir() and f"{top}/{child.name}" not in keep and top not in keep:
                shutil.rmtree(child)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="codeview build", description=__doc__.splitlines()[0])
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="rebuild only the repos whose inputs changed since the last incremental build",
    )
    args = parser.parse_args(argv)
    # 生成を始める前に設定と拡張を読む。誤っていれば public/ にも触れずに止まる
    site = Path(os.environ.get("CODEVIEW_OUT") or Path.cwd())
    public = site / "public"
    try:
        config.load()
        ctx = plugins.context(public, site / "functions")
        extra_css = plugins.css(ctx)
    except (config.ConfigError, plugins.PluginError) as e:
        raise SystemExit(f"error: {e}") from None

    counts = ctx.counts
    slugged = ctx.repos
    # ファイルページに Issue へのリンクを差し込むので、ページを書く前に全リポ分を集める
    board = collect(ctx)
    github = github_links(slugged, board)
    # 外したリポの設定が残っていても build は止めない
    known = {slug for _, _, slug in slugged}
    for slug in config.load().repo_scan:
        if slug not in known:
            print(f"warning: [scan.repos] no such repo: {slug}", file=sys.stderr)
    for account, failed in board.failed.items():
        for name in failed:
            print(f"  issues/{account}: fetch failed: {name}", file=sys.stderr)

    # リポのページの入力は、そのリポの HEAD・属するアカウント・そのリポを対象に挙げた Issue・
    # 本体と設定、それに Markdown が GitHub の URL を含むなら GitHub の索引（他のリポの中身）
    state = {
        "global": _digest([_code_digest(), config.load().source.read_text(), extra_css]),
        "github": _github_digest(github),
        "board": _issues_digest(i for rows in board.issues.values() for i in rows),
        "failed": board.failed,
        "repos": {},
    }
    # ファイルのページの見出しに出す、対象に挙げた Issue へのリンク
    by_slug: dict[str, list] = {}
    for (slug, path), rows in board.by_file.items():
        by_slug.setdefault(slug, []).extend((path, i.repo, i.ref, i.href) for i in rows)
    for group, repo, slug in slugged:
        state["repos"][slug] = {
            "head": head(repo),
            # ファイルのページはリポの置き場所を出す
            "path": str(repo),
            "account": account_of(group, repo),
            "issues": _digest(sorted(by_slug.get(slug, ()))),
        }

    state_path = site / STATE_NAME
    prev = _load_state(state_path) if args.incremental else None
    keep: dict[str, int] = {}
    if prev and public.is_dir() and prev.get("global") == state["global"]:
        github_same = prev.get("github") == state["github"]
        for group, repo, slug in slugged:
            old = prev.get("repos", {}).get(slug)
            if (
                old
                and old.get("files")
                and all(old.get(k) == v for k, v in state["repos"][slug].items())
                and (public / slug).is_dir()
                and (github_same or not markdown_mentions(repo, "github.com/"))
            ):
                keep[slug] = old["files"]
        same = {k: prev.get(k) for k in ("board", "failed")} == {
            k: state[k] for k in ("board", "failed")
        }
        if same and len(keep) == len(slugged) and set(prev.get("repos", {})) == set(state["repos"]):
            print("build skipped: no change since the last build", file=sys.stderr)
            return

    _clear(public, set(keep))
    build_style(public, extra_css)
    build_mermaid(public)

    for group, repo, slug in slugged:
        if slug in keep:
            n = keep[slug]
            state["repos"][slug]["files"] = n
            counts.setdefault(group, []).append((slug, repo.name, n))
            print(f"  {slug}: unchanged", file=sys.stderr)
            continue
        n = build_repo(
            repo, slug, public, board.by_file, github, account_of(group, repo)
        )
        state["repos"][slug]["files"] = n
        if n == 0:
            print(f"  {slug}: skip (empty)", file=sys.stderr)
            continue
        counts.setdefault(group, []).append((slug, repo.name, n))
        print(f"  {slug}: {n} files", file=sys.stderr)

    build_index(
        counts, public, board, plugins.home(ctx), plugins.side(ctx)
    )
    issues_pages(board, public, github)
    plugins.build(ctx)
    write(site / "functions" / "_middleware.js", MIDDLEWARE)
    if args.incremental:
        state_path.write_text(json.dumps(state, ensure_ascii=False) + "\n")

    total = sum(1 for p in public.rglob("*") if p.is_file())
    print(f"{total} files -> {public}", file=sys.stderr)
    if total > 20000:
        print(
            "warning: over the Cloudflare Pages limit of 20,000 files",
            file=sys.stderr,
        )

