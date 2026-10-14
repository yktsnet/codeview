"""GitHub の Issue の一覧・ページと、アカウントごとの取得を生成物で確かめる。"""

from __future__ import annotations

import re
from html.parser import HTMLParser


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = []

    def handle_starttag(self, tag, attrs):
        self.found += [v for k, v in attrs if k in ("href", "src") and v]


def test_github_issue_page_comments_oldest_first(site):
    public, _ = site.build()
    page = (public / "issues" / "work" / "beta" / "7.html").read_text()
    assert "beta の問い" in page
    assert page.index("一つ目") < page.index("二つ目のコメント")
    assert "carol" in page and "bob" in page
    assert "github.com/org" not in page


def test_issue_pages_link_relatively(site):
    public, _ = site.build()
    page = (public / "issues" / "work" / "beta" / "7.html").read_text()
    # 戻るリンク・左の一覧・CSS は、ページの位置からの相対パスで実在するファイルを指す
    assert 'id="back" href="index.html"' in page
    assert 'href="../index.html"' in page
    assert 'href="7.html"' in page
    assert re.search(r'href="\.\./\.\./\.\./style\.[0-9a-f]+\.css"', page)
    for page_path in (public / "issues").rglob("*.html"):
        parser = _Links()
        parser.feed(page_path.read_text())
        for link in parser.found:
            if link.startswith(("http:", "https:", "#", "//")):
                continue
            assert not link.startswith("/"), f"{page_path}: {link}"
            assert (page_path.parent / link.split("#")[0]).resolve().is_file(), f"{page_path}: {link}"


def test_github_raw_html_is_escaped(site):
    public, _ = site.build()
    page = (public / "issues" / "work" / "beta" / "7.html").read_text()
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
    # 属性の文字は本文として残ってよい。タグとして出ていないことを見る
    assert "<img" not in page
    assert "&lt;img src=x" in page


def test_github_fetch_failure_does_not_stop_build(site):
    public, proc = site.build()
    listing = (public / "issues" / "work" / "index.html").read_text()
    assert "fetch failed: gamma" in listing
    assert "beta の問い" in listing
    assert "fetch failed: gamma" in proc.stderr


def test_two_accounts_use_their_own_gh_config(site):
    public, _ = site.build()
    assert "alpha の問い" in (public / "issues" / "me" / "index.html").read_text()
    assert "beta の問い" in (public / "issues" / "work" / "index.html").read_text()
    calls = dict(site.gh_calls())
    assert calls["alpha"] == "-"
    assert calls["beta"].endswith("/.config/gh-work")
