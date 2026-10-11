"""build → 配信ブランチへ push。

配信するリポは設定ファイルのあるリポで、生成物はその直下の public/ と functions/ に書く。

配信ブランチは親を持たない単一コミットとして毎回作り直す。生成物は全リポ分の HTML で
毎回ほぼ全ファイルが差し替わるため、履歴を積むとリポジトリが際限なく膨らむ。
作業ツリーに触らないよう、一時 index に載せて plumbing で木とコミットを作る。
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from codeview import config, plugins
from codeview.issues import github_fingerprint
from codeview.repo import repos

# Pages が配るのは公開ディレクトリと Functions だけ。生成器は配信ブランチに載せない
ASSETS = ("public", "functions")

_cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
STATE = _cache / "codeview" / "publish-state"


def _site() -> Path:
    where = config.load().source.parent
    try:
        top = subprocess.run(
            ["git", "-C", str(where), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        raise config.ConfigError(f"{where} is not in a git repository to publish from") from None
    return Path(top)


def _version() -> str:
    try:
        return metadata.version("codeview")
    except metadata.PackageNotFoundError:
        return "source"


def _git(*args: str, env: dict | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(_site()), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.strip()


def _tree_of_assets() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        # 生成物は作業ブランチでは無視されている。配信ブランチには載せる
        _git("add", "--force", "--", *ASSETS, env=env)
        return _git("write-tree", env=env)


def _fingerprint(ctx: plugins.Context) -> str:
    """走査対象リポの HEAD・GitHub の open な Issue・配信するリポの HEAD・本体の版をまとめた指紋。

    配信するリポの未コミット変更は指紋に出ない。定期実行が拾うのはコミット済みの状態だけで、
    手元の実験を配信させないため。手動 publish は指紋を見ないので確認はそちらで足りる。
    """
    found = repos()
    lines = []
    for group, path in found:
        try:
            head = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except subprocess.CalledProcessError:
            head = "-"
        lines.append(f"{group}/{path.name}\t{head}")
    # GitHub の Issue は HEAD に現れないので、GitHub 側の動きを別に見る
    for account in config.load().accounts:
        if account.issues == "github":
            lines.append(f"__{account.name}_issues__\t{github_fingerprint(account, found)}")
    lines.extend(f"__plugin__\t{line}" for line in plugins.fingerprint(ctx))
    lines.append(f"__site__\t{_git('rev-parse', 'HEAD')}")
    lines.append(f"__codeview__\t{_version()}")
    return hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest()


def publish(remote: str, branch: str, dry_run: bool, if_changed: bool) -> int:
    ctx = plugins.context()
    plugins.before_publish(ctx)
    # build 前に採る。生成中に元リポが動いた分は次回に回るほうが、取り落とすより安全
    fingerprint = _fingerprint(ctx)
    if if_changed and STATE.exists() and STATE.read_text().strip() == fingerprint:
        print("publish skipped: no change in the scan targets")
        return 0

    site = _site()
    subprocess.run(
        [sys.executable, "-m", "codeview", "build"],
        check=True,
        env={**os.environ, "CODEVIEW_OUT": str(site)},
    )

    public = site / "public"
    files = sum(1 for p in public.rglob("*") if p.is_file())
    if files == 0:
        print("publish aborted: nothing was generated", file=sys.stderr)
        return 1
    if files > 20000:
        print(f"publish aborted: {files} files exceed the Pages limit", file=sys.stderr)
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    message = f"site: {files} files ({stamp})"
    commit = _git("commit-tree", _tree_of_assets(), "-m", message)

    if dry_run:
        print(f"dry-run {commit[:8]} → {remote}/{branch}  {message}")
        return 0

    _git("push", "--force", remote, f"{commit}:refs/heads/{branch}")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(fingerprint + "\n")
    print(f"pushed {commit[:8]} → {remote}/{branch}  {message}")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        config.load()
        plugins.load()
    except (config.ConfigError, plugins.PluginError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(prog="codeview publish", description=__doc__.splitlines()[0])
    cfg = config.load()
    parser.add_argument("--remote", default=cfg.publish_remote)
    parser.add_argument("--branch", default=cfg.publish_branch)
    parser.add_argument("-n", "--dry-run", action="store_true")
    parser.add_argument(
        "--if-changed",
        action="store_true",
        help="do nothing if nothing changed since the last publish (for scheduled runs)",
    )
    args = parser.parse_args(argv)
    try:
        return publish(args.remote, args.branch, args.dry_run, args.if_changed)
    except config.ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

