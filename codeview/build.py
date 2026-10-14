"""ローカルの git リポジトリ群を静的 HTML のコードブラウザに変換する。

出力先は環境変数 `CODEVIEW_OUT`、無ければ作業ディレクトリ。その下に public/ と functions/ を書く。
"""

from __future__ import annotations

import argparse
import hashlib
import html
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
    human,
    is_text,
    line_count,
    render_code_lang,
    render_markdown,
)
from codeview.repo import (
    read_blobs,
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


def build_repo(repo: Path, slug: str, out_root: Path, by_file: dict) -> int:
    cfg = config.load()
    entries = [
        (path, sha)
        for path, sha in tracked_blobs(repo)
        if not path.startswith(cfg.exclude_prefixes)
        and not path.lower().endswith(cfg.skip_exts)
    ]
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
            body, extra_script = render_markdown(data)
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
                body, extra_script = render_markdown(data)
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


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(prog="codeview build", description=__doc__.splitlines()[0]).parse_args(argv)
    # 生成を始める前に設定と拡張を読む。誤っていれば public/ にも触れずに止まる
    site = Path(os.environ.get("CODEVIEW_OUT") or Path.cwd())
    public = site / "public"
    try:
        config.load()
        ctx = plugins.context(public, site / "functions")
        extra_css = plugins.css(ctx)
    except (config.ConfigError, plugins.PluginError) as e:
        raise SystemExit(f"error: {e}") from None
    if public.exists():
        shutil.rmtree(public)

    build_style(public, extra_css)
    build_mermaid(public)

    counts = ctx.counts
    slugged = ctx.repos
    # ファイルページに Issue へのリンクを差し込むので、ページを書く前に全リポ分を集める
    board = collect(ctx)
    for account, failed in board.failed.items():
        for name in failed:
            print(f"  issues/{account}: fetch failed: {name}", file=sys.stderr)
    for group, repo, slug in slugged:
        n = build_repo(repo, slug, public, board.by_file)
        if n == 0:
            print(f"  {slug}: skip (empty)", file=sys.stderr)
            continue
        counts.setdefault(group, []).append((slug, repo.name, n))
        print(f"  {slug}: {n} files", file=sys.stderr)

    build_index(
        counts, public, board, plugins.home(ctx), plugins.side(ctx)
    )
    issues_pages(board, public)
    plugins.build(ctx)
    write(site / "functions" / "_middleware.js", MIDDLEWARE)

    total = sum(1 for p in public.rglob("*") if p.is_file())
    print(f"{total} files -> {public}", file=sys.stderr)
    if total > 20000:
        print(
            "warning: over the Cloudflare Pages limit of 20,000 files",
            file=sys.stderr,
        )

