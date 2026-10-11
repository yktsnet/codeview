"""配信の指紋が、走査対象の HEAD と GitHub の Issue の動きで変わることを確かめる。"""

from __future__ import annotations

import subprocess

from conftest import commit, gh_row, git


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


def _with_remote(site, tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    git(site.config.parent, "remote", "add", "origin", str(remote))
    return remote


def test_publish_pushes_single_commit_of_assets(site, tmp_path):
    remote = _with_remote(site, tmp_path)
    site.run("-m", "codeview", "publish")
    assert git(remote, "rev-list", "--parents", "-n1", "deploy").count(" ") == 0
    assert git(remote, "ls-tree", "--name-only", "deploy").split() == ["functions", "public"]


def test_publish_if_changed_skips_without_changes(site, tmp_path):
    remote = _with_remote(site, tmp_path)
    site.run("-m", "codeview", "publish", "--if-changed")
    first = git(remote, "rev-parse", "deploy")
    proc = site.run("-m", "codeview", "publish", "--if-changed")
    assert "skipped" in proc.stdout
    assert git(remote, "rev-parse", "deploy") == first
