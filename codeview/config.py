"""config — 走査対象・アカウント・配信先を設定ファイル（TOML）から読む。

場所は環境変数 `CODEVIEW_CONFIG`、無ければ作業ディレクトリの `codeview.toml`。
読めない・書式が誤っているときは `ConfigError` で止める。既定値で続行はしない。
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ENV = "CODEVIEW_CONFIG"
DEFAULT_NAME = "codeview.toml"

MAX_ACCOUNTS = 2


class ConfigError(Exception):
    """設定の誤り。メッセージはそのまま利用者に出す。"""


@dataclass(frozen=True)
class Root:
    group: str
    # `path` は 1 つのリポそのもの、`children` は直下の git リポすべて
    path: Path | None = None
    children: Path | None = None


@dataclass(frozen=True)
class Account:
    name: str
    hosts: tuple[str, ...]
    groups: tuple[str, ...]
    # "github" か、Issue を返す拡張のモジュール名
    issues: str = "github"
    gh_config_dir: Path | None = None


@dataclass(frozen=True)
class Config:
    source: Path
    roots: tuple[Root, ...]
    skip_dirs: frozenset[str] = frozenset()
    exclude_prefixes: tuple[str, ...] = ()
    skip_exts: tuple[str, ...] = ()
    accounts: tuple[Account, ...] = ()
    publish_remote: str = "origin"
    publish_branch: str = "deploy"
    # 読み込む拡張のモジュール名（並べた順）と、拡張ごとの設定表（モジュール名の末尾で引く）
    plugins: tuple[str, ...] = ()
    plugin_options: dict = field(default_factory=dict)


def config_path() -> Path:
    env = os.environ.get(ENV)
    return Path(env).expanduser() if env else Path.cwd() / DEFAULT_NAME


def _expand(value: str) -> Path:
    return Path(value).expanduser()


def _table(parent: dict, key: str, where: str) -> dict:
    value = parent.get(key, {})
    if not isinstance(value, dict):
        raise ConfigError(f"{where}: [{key}] must be a table")
    return value


def _array(parent: dict, key: str, where: str, required: bool = False) -> list:
    if key not in parent:
        if required:
            raise ConfigError(f"{where}: missing [[{key}]]")
        return []
    value = parent[key]
    if not isinstance(value, list):
        raise ConfigError(f"{where}: '{key}' must be an array")
    return value


def _str(row: dict, key: str, where: str, required: bool = True) -> str | None:
    if key not in row:
        if required:
            raise ConfigError(f"{where}: missing '{key}'")
        return None
    value = row[key]
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{where}: '{key}' must be a non-empty string")
    return value


def _strs(row: dict, key: str, where: str) -> tuple[str, ...]:
    value = row.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise ConfigError(f"{where}: '{key}' must be an array of non-empty strings")
    return tuple(value)


def _unknown(row: dict, allowed: tuple[str, ...], where: str) -> None:
    extra = sorted(set(row) - set(allowed))
    if extra:
        raise ConfigError(f"{where}: unknown key '{extra[0]}'")


def _roots(data: dict, src: Path) -> tuple[Root, ...]:
    roots = []
    for i, row in enumerate(_array(data, "roots", str(src), required=True), 1):
        where = f"{src}: roots[{i}]"
        if not isinstance(row, dict):
            raise ConfigError(f"{where}: must be a table")
        _unknown(row, ("group", "path", "children"), where)
        group = _str(row, "group", where)
        path = _str(row, "path", where, required=False)
        children = _str(row, "children", where, required=False)
        if (path is None) == (children is None):
            raise ConfigError(f"{where}: set exactly one of 'path' or 'children'")
        roots.append(
            Root(group, _expand(path) if path else None, _expand(children) if children else None)
        )
    if not roots:
        raise ConfigError(f"{src}: [[roots]] is empty")
    groups = [r.group for r in roots]
    dup = next((g for g in groups if groups.count(g) > 1), None)
    if dup:
        raise ConfigError(f"{src}: duplicate roots group '{dup}'")
    return tuple(roots)


def _accounts(data: dict, src: Path, plugins: tuple[str, ...]) -> tuple[Account, ...]:
    accounts = []
    rows = _array(data, "accounts", str(src), required=True)
    if not 1 <= len(rows) <= MAX_ACCOUNTS:
        raise ConfigError(f"{src}: [[accounts]] must have 1 to {MAX_ACCOUNTS} entries")
    for i, row in enumerate(rows, 1):
        where = f"{src}: accounts[{i}]"
        if not isinstance(row, dict):
            raise ConfigError(f"{where}: must be a table")
        _unknown(row, ("name", "hosts", "groups", "issues", "gh_config_dir"), where)
        issues = _str(row, "issues", where, required=False) or "github"
        if issues != "github" and issues not in plugins:
            raise ConfigError(
                f"{where}: 'issues' must be \"github\" or a module in [plugins] modules"
            )
        gh_dir = _str(row, "gh_config_dir", where, required=False)
        if gh_dir and issues != "github":
            raise ConfigError(f"{where}: 'gh_config_dir' needs issues = \"github\"")
        accounts.append(
            Account(
                name=_str(row, "name", where),
                hosts=_strs(row, "hosts", where),
                groups=_strs(row, "groups", where),
                issues=issues,
                gh_config_dir=_expand(gh_dir) if gh_dir else None,
            )
        )
    names = [a.name for a in accounts]
    dup = next((n for n in names if names.count(n) > 1), None)
    if dup:
        raise ConfigError(f"{src}: duplicate account '{dup}'")
    return tuple(accounts)


def plugin_key(module: str) -> str:
    """拡張の設定表 `[plugins.<key>]` の key。モジュール名の末尾。"""
    return module.rsplit(".", 1)[-1]


def _plugins(data: dict, src: Path) -> tuple[tuple[str, ...], dict]:
    where = f"{src}: [plugins]"
    table = _table(data, "plugins", str(src))
    modules = _strs(table, "modules", where)
    if len(set(modules)) != len(modules):
        raise ConfigError(f"{where}: duplicate module in 'modules'")
    keys = [plugin_key(m) for m in modules]
    dup = next((k for k in keys if keys.count(k) > 1), None)
    if dup:
        raise ConfigError(f"{where}: modules share the options table name '{dup}'")
    options = {}
    for key, value in table.items():
        if key == "modules":
            continue
        if not isinstance(value, dict):
            raise ConfigError(f"{where}: unknown key '{key}'")
        options[key] = value
    return modules, options


@lru_cache(maxsize=1)
def load() -> Config:
    src = config_path()
    try:
        data = tomllib.loads(src.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(
            f"config not found: {src} (create it, or point {ENV} at one)"
        ) from None
    except (OSError, UnicodeDecodeError) as e:
        raise ConfigError(f"cannot read config: {src}: {e}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"invalid TOML in {src}: {e}") from e

    scan = _table(data, "scan", str(src))
    _unknown(scan, ("skip_dirs", "exclude_prefixes", "skip_exts"), f"{src}: [scan]")
    publish = _table(data, "publish", str(src))
    _unknown(publish, ("remote", "branch"), f"{src}: [publish]")
    plugins, plugin_options = _plugins(data, src)
    accounts = _accounts(data, src, plugins)

    return Config(
        source=src,
        roots=_roots(data, src),
        skip_dirs=frozenset(_strs(scan, "skip_dirs", f"{src}: [scan]")),
        exclude_prefixes=_strs(scan, "exclude_prefixes", f"{src}: [scan]"),
        skip_exts=tuple(e.lower() for e in _strs(scan, "skip_exts", f"{src}: [scan]")),
        accounts=accounts,
        publish_remote=_str(publish, "remote", f"{src}: [publish]", required=False) or "origin",
        publish_branch=_str(publish, "branch", f"{src}: [publish]", required=False) or "deploy",
        plugins=plugins,
        plugin_options=plugin_options,
    )
