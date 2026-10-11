"""走査・ファイルページ・拡張・設定の誤りを、生成物で確かめる。"""

from __future__ import annotations


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
