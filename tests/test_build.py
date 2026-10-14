"""走査・ファイルページ・拡張・設定の誤りを、生成物で確かめる。"""

from __future__ import annotations

import re
from html.parser import HTMLParser

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
    assert 'href="alpha/index.html"' in index and 'href="beta/index.html"' in index


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
    assert '<nav class="crumb mcrumb"><a href="../index.html">codeview</a>' in page
    assert 'href="index.html"' in page
    # 同じディレクトリの前後（左の一覧と同じ、大小を無視した名前順）
    assert 'class="next" href="README.md.html"' in page
    assert 'class="prev"' in page and 'class="prev" href' not in page
    readme = (public / "alpha" / "README.md.html").read_text()
    assert 'class="prev" href="main.py.html"' in readme
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
    page_dir = public / "alpha" / "docs"
    page = (page_dir / "diagram.md.html").read_text()
    assert 'class="mermaid"' in page
    assert not re.search(r"(src\s*=|import\b[^;\n]*)[\"' (]*https?://", page)
    srcs = re.findall(r'<script\s+src="([^"]+)"', page)
    assert srcs and not any(s.startswith(("/", "http")) for s in srcs)
    for src in srcs:
        assert (page_dir / src).resolve().is_file()


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


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("href", "src") and v is not None:
                self.found.append(v)


_EXTERNAL = ("http:", "https:", "mailto:", "#", "//")

# 拡張が home() / side() で返すリンク。本体のページを通るので相対パスに直る
HOMESRC = '''
def home(ctx):
    return '<a class="x" href="/alpha/">home link</a><script>var a = 1 < 2;</script>'


def side(ctx):
    return '<a class="y" href="/beta/docs/">side link</a>'
'''


def _assert_relative_and_resolvable(public):
    checked = 0
    for page in public.rglob("*.html"):
        parser = _Links()
        parser.feed(page.read_text())
        for link in parser.found:
            if link.startswith(_EXTERNAL):
                continue
            assert not link.startswith("/"), f"{page}: {link}"
            target = (page.parent / link.split("#")[0]).resolve()
            assert target.is_file(), f"{page}: {link}"
            assert public.resolve() in target.parents
            checked += 1
    return checked


def test_links_are_relative_and_resolve(site):
    commit(
        site.home / "own" / "alpha",
        {"docs/code.md": "コード `<a href=\"/x\">` の例\n\n[top](/) [dir](/alpha/docs/) [ext](https://example.com/)\n"},
    )
    public, _ = site.build()
    assert _assert_relative_and_resolvable(public) > 50
    page = (public / "alpha" / "docs" / "code.md.html").read_text()
    # エスケープ済みのコードは書き換えない
    assert "&lt;a href=" in page and "/x" in page
    assert 'href="../../index.html"' in page and 'href="index.html"' in page
    assert 'href="https://example.com/"' in page
    # CSS は深さに応じた相対パス
    assert re.search(r'<link rel=stylesheet href="\.\./\.\./style\.[0-9a-f]+\.css">', page)
    assert re.search(r'<link rel=stylesheet href="style\.[0-9a-f]+\.css">', (public / "index.html").read_text())


def test_extension_home_and_side_links_are_relative(site):
    (site.config.parent / "homesrc.py").write_text(HOMESRC)
    site.write_config(site.config.read_text() + '\n[plugins]\nmodules = ["homesrc"]\n')
    public, _ = site.build()
    index = (public / "index.html").read_text()
    assert 'class="x" href="alpha/index.html"' in index
    assert 'class="y" href="beta/docs/index.html"' in index
    # script の本文は書き換えない
    assert "var a = 1 < 2;" in index
