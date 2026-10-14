"""issues — 未消化の Issue をアカウントごとに集める。

取り込み元はアカウントの設定で決まる。`issues = "github"` は各リポの GitHub Issue（open）、
それ以外は設定に挙げた拡張の `issues()` が返すもの。アカウントをまたぐ参照は作らない。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import config, plugins
from .repo import account_of, owner_repo

GH_TIMEOUT = 60
# 指紋は毎時の判定で回るので、本文やコメントまでは取りに行かない
GH_FIELDS = "number,title,labels,updatedAt,url"
GH_FIELDS_FULL = "number,title,labels,updatedAt,body,author,createdAt,comments"

FAILED_MARK = "fetch-failed"

@dataclass
class Wait:
    """同じアカウントの未消化の Issue への依存。href は本体が埋める。"""

    repo: str
    ref: str
    href: str = ""


@dataclass
class Comment:
    author: str
    created: int
    body: str


@dataclass
class Issue:
    account: str
    repo: str
    slug: str
    ref: str
    title: str
    kind: str
    state: str
    updated: int
    # Issue ページの URL。同じアカウントに同名のリポがあれば slug 側で分ける
    href: str = ""
    labels: list[str] = field(default_factory=list)
    author: str = ""
    created: int = 0
    body: str = ""
    comments: list[Comment] = field(default_factory=list)
    # 本文を Markdown の生の HTML ごと出してよいか。他の人の文章が混ざる取り込み元では False
    trusted: bool = False
    # 元の Issue があるファイルのページ（リポの中に台帳がある取り込み元だけ）
    source: str = ""
    waits: list[Wait] = field(default_factory=list)
    # Issue が対象に挙げたリポ内のパス。そのファイルのページから Issue へリンクする
    targets: list[str] = field(default_factory=list)


@dataclass
class Board:
    issues: dict[str, list[Issue]]
    failed: dict[str, list[str]]
    # (slug, repo 内のパス) -> その中を対象に挙げた Issue
    by_file: dict[tuple[str, str], list[Issue]]


def _gh(owner_repo: str, fields: str, config_dir: Path | None) -> list[dict]:
    # zsh の `gh` 関数は cwd で config dir を振り直すので、バイナリを直接呼んでここで固定する
    env = dict(os.environ)
    if config_dir is not None:
        env["GH_CONFIG_DIR"] = str(config_dir)
    proc = subprocess.run(
        [
            "gh", "issue", "list", "-R", owner_repo,
            "--state", "open", "--limit", "1000", "--json", fields,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=GH_TIMEOUT,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"gh exited {proc.returncode}")
    return json.loads(proc.stdout)


def _fetch_github(
    account: config.Account, repo: Path, fields: str = GH_FIELDS_FULL
) -> list[dict]:
    try:
        return _gh(owner_repo(repo), fields, account.gh_config_dir)
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError) as e:
        raise RuntimeError(str(e)) from e


def _epoch(iso: str) -> int:
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def _login(person: dict | None) -> str:
    return (person or {}).get("login") or "ghost"


def _from_github(account: str, repo: Path, slug: str, rows: list[dict]) -> list[Issue]:
    found = []
    for row in rows:
        labels = [label["name"] for label in row.get("labels", [])]
        comments = sorted(
            (
                Comment(
                    _login(c.get("author")),
                    _epoch(c.get("createdAt", "")),
                    c.get("body") or "",
                )
                for c in row.get("comments", [])
            ),
            key=lambda c: c.created,
        )
        updated = _epoch(row.get("updatedAt", ""))
        found.append(
            Issue(
                account=account,
                repo=repo.name,
                slug=slug,
                ref=str(row["number"]),
                title=row["title"],
                kind=", ".join(labels),
                state="Open",
                updated=updated,
                labels=labels,
                author=_login(row.get("author")),
                created=_epoch(row.get("createdAt", "")) or updated,
                body=row.get("body") or "",
                comments=comments,
            )
        )
    return found


def _assign_hrefs(issues: list[Issue]) -> None:
    """URL のリポ名は repo.name。同じアカウントに同名のリポがあれば slug で分ける。"""
    names = [i.repo for i in {(i.repo, i.slug): i for i in issues}.values()]
    for issue in issues:
        part = issue.repo if names.count(issue.repo) == 1 else issue.slug.replace("/", "--")
        issue.href = f"/issues/{issue.account}/{part}/{issue.ref}.html"


def _resolve_waits(issues: list[Issue]) -> None:
    """依存先が同じアカウントの一覧に載っているものだけ残し、href を埋める。"""
    index = {(i.repo, i.ref): i for i in issues}
    for issue in issues:
        waits = []
        for w in issue.waits:
            target = index.get((w.repo, w.ref))
            if target is not None and target is not issue:
                waits.append(Wait(target.repo, target.ref, target.href))
        issue.waits = waits


def collect(ctx: plugins.Context) -> Board:
    accounts = ctx.config.accounts
    issues: dict[str, list[Issue]] = {a.name: [] for a in accounts}
    failed: dict[str, list[str]] = {a.name: [] for a in accounts}

    owned: dict[str, list[plugins.Repo]] = {a.name: [] for a in accounts}
    for repo in ctx.repos:
        name = account_of(repo.group, repo.path)
        if name is not None:
            owned[name].append(repo)

    for account in accounts:
        if account.issues != "github":
            issues[account.name].extend(plugins.issues(ctx, account, owned[account.name]))

    def fetch(item):
        account, repo = item
        try:
            return item, _fetch_github(account, repo.path), None
        except RuntimeError as e:
            return item, None, e

    remote = [
        (a, repo) for a in accounts if a.issues == "github" for repo in owned[a.name]
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for (account, repo), rows, err in pool.map(fetch, remote):
            if err is not None:
                failed[account.name].append(repo.path.name)
                continue
            issues[account.name].extend(
                _from_github(account.name, repo.path, repo.slug, rows)
            )

    by_file: dict[tuple[str, str], list[Issue]] = {}
    for rows in issues.values():
        _assign_hrefs(rows)
        _resolve_waits(rows)
        for issue in rows:
            for path in issue.targets:
                by_file.setdefault((issue.slug, path), []).append(issue)
        rows.sort(key=lambda i: (-i.updated, i.repo, i.ref))
    return Board(issues, failed, by_file)


def github_fingerprint(account: config.Account, found: list[tuple[str, Path]]) -> str:
    """アカウントの open な Issue の number と updatedAt をまとめた指紋。

    取得に失敗したリポは固定の印にする。前回と同じ扱いにすると、復旧しても
    変化が見えず、失敗が続く間も無駄に配信し直してしまうため。
    """
    targets = [p for g, p in found if account_of(g, p) == account.name]

    def line(repo: Path) -> str:
        try:
            rows = _fetch_github(account, repo, GH_FIELDS)
        except RuntimeError:
            return f"{repo.name}\t{FAILED_MARK}"
        body = ",".join(
            f"{r['number']}:{r.get('updatedAt', '')}"
            for r in sorted(rows, key=lambda r: r["number"])
        )
        return f"{repo.name}\t{body}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        lines = sorted(pool.map(line, targets))
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()
