"""走査・ファイルページ・拡張・設定の誤りを、生成物で確かめる。"""

from __future__ import annotations

import re

from conftest import commit


def test_scans_children_and_skips(site):
    public, _ = site.build()
    alpha = public / "alpha"
    assert (alpha / "main.py.html").is_file()
    assert (alpha / "docs" / "guide.md.html").is_file()
    # exclude_prefixes・skip_exts・未コミットのファイルは出さない
    assert not (alpha / "secrets").exists()
    assert not (alpha / "logo.png.html").exists()
    assert not (alpha / "uncommitted.py.html").exists()
    # skip_dirs と worktree（.git がファイル）は走査しない
    assert not (public / "old").exists()
    assert not (public / "wt").exists()
    index = (public / "index.html").read_text()
    assert 'href="/alpha/"' in index and 'href="/beta/"' in index


def test_scans_single_repo_path(site):
    text = site.config.read_text().replace(
        '[[roots]]\ngroup = "work"\nchildren = "{0}/work"'.format(site.home),
        '[[roots]]\ngroup = "work"\npath = "{0}/work/beta"'.format(site.home),
    )
    site.write_config(text)
    public, _ = site.build()
    assert (public / "beta" / "app.py.html").is_file()
    assert not (public / "gamma").exists()


def test_readme_on_directory_page(site):
    public, _ = site.build()
    page = (public / "alpha" / "index.html").read_text()
    assert 'class="readme"' in page
    assert "alpha の説明" in page
    # README の無いディレクトリは案内文のまま
    assert "Select a file" in (public / "alpha" / "docs" / "index.html").read_text()


def test_no_plugins_means_plain_top(site):
    public, _ = site.build()
    out = public.parent
    assert sorted(p.name for p in (out / "functions").iterdir()) == ["_middleware.js"]
    index = (public / "index.html").read_text()
    assert "Select a repository" in index
    assert "repos /" in index


def test_file_page_navigation(site):
    public, _ = site.build()
    page = (public / "alpha" / "main.py.html").read_text()
    # 行数と言語をヘッダに出す
    assert "1 line · Python · " in page
    # 本文側のパンくずはトップからたどれる
    assert '<nav class="crumb mcrumb"><a href="/">codeview</a>' in page
    assert 'href="/alpha/"' in page
    # 同じディレクトリの前後（左の一覧と同じ、大小を無視した名前順）
    assert 'class="next" href="/alpha/README.md.html"' in page
    assert 'class="prev"' in page and 'class="prev" href' not in page
    readme = (public / "alpha" / "README.md.html").read_text()
    assert 'class="prev" href="/alpha/main.py.html"' in readme
    # ディレクトリにファイルが1つなら前後は出さない
    assert 'class="pager"' not in (public / "alpha" / "docs" / "guide.md.html").read_text()


def test_long_markdown_gets_toc(site):
    heads = "".join(f"## 節{i}\n\n本文\n\n" for i in range(4))
    commit(site.home / "own" / "alpha", {"docs/long.md": "# 表題\n\n" + heads})
    public, _ = site.build()
    page = (public / "alpha" / "docs" / "long.md.html").read_text()
    assert '<details class="toc">' in page
    assert 'href="#節0"' in page and 'id="節0"' in page
    # 見出しの少ない文書には付けない
    assert 'class="toc"' not in (public / "alpha" / "docs" / "guide.md.html").read_text()


def test_mermaid_page_loads_only_bundled_script(site):
    md = "# 図\n\n```mermaid\ngraph TD\n  A --> B\n```\n"
    commit(site.home / "own" / "alpha", {"docs/diagram.md": md})
    public, _ = site.build()
    page = (public / "alpha" / "docs" / "diagram.md.html").read_text()
    assert 'class="mermaid"' in page
    assert not re.search(r"(src\s*=|import\b[^;\n]*)[\"' (]*https?://", page)
    srcs = re.findall(r'<script\s+src="([^"]+)"', page)
    assert srcs and all(s.startswith("/") for s in srcs)
    for src in srcs:
        assert (public / src.lstrip("/")).is_file()


def test_missing_config_stops_before_build(site):
    site.config.unlink()
    public, proc = site.build(check=False)
    assert proc.returncode != 0
    assert "error:" in proc.stderr
    assert not public.exists()


def test_broken_config_stops_before_build(site):
    site.write_config("[[roots]]\ngroup = 1\n")
    public, proc = site.build(check=False)
    assert proc.returncode != 0
    assert "error:" in proc.stderr
    assert not public.exists()


def test_unknown_plugin_stops_before_build(site):
    site.write_config(site.config.read_text() + '\n[plugins]\nmodules = ["plugins.nope"]\n')
    public, proc = site.build(check=False)
    assert proc.returncode != 0
    assert "plugins.nope" in proc.stderr
    assert not public.exists()


def test_middleware_blocks_pages_dev(site):
    public, _ = site.build()
    js = (public.parent / "functions" / "_middleware.js").read_text()
    assert "host.endsWith('.pages.dev')" in js
    assert "status: 404" in js
