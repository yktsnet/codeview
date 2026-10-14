"""見本のリポ群・設定・偽の gh を一時ディレクトリに作り、生成器を別プロセスで回す。

生成器は設定と拡張をプロセスの中でキャッシュするので、ケースごとに別プロセスで呼ぶ。
設定は git リポ（配信するリポ）の中に置き、`codeview` をそこで動かす。
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# 偽の gh。`-R <owner>/<repo>` を見て、$FAKE_GH_DIR/<repo>.json を返す。無ければ失敗する。
# 呼ばれた repo と GH_CONFIG_DIR を calls.log に残す
FAKE_GH = """#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
repo = args[args.index("-R") + 1].split("/")[-1]
with open(os.path.join(os.environ["FAKE_GH_DIR"], "calls.log"), "a") as log:
    log.write(repo + "\\t" + os.environ.get("GH_CONFIG_DIR", "-") + "\\n")
path = os.path.join(os.environ["FAKE_GH_DIR"], repo + ".json")
if not os.path.exists(path):
    sys.stderr.write("could not resolve to a repository\\n")
    sys.exit(1)
sys.stdout.write(open(path).read())
"""


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def make_repo(path: Path, files: dict[str, str], remote: str | None = None) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "test@example.invalid")
    git(path, "config", "user.name", "tester")
    for name, body in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    git(path, "add", "-A")
    git(path, "commit", "-qm", "init")
    if remote:
        git(path, "remote", "add", "origin", remote)
    return path


def commit(repo: Path, files: dict[str, str]) -> None:
    for name, body in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(body)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "update")


def gh_row(number: int, title: str, updated: str, body: str = "", comments=()) -> dict:
    return {
        "number": number,
        "title": title,
        "labels": [{"name": "question"}],
        "updatedAt": updated,
        "url": f"https://github.com/org/x/issues/{number}",
        "body": body,
        "author": {"login": "alice"},
        "createdAt": "2026-01-01T00:00:00Z",
        "comments": [
            {"author": {"login": who}, "createdAt": at, "body": text}
            for who, at, text in comments
        ],
    }


CONFIG = """
[[roots]]
group = "own"
children = "{home}/own"

[[roots]]
group = "work"
children = "{home}/work"

[scan]
skip_dirs = ["00archive"]
exclude_prefixes = ["secrets/"]
skip_exts = [".png"]

[[accounts]]
name = "me"
hosts = ["github.com"]
groups = ["own"]

[[accounts]]
name = "work"
hosts = ["github-work"]
groups = ["work"]
issues = "github"
gh_config_dir = "{home}/.config/gh-work"

[publish]
remote = "origin"
branch = "deploy"
"""


@dataclass
class Site:
    home: Path
    config: Path
    gh_dir: Path
    env: dict

    def write_config(self, text: str) -> None:
        self.config.write_text(text)

    def gh_calls(self) -> list[tuple[str, str]]:
        log = self.gh_dir / "calls.log"
        if not log.exists():
            return []
        return [tuple(line.split("\t")) for line in log.read_text().splitlines()]

    def set_gh(self, repo: str, rows: list[dict] | None) -> None:
        path = self.gh_dir / f"{repo}.json"
        if rows is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(json.dumps(rows))

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, *args],
            cwd=self.config.parent,
            env=self.env,
            capture_output=True,
            text=True,
            check=check,
        )

    def build(self, check: bool = True) -> tuple[Path, subprocess.CompletedProcess]:
        out = Path(self.env["CODEVIEW_OUT"])
        proc = self.run("-m", "codeview", "build", check=check)
        return out / "public", proc

    def fingerprint(self) -> str:
        code = "from codeview import publish, plugins as p; print(publish._fingerprint(p.context()))"
        return self.run("-c", code).stdout.strip()


@pytest.fixture
def site(tmp_path: Path) -> Site:
    home = tmp_path / "home"
    own = home / "own"
    work = home / "work"

    make_repo(
        own / "alpha",
        {
            "main.py": 'print("hello")\n',
            "README.md": "# alpha\n\nalpha の説明\n",
            "secrets/token.txt": "secret\n",
            "logo.png": "not really a png\n",
            "docs/guide.md": "# guide\n",
        },
        remote="git@github.com:me/alpha.git",
    )
    (own / "alpha" / "uncommitted.py").write_text("print('wip')\n")

    make_repo(own / "00archive" / "old", {"a.py": "x = 1\n"})
    # worktree は .git がファイルになる
    wt = own / "wt"
    wt.mkdir(parents=True)
    (wt / ".git").write_text("gitdir: /nowhere\n")
    (wt / "b.py").write_text("y = 2\n")

    make_repo(work / "beta", {"app.py": "z = 3\n"}, remote="github-work:org/beta.git")
    make_repo(work / "gamma", {"g.py": "g = 4\n"}, remote="github-work:org/gamma.git")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    gh_dir = tmp_path / "gh"
    gh_dir.mkdir()

    config = tmp_path / "site" / "codeview.toml"
    make_repo(config.parent, {"codeview.toml": textwrap.dedent(CONFIG).format(home=home)})

    # 端末の GH_CONFIG_DIR が漏れると、gh_config_dir を設定しないアカウントの呼び出しに乗る
    env = {
        **{k: v for k, v in os.environ.items() if k != "GH_CONFIG_DIR"},
        "HOME": str(home),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "PYTHONPATH": str(ROOT),
        "CODEVIEW_CONFIG": str(config),
        "CODEVIEW_OUT": str(tmp_path / "out"),
        "FAKE_GH_DIR": str(gh_dir),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
    }
    s = Site(home=home, config=config, gh_dir=gh_dir, env=env)
    s.set_gh("alpha", [gh_row(3, "alpha の問い", "2026-03-01T00:00:00Z")])
    s.set_gh(
        "beta",
        [
            gh_row(
                7,
                "beta の問い",
                "2026-02-01T00:00:00Z",
                body="<script>alert(1)</script> 本文",
                comments=[
                    ("bob", "2026-02-02T00:00:00Z", "二つ目のコメント"),
                    ("carol", "2026-01-15T00:00:00Z", '<img src=x onerror="alert(2)"> 一つ目'),
                ],
            )
        ],
    )
    # gamma の JSON は置かない（取得に失敗するリポ）
    return s
