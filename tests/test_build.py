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
        {"docs/code.md": "コード `<a href=\"/x\">` の例\n\n[top](/) [dir](/docs/) [ext](https://example.com/)\n"},
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


class _Anchors(HTMLParser):
    """本文の `<a>` を（文字, href）で集める。"""

    def __init__(self):
        super().__init__()
        self.anchors: dict[str, str] = {}
        self._href = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag == "a":
            self._href = None

    def handle_data(self, data):
        if self._href is not None:
            self.anchors[data] = self._href


def _anchors(page_path):
    parser = _Anchors()
    parser.feed(page_path.read_text())
    return parser.anchors


def _target(page_path, href):
    """href をページの位置から解決した先（`#` 以降は除く）。"""
    return (page_path.parent / href.split("#")[0]).resolve()


README_LINKS = """# alpha

[guide](docs/guide.md) [anchor](docs/guide.md#usage) [src](main.py)
[dir1](docs/) [dir2](docs) [root](/docs/guide.md) [top](.) [enc](docs/guide%2Emd?x=1)
[missing](nothing.md) [skipped](logo.png) [outside](../../x.md)
[ext](https://example.com/) [hash](#見出し)
"""


def test_markdown_links_point_to_generated_pages(site):
    alpha = site.home / "own" / "alpha"
    commit(
        alpha,
        {
            "README.md": README_LINKS,
            "docs/guide.md": "# guide\n\n[up](../README.md) [far](../../x.md)\n",
        },
    )
    public, _ = site.build()
    out = public / "alpha"
    guide = (out / "docs" / "guide.md.html").resolve()
    main = (out / "main.py.html").resolve()
    docs_index = (out / "docs" / "index.html").resolve()
    for page_path in (out / "README.md.html", out / "index.html"):
        found = _anchors(page_path)
        assert _target(page_path, found["guide"]) == guide
        assert found["anchor"].endswith("guide.md.html#usage")
        assert _target(page_path, found["anchor"]) == guide
        assert _target(page_path, found["src"]) == main
        for name in ("dir1", "dir2"):
            assert _target(page_path, found[name]) == docs_index
        assert _target(page_path, found["root"]) == guide
        assert _target(page_path, found["top"]) == (out / "index.html").resolve()
        # %エンコードは戻して突き合わせ、query は落とす
        assert _target(page_path, found["enc"]) == guide and "?" not in found["enc"]
        # ページの無い先は、リンクにせず文字だけ残す
        text = page_path.read_text()
        for name in ("missing", "skipped", "outside"):
            assert name not in found and name in text
        assert found["ext"] == "https://example.com/"
        assert found["hash"] == "#見出し"
    # 基準は .md の位置。docs/ の中から親のファイルを指せる
    page_path = out / "docs" / "guide.md.html"
    found = _anchors(page_path)
    assert _target(page_path, found["up"]) == (out / "README.md.html").resolve()
    assert "far" not in found and "far" in page_path.read_text()
    _assert_relative_and_resolvable(public)


def test_markdown_links_resolve_from_md_location_in_subdirectory(site):
    # サブディレクトリの README は、ファイルページと docs/index.html に埋め込まれた形で同じ先を指す
    commit(
        site.home / "own" / "alpha",
        {
            "docs/README.md": (
                "[sib](guide.md) [root](/main.py) [up](../README.md) "
                "[sec](../secrets/token.txt) [q](guide.md?x#a)\n"
            ),
        },
    )
    public, _ = site.build()
    out = public / "alpha"
    for page_path in (out / "docs" / "README.md.html", out / "docs" / "index.html"):
        found = _anchors(page_path)
        guide = (out / "docs" / "guide.md.html").resolve()
        assert _target(page_path, found["sib"]) == guide
        assert _target(page_path, found["root"]) == (out / "main.py.html").resolve()
        assert _target(page_path, found["up"]) == (out / "README.md.html").resolve()
        assert _target(page_path, found["q"]) == guide and found["q"].endswith("#a")
        # exclude_prefixes で除外したファイルはページが無いので文字になる
        assert "sec" not in found and "sec" in page_path.read_text()
    _assert_relative_and_resolvable(public)


GITHUB_LINKS = """# alpha

[blob](https://github.com/me/alpha/blob/main/docs/guide.md#usage)
[tree](https://github.com/Me/Alpha/tree/main/docs) [repo](https://github.com/me/alpha)
[cross](https://github.com/org/beta/blob/main/app.py) [issue](https://github.com/me/alpha/issues/3)
[sha](https://github.com/me/alpha/blob/0123abc/main.py) [gone](https://github.com/me/alpha/blob/main/nothing.md)
[skipped](https://github.com/me/alpha/blob/main/logo.png) [closed](https://github.com/me/alpha/issues/99)
[xacct](https://github.com/org/beta/issues/7) [pull](https://github.com/me/alpha/pull/1)
[unknown](https://github.com/me/other/blob/main/x.md)
"""


def test_github_urls_point_to_generated_pages(site):
    commit(site.home / "own" / "alpha", {"README.md": GITHUB_LINKS})
    public, _ = site.build()
    out = public / "alpha"
    for page_path in (out / "README.md.html", out / "index.html"):
        found = _anchors(page_path)
        assert _target(page_path, found["blob"]) == (out / "docs" / "guide.md.html").resolve()
        assert found["blob"].endswith("#usage")
        assert _target(page_path, found["tree"]) == (out / "docs" / "index.html").resolve()
        assert _target(page_path, found["repo"]) == (out / "index.html").resolve()
        # ファイルへのリンクはアカウントをまたいでよい
        assert _target(page_path, found["cross"]) == (public / "beta" / "app.py.html").resolve()
        assert _target(page_path, found["issue"]) == (public / "issues" / "me" / "alpha" / "3.html").resolve()
        # 対応するページが無い・別の ref・別アカウントの Issue は、外部 URL のまま残す
        for name in ("sha", "gone", "skipped", "closed", "xacct", "pull", "unknown"):
            assert found[name].startswith("https://github.com/"), name
    _assert_relative_and_resolvable(public)
