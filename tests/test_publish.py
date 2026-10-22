"""配信の指紋が走査対象の HEAD で変わり、GitHub の Issue では変わらないことと、
アカウントごとの間隔で変化を見ることを確かめる。"""

from __future__ import annotations

import json
import subprocess
import time

from conftest import commit, gh_row, git


def test_fingerprint_stable_without_changes(site):
    assert site.fingerprint() == site.fingerprint()


def test_fingerprint_changes_with_head(site):
    before = site.fingerprint()
    commit(site.home / "own" / "alpha", {"new.py": "n = 1\n"})
    assert site.fingerprint() != before


def test_fingerprint_ignores_github_issue_update(site):
    before = site.fingerprint()
    site.set_gh("beta", [gh_row(7, "beta の問い", "2026-03-01T00:00:00Z")])
    assert site.fingerprint() == before
    # 指紋を取るだけでは GitHub に問い合わせない
    assert site.gh_calls() == []


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


def test_publish_if_changed_skips_issue_only_change(site, tmp_path):
    remote = _with_remote(site, tmp_path)
    site.run("-m", "codeview", "publish", "--if-changed")
    first = git(remote, "rev-parse", "deploy")
    site.set_gh("beta", [gh_row(7, "beta の問い", "2026-03-01T00:00:00Z")])
    proc = site.run("-m", "codeview", "publish", "--if-changed")
    assert "skipped" in proc.stdout
    assert git(remote, "rev-parse", "deploy") == first


def _state(site, tmp_path) -> Path:
    return tmp_path / "cache" / "codeview" / "publish-state"


def test_publish_checks_account_at_its_interval(site, tmp_path):
    site.write_config(
        site.config.read_text().replace(
            'gh_config_dir = "', 'check_every_hours = 2\ngh_config_dir = "', 1
        )
    )
    remote = _with_remote(site, tmp_path)
    site.run("-m", "codeview", "publish", "--if-changed")
    first = git(remote, "rev-parse", "deploy")

    # 間隔の経っていないアカウントのコミットでは配信しない
    commit(site.home / "work" / "beta", {"new.py": "n = 1\n"})
    proc = site.run("-m", "codeview", "publish", "--if-changed")
    assert "skipped" in proc.stdout
    assert git(remote, "rev-parse", "deploy") == first

    # 間隔の無いアカウントのコミットは、すぐ配信する
    commit(site.home / "own" / "alpha", {"new.py": "n = 1\n"})
    proc = site.run("-m", "codeview", "publish", "--if-changed")
    assert "pushed" in proc.stdout
    second = git(remote, "rev-parse", "deploy")
    assert second != first

    # 間隔が経てば、そのアカウントのコミットで配信する。起動のずれの分は早めに見る
    commit(site.home / "work" / "beta", {"more.py": "m = 1\n"})
    path = _state(site, tmp_path)
    state = json.loads(path.read_text())
    state["accounts"]["work"]["checked"] = int(time.time()) - 2 * 3600 + 60
    path.write_text(json.dumps(state))
    proc = site.run("-m", "codeview", "publish", "--if-changed")
    assert "pushed" in proc.stdout
    assert git(remote, "rev-parse", "deploy") != second


def test_publish_if_changed_republishes_over_old_state(site, tmp_path):
    # 指紋だけを書いていた旧形式の状態は、無いものとして配信する
    remote = _with_remote(site, tmp_path)
    path = _state(site, tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("0" * 64 + "\n")
    proc = site.run("-m", "codeview", "publish", "--if-changed")
    assert "pushed" in proc.stdout
    assert git(remote, "rev-parse", "deploy")


def test_check_every_hours_must_be_positive_integer(site):
    for bad in ("0", "1.5", "true", '"2"'):
        site.write_config(
            site.config.read_text().replace(
                'gh_config_dir = "', f'check_every_hours = {bad}\ngh_config_dir = "', 1
            )
        )
        proc = site.run("-m", "codeview", "publish", "--dry-run", check=False)
        assert proc.returncode != 0
        assert "check_every_hours" in proc.stderr
        site.write_config(
            site.config.read_text().replace(f"check_every_hours = {bad}\n", "", 1)
        )
