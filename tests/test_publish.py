"""配信の指紋が、走査対象の HEAD と GitHub の Issue の動きで変わることを確かめる。"""

from __future__ import annotations

from conftest import commit, gh_row


def test_fingerprint_stable_without_changes(site):
    assert site.fingerprint() == site.fingerprint()


def test_fingerprint_changes_with_head(site):
    before = site.fingerprint()
    commit(site.home / "own" / "alpha", {"new.py": "n = 1\n"})
    assert site.fingerprint() != before


def test_fingerprint_changes_with_github_issue_update(site):
    before = site.fingerprint()
    site.set_gh("beta", [gh_row(7, "beta の問い", "2026-03-01T00:00:00Z")])
    assert site.fingerprint() != before


def test_fingerprint_ignores_uncommitted(site):
    before = site.fingerprint()
    (site.home / "own" / "alpha" / "scratch.py").write_text("s = 1\n")
    assert site.fingerprint() == before


def test_publish_writes_into_the_config_repo(site):
    proc = site.run("-m", "codeview", "publish", "--dry-run")
    assert "dry-run" in proc.stdout
    assert (site.config.parent / "public" / "index.html").is_file()
    assert (site.config.parent / "functions" / "_middleware.js").is_file()
