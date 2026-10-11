"""plugins — 設定の `[plugins] modules` に並べた拡張モジュールを読み込み、決まった口で呼ぶ。

拡張は Python のモジュールで、次の関数を必要なものだけ持つ。持たない関数は呼ばない。

    css(ctx) -> str              本体の CSS の末尾に足す
    side(ctx) -> str             トップの左メニューの先頭に差し込む塊
    home(ctx) -> str | None      トップの右側に出す HTML。None なら出さない
    build(ctx) -> None           public/ と functions/ に自前のページを書く
    before_publish(ctx) -> None  配信の指紋を取る前に呼ぶ
    fingerprint(ctx) -> str      配信の指紋に足す1行
    issues(ctx, account, repos) -> list[Issue]
                                 アカウントの `issues` にこのモジュールを挙げたとき、
                                 そのアカウントのリポ（`Repo` の列）から未消化の Issue を返す

`home` の HTML に含まれる <script> は、本体がページ末尾へ移す。
拡張の設定は設定ファイルの `[plugins.<モジュール名の末尾>]` に置き、`ctx.options` で読む。
拡張のモジュールは、設定ファイルのあるディレクトリからも読める。
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import ModuleType
from typing import NamedTuple

from . import config
from .repo import read_blobs, repos, tracked_blobs


class PluginError(Exception):
    """拡張の読み込みの失敗。メッセージはそのまま利用者に出す。"""


class Repo(NamedTuple):
    group: str
    path: Path
    slug: str


@dataclass
class Context:
    config: config.Config
    repos: list[Repo]
    public: Path | None = None
    functions: Path | None = None
    # 生成の途中で本体が埋める。グループ名 -> [(slug, リポ名, ファイル数)]
    counts: dict = field(default_factory=dict)
    # 呼び出し先の拡張の設定表。呼ぶたびに差し替わる
    options: dict = field(default_factory=dict)

    @property
    def stats(self) -> str:
        total = sum(n for items in self.counts.values() for _, _, n in items)
        repo_count = sum(len(items) for items in self.counts.values())
        return f"{repo_count} repos / {total:,} files"

    def find(self, group: str, name: str) -> Repo | None:
        for repo in self.repos:
            if repo.group == group and repo.path.name == name:
                return repo
        return None

    def read(self, repo: Repo, path: str) -> bytes | None:
        """repo の HEAD にあるファイルを読む。無ければ None。"""
        sha = dict(tracked_blobs(repo.path)).get(path)
        if sha is None:
            return None
        return read_blobs(repo.path, [sha]).get(sha, b"")


def _slugged() -> list[Repo]:
    """走査対象を slug 付きで返す。リポ名が重なるものだけグループ付きの slug にする。"""
    found = repos()
    names = [path.name for _, path in found]
    return [
        Repo(group, path, path.name if names.count(path.name) == 1 else f"{group}/{path.name}")
        for group, path in found
    ]


def context(public: Path | None = None, functions: Path | None = None) -> Context:
    return Context(
        config=config.load(),
        repos=_slugged(),
        public=public,
        functions=functions,
    )


_loaded: list[tuple[str, ModuleType]] | None = None


def load() -> list[tuple[str, ModuleType]]:
    """設定の順に拡張を読み込む。1つでも失敗したら PluginError。"""
    global _loaded
    if _loaded is None:
        loaded = []
        # 本体をパッケージとして入れても、設定の隣に置いた拡張を読めるようにする
        base = str(config.load().source.parent)
        if base not in sys.path:
            sys.path.insert(0, base)
        for name in config.load().plugins:
            try:
                loaded.append((name, importlib.import_module(name)))
            except Exception as e:
                raise PluginError(f"cannot load plugin '{name}': {e}") from e
        modules = dict(loaded)
        for account in config.load().accounts:
            source = modules.get(account.issues)
            if account.issues != "github" and not callable(getattr(source, "issues", None)):
                raise PluginError(
                    f"plugin '{account.issues}' has no issues() for account '{account.name}'"
                )
        _loaded = loaded
    return _loaded


def _with_options(ctx: Context, name: str) -> Context:
    return replace(ctx, options=ctx.config.plugin_options.get(config.plugin_key(name), {}))


def _each(ctx: Context, func: str):
    for name, module in load():
        fn = getattr(module, func, None)
        if callable(fn):
            yield fn(_with_options(ctx, name))


def css(ctx: Context) -> str:
    return "\n".join(out for out in _each(ctx, "css") if out)


def side(ctx: Context) -> str:
    return "".join(out for out in _each(ctx, "side") if out)


def home(ctx: Context) -> list[str]:
    return [out for out in _each(ctx, "home") if out]


def build(ctx: Context) -> None:
    for _ in _each(ctx, "build"):
        pass


def before_publish(ctx: Context) -> None:
    for _ in _each(ctx, "before_publish"):
        pass


def fingerprint(ctx: Context) -> list[str]:
    return [out for out in _each(ctx, "fingerprint") if out]


def issues(ctx: Context, account: config.Account, owned: list[Repo]) -> list:
    module = dict(load())[account.issues]
    return module.issues(_with_options(ctx, account.issues), account, owned)
