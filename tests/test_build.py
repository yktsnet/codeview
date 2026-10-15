"""走査・ファイルページ・拡張・設定の誤りを、生成物で確かめる。"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

from conftest import commit, git


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


REPO_SCAN = """
[scan.repos."alpha"]
skip_exts = [".PY"]
exclude_prefixes = ["docs/"]
"""


def _repo_scan_site(site, extra=REPO_SCAN):
    # alpha と同じ拡張子・パスのファイルを beta にも置く
    commit(
        site.home / "own" / "alpha",
        {"README.md": "[g](docs/guide.md) [m](main.py) [l](logo.png)\n"},
    )
    commit(
        site.home / "work" / "beta",
        {
            "main.py": "m = 1\n",
            "docs/guide.md": "# guide\n",
            "logo.png": "not really a png\n",
            "README.md": "[g](docs/guide.md) [m](main.py) [l](logo.png)\n",
        },
    )
    site.write_config(site.config.read_text() + extra)


def test_repo_scan_adds_to_global_for_that_repo_only(site):
    _repo_scan_site(site)
    public, _ = site.build()
    alpha, beta = public / "alpha", public / "beta"
    # リポ単位の除外は、そのリポだけに効く（拡張子は大小を無視する）
    assert not (alpha / "main.py.html").exists()
    assert not (alpha / "docs").exists()
    assert (beta / "main.py.html").is_file()
    assert (beta / "docs" / "guide.md.html").is_file()
    # 全体の除外は足したあとも効く
    assert not (alpha / "logo.png.html").exists()
    assert not (beta / "logo.png.html").exists()
    assert (alpha / "README.md.html").is_file()
    # 除外したファイルは Markdown のリンク先にならない（文字だけ残る）
    for page in (alpha / "README.md.html", alpha / "index.html"):
        found = _anchors(page)
        assert "g" not in found and "m" not in found and "l" not in found
    found = _anchors(beta / "README.md.html")
    assert "g" in found and "m" in found and "l" not in found
    _assert_relative_and_resolvable(public)


def test_repo_scan_excluded_file_is_not_a_github_link_target(site):
    _repo_scan_site(site)
    commit(
        site.home / "own" / "alpha",
        {"README.md": "[m](https://github.com/me/alpha/blob/main/main.py)\n"},
    )
    public, _ = site.build()
    found = _anchors(public / "alpha" / "README.md.html")
    assert found["m"].startswith("https://github.com/")


def test_repo_scan_unknown_key_stops_before_build(site):
    _repo_scan_site(site, '\n[scan.repos."alpha"]\nskip_dirs = ["x"]\n')
    public, proc = site.build(check=False)
    assert proc.returncode != 0
    assert "error:" in proc.stderr and "skip_dirs" in proc.stderr
    assert not public.exists()


def test_repo_scan_must_be_a_table_per_repo(site):
    site.write_config(site.config.read_text() + '\n[scan.repos]\nalpha = ".png"\n')
    public, proc = site.build(check=False)
    assert proc.returncode != 0 and "error:" in proc.stderr
    assert not public.exists()


def test_repo_scan_unknown_slug_warns_and_continues(site):
    site.write_config(site.config.read_text() + '\n[scan.repos."gone"]\nskip_exts = [".py"]\n')
    public, proc = site.build()
    assert "no such repo: gone" in proc.stderr
    assert (public / "alpha" / "main.py.html").is_file()


def test_repo_scan_change_rebuilds_incrementally(site, tmp_path):
    _repo_scan_site(site, "")
    _build_incremental(site)
    site.write_config(site.config.read_text() + REPO_SCAN)
    public, err = _build_incremental(site)
    assert not (public / "alpha" / "main.py.html").exists()
    assert _tree(public) == _tree(_full_build_elsewhere(site, tmp_path / "1"))


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
            target = (page.parent / unquote(link.split("#")[0])).resolve()
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
    return (page_path.parent / unquote(href.split("#")[0])).resolve()


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


# 1x1 の GIF
GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")

IMAGES_README = """# alpha

![dot](img/dot.gif) ![root](/img/dot.gif) ![space](img/my%20pic.gif) ![svg](icon.svg)
![edge](edge.webp) ![skipped](logo.png) ![hidden](secrets/pic.gif) ![big](big.webp) ![missing](nothing.gif)
![ext](https://example.com/x.png) ![out](../../x.gif)

<img src="img/dot.gif" alt="rawdot" width="10">
<img src="logo.png" alt="rawskipped"> <img src="https://example.com/y.png" alt="rawext">
"""

IMAGES_DOCS_README = """# docs

![up](../img/dot.gif) ![none](dot.gif)

<img src="../img/dot.gif" alt="rawup"> <img src="/img/dot.gif" alt="rawroot"> <img alt="nosrc">
"""


class _Imgs(HTMLParser):
    """本文の `<img>`（alt, src）と、画像の代わりに出した文字を集める。"""

    def __init__(self):
        super().__init__()
        self.imgs: dict[str, str] = {}
        self.noimg: list[str] = []
        self._noimg = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "img":
            self.imgs[a.get("alt", "")] = a.get("src", "")
        self._noimg = tag == "span" and a.get("class") == "noimg"

    def handle_endtag(self, tag):
        self._noimg = False

    def handle_data(self, data):
        if self._noimg:
            self.noimg.append(data)


def _imgs(page_path):
    parser = _Imgs()
    parser.feed(page_path.read_text())
    return parser


def test_images_are_copied_and_shown(site):
    alpha = site.home / "own" / "alpha"
    for name, data in {
        "img/dot.gif": GIF,
        "img/my pic.gif": GIF + b"\0",
        "secrets/pic.gif": GIF,
        "big.webp": b"\0" * (5 * 1024 * 1024 + 1),
        "edge.webp": b"\0" * (5 * 1024 * 1024),
        "icon.svg": b'<svg xmlns="http://www.w3.org/2000/svg"/>\n',
    }.items():
        (alpha / name).parent.mkdir(parents=True, exist_ok=True)
        (alpha / name).write_bytes(data)
    git(alpha, "add", "-A")
    git(alpha, "commit", "-qm", "images")
    commit(alpha, {"README.md": IMAGES_README, "docs/README.md": IMAGES_DOCS_README})
    public, _ = site.build()
    out = public / "alpha"

    # 除外していない 5 MiB 以下（ちょうど 5 MiB を含む）の画像だけをそのままコピーする
    assert (out / "edge.webp").stat().st_size == 5 * 1024 * 1024
    assert (out / "img" / "dot.gif").read_bytes() == GIF
    assert (out / "img" / "my pic.gif").read_bytes() == GIF + b"\0"
    assert (out / "icon.svg").is_file()
    for gone in ("logo.png", "secrets/pic.gif", "big.webp"):
        assert not (out / gone).exists(), gone

    # 画像ファイルのページは <img> で表示する。大きすぎる画像は出さない。svg はコードのまま
    page = out / "img" / "dot.gif.html"
    shown = _imgs(page).imgs
    assert _target(page, shown["dot.gif"]) == (out / "img" / "dot.gif").resolve()
    assert 'class="imgfile"' in page.read_text()
    assert "Too large to display" in (out / "big.webp.html").read_text()
    assert "<img" not in (out / "big.webp.html").read_text()
    svg_page = (out / "icon.svg.html").read_text()
    assert 'class="hl"' in svg_page and "<img" not in svg_page

    # 本文の src はページの位置からの相対パスで、コピーした画像を指す
    gif = (out / "img" / "dot.gif").resolve()
    for page in (out / "README.md.html", out / "index.html"):
        found = _imgs(page)
        for alt in ("dot", "root", "rawdot"):
            assert _target(page, found.imgs[alt]) == gif, alt
        assert _target(page, found.imgs["edge"]) == (out / "edge.webp").resolve()
        assert _target(page, found.imgs["space"]) == (out / "img" / "my pic.gif").resolve()
        assert _target(page, found.imgs["svg"]) == (out / "icon.svg").resolve()
        assert 'width="10"' in page.read_text()
        # ページの無い画像・リポ外の画像は <img> にせず [alt] の文字にする
        assert found.noimg == [
            f"[{n}]"
            for n in ("skipped", "hidden", "big", "missing", "ext", "out", "rawskipped", "rawext")
        ]
        assert "example.com" not in page.read_text()
    # 基準は .md の位置。ファイルページと埋め込み README で同じ先を指す
    for page in (out / "docs" / "README.md.html", out / "docs" / "index.html"):
        found = _imgs(page)
        for alt in ("up", "rawup", "rawroot"):
            assert _target(page, found.imgs[alt]) == gif, alt
        assert found.noimg == ["[none]", "[nosrc]"]
    _assert_relative_and_resolvable(public)


def test_incremental_build_copies_images_like_full_build(site, tmp_path):
    alpha = site.home / "own" / "alpha"
    _build_incremental(site)
    # 画像を足すコミットの後は、alpha を作り直す経路を通る
    (alpha / "dot.gif").write_bytes(GIF)
    git(alpha, "add", "-A")
    git(alpha, "commit", "-qm", "image")
    commit(alpha, {"README.md": "![dot](dot.gif)\n"})
    public, err = _build_incremental(site)
    assert "alpha: unchanged" not in err and "beta: unchanged" in err
    assert (public / "alpha" / "dot.gif").read_bytes() == GIF
    assert _tree(public) == _tree(_full_build_elsewhere(site, tmp_path / "1"))

    # 画像を消すコミットの後は、コピーした画像も残らない
    git(alpha, "rm", "-q", "dot.gif")
    commit(alpha, {"README.md": "![dot](dot.gif)\n"})
    public, err = _build_incremental(site)
    assert "alpha: unchanged" not in err
    assert not (public / "alpha" / "dot.gif").exists()
    assert _tree(public) == _tree(_full_build_elsewhere(site, tmp_path / "2"))


def _build_incremental(site):
    proc = site.run("-m", "codeview", "build", "--incremental")
    return Path(site.env["CODEVIEW_OUT"]) / "public", proc.stderr


def _full_build_elsewhere(site, tmp_path):
    out = tmp_path / "full"
    subprocess.run(
        [sys.executable, "-m", "codeview", "build"],
        cwd=site.config.parent,
        env={**site.env, "CODEVIEW_OUT": str(out)},
        check=True,
        capture_output=True,
    )
    return out / "public"


def _tree(public):
    return {
        str(p.relative_to(public)): p.read_bytes()
        for p in public.rglob("*")
        if p.is_file()
    }


def test_incremental_build_skips_when_nothing_changed(site):
    public, _ = _build_incremental(site)
    page = public / "beta" / "app.py.html"
    before = page.stat().st_mtime_ns
    _, err = _build_incremental(site)
    assert "build skipped" in err
    assert page.stat().st_mtime_ns == before
    # 記録は public/ の外に置く（配信に載せない）
    assert not any(p.name == ".codeview-build.json" for p in public.rglob("*"))


def test_incremental_build_matches_full_build(site, tmp_path):
    _build_incremental(site)
    alpha = site.home / "own" / "alpha"
    beta = site.home / "work" / "beta"
    commit(alpha, {"README.md": "[app](https://github.com/org/beta/blob/main/app.py) [x](docs/guide.md)\n"})
    public, err = _build_incremental(site)
    assert "beta: unchanged" in err and "alpha: 4 files" in err
    assert _tree(public) == _tree(_full_build_elsewhere(site, tmp_path / "1"))

    # beta だけが変わっても、beta の中身を GitHub の URL で指す alpha は作り直す
    (beta / "app.py").unlink()
    commit(beta, {"lib.py": "w = 5\n"})
    public, err = _build_incremental(site)
    assert "alpha: unchanged" not in err
    assert _tree(public) == _tree(_full_build_elsewhere(site, tmp_path / "2"))

    # 消えたリポのページは残らない
    shutil.rmtree(site.home / "work" / "gamma")
    public, err = _build_incremental(site)
    assert not (public / "gamma").exists()
    assert _tree(public) == _tree(_full_build_elsewhere(site, tmp_path / "3"))
