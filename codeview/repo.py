"""repo — Git repository scanning and blob extraction."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from . import config


def repos() -> list[tuple[str, Path]]:
    """走査対象のリポジトリを (グループ名, パス) で返す。"""
    found = []
    cfg = config.load()
    for root in cfg.roots:
        if root.path is not None:
            if (root.path / ".git").is_dir():
                found.append((root.group, root.path))
            continue
        if not root.children.is_dir():
            continue
        for path in sorted(root.children.iterdir()):
            if path.name.startswith(".") or path.name in cfg.skip_dirs:
                continue
            if (path / ".git").is_dir():
                found.append((root.group, path))
    return found


def tracked_blobs(repo: Path) -> list[tuple[str, str]]:
    """HEAD に含まれる (パス, blob sha) を返す。コミットが1つも無ければ空。"""
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "HEAD"],
        cwd=repo,
        capture_output=True,
    )
    if proc.returncode != 0:
        return []
    entries = []
    for record in proc.stdout.split(b"\0"):
        if not record:
            continue
        meta, _, path = record.partition(b"\t")
        parts = meta.split()
        if len(parts) < 3 or parts[1] != b"blob":
            continue
        entries.append((path.decode("utf-8", "replace"), parts[2].decode()))
    return entries


def read_blobs(repo: Path, shas: list[str]) -> dict[str, bytes]:
    """blob を一括で読む。sha -> bytes。"""
    blobs = {}
    if not shas:
        return blobs
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=repo,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    try:
        for sha in shas:
            proc.stdin.write(sha.encode() + b"\n")
            proc.stdin.flush()
            header = proc.stdout.readline().split()
            if len(header) < 3:
                continue
            size = int(header[2])
            blobs[sha] = proc.stdout.read(size)
            proc.stdout.read(1)
    finally:
        proc.stdin.close()
        proc.wait()
    return blobs


def branch(repo: Path) -> str | None:
    """HEAD が指すブランチ名。detached なら None。"""
    proc = subprocess.run(
        ["git", "symbolic-ref", "-q", "--short", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() or None


def remote_host(repo: Path) -> str | None:
    """`origin` の URL からホスト名を取り出す。remote が無ければ None。"""
    proc = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    url = proc.stdout.strip()
    # scp 形式（`git@github.com:o/r.git`、`work:o/r.git`）と URL 形式の両方
    m = re.match(r"^[a-z+]+://(?:[^@/]+@)?([^/:]+)", url) or re.match(
        r"^(?:[^@/:]+@)?([^/:]+):", url
    )
    return m.group(1) if m else None


def owner_repo(repo: Path) -> str:
    proc = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    url = proc.stdout.strip()
    # scp 形式（`<host>:<owner>/<repo>.git`）と https 形式の両方を受ける
    m = re.search(r"[:/]([^/:]+/[^/:]+?)(?:\.git)?/?$", url)
    if not m:
        raise RuntimeError(f"no owner/repo in remote: {url or '(none)'}")
    return m.group(1)


def account_of(group: str, repo: Path) -> str | None:
    """Issue の台帳を持つアカウント名。remote のホストが決め手で、無ければ置き場のグループ。

    どちらにも当たらなければ None（Issue の集計から外す）。
    """
    accounts = config.load().accounts
    host = remote_host(repo)
    if host:
        for account in accounts:
            if host in account.hosts:
                return account.name
    for account in accounts:
        if group in account.groups:
            return account.name
    return None
