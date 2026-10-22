"""build → 配信ブランチへ push。

配信するリポは設定ファイルのあるリポで、生成物はその直下の public/ と functions/ に書く。

配信ブランチは親を持たない単一コミットとして毎回作り直す。生成物は全リポ分の HTML で
毎回ほぼ全ファイルが差し替わるため、履歴を積むとリポジトリが際限なく膨らむ。
作業ツリーに触らないよう、一時 index に載せて plumbing で木とコミットを作る。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from codeview import config, plugins
from codeview.repo import account_of, repos

# Pages が配るのは公開ディレクトリと Functions だけ。生成器は配信ブランチに載せない
ASSETS = ("public", "functions")

_cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
STATE = _cache / "codeview" / "publish-state"
# 定期実行の起動は数秒〜数十秒ずれる。間隔ちょうどの回を見送って一周遅れないよう、その分を差し引く
SLACK = 300


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


def _digest(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest()


def _head(path: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return "-"


def _fingerprint(ctx: plugins.Context) -> dict:
    """配信の指紋。`accounts` はアカウントごとの走査対象リポの HEAD、`global` はそれ以外
    （拡張の行・配信するリポの HEAD・本体の版）。

    GitHub の Issue は見ない。Issue だけの動きでは配信せず、次にコミットで配信するときに載る。
    配信するリポの未コミット変更も指紋に出ない。定期実行が拾うのはコミット済みの状態だけで、
    手元の実験を配信させないため。手動 publish は指紋を見ないので確認はそちらで足りる。
    """
    accounts: dict[str, list[str]] = {}
    for group, path in repos():
        # どのアカウントにも属さないリポは "" にまとめ、毎回見る
        name = account_of(group, path) or ""
        accounts.setdefault(name, []).append(f"{group}/{path.name}\t{_head(path)}")
    rest = [f"__plugin__\t{line}" for line in plugins.fingerprint(ctx)]
    rest.append(f"__site__\t{_git('rev-parse', 'HEAD')}")
    rest.append(f"__codeview__\t{_version()}")
    return {
        "global": _digest(rest),
        "accounts": {name: _digest(lines) for name, lines in accounts.items()},
    }


def _load_state() -> dict | None:
    try:
        state = json.loads(STATE.read_text())
    except (OSError, ValueError):
        return None
    # 指紋だけを書いていた旧形式は、状態なしとして一度配信し直す
    if not isinstance(state, dict) or not isinstance(state.get("accounts"), dict):
        return None
    return state


def _due(prev: dict, now: int) -> set[str]:
    """前回の状態のうち、今回変化を見るアカウント。`check_every_hours` が経っていないものは見ない。"""
    every = {a.name: a.check_every_hours for a in config.load().accounts}
    due = set()
    for name, entry in prev["accounts"].items():
        hours = every.get(name)
        if not hours or now - entry.get("checked", 0) >= hours * 3600 - SLACK:
            due.add(name)
    return due


def _changed(prev: dict, current: dict, due: set[str]) -> bool:
    if prev.get("global") != current["global"]:
        return True
    old = prev["accounts"]
    # アカウントが増えた・消えたときは、間隔を待たずに配信する
    if set(old) != set(current["accounts"]):
        return True
    return any(old[name].get("digest") != current["accounts"][name] for name in due)


def _save(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, sort_keys=True) + "\n")


def publish(remote: str, branch: str, dry_run: bool, if_changed: bool) -> int:
    ctx = plugins.context()
    plugins.before_publish(ctx)
    # build 前に採る。生成中に元リポが動いた分は次回に回るほうが、取り落とすより安全
    fingerprint = _fingerprint(ctx)
    now = int(time.time())
    prev = _load_state() if if_changed else None
    if prev is not None:
        due = _due(prev, now)
        if not _changed(prev, fingerprint, due):
            # 見た時刻だけ進める。digest は前回の配信のものを残し、まだ見ていない変化を取り落とさない
            for name in due:
                prev["accounts"][name]["checked"] = now
            _save(prev)
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
    _save(
        {
            "global": fingerprint["global"],
            "accounts": {
                name: {"digest": digest, "checked": now}
                for name, digest in fingerprint["accounts"].items()
            },
        }
    )
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

