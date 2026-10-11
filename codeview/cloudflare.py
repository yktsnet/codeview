"""cloudflare — Cloudflare API の呼び出しと資格情報の読み込み。

資格情報は環境変数 `CF_API_TOKEN` と `CF_ACCOUNT_ID`。無ければ `CF_ENV_FILE` が指す
dotenv 形式のファイルから読む。日常の配信（codeview publish）は使わず、初回設定と状態確認だけが使う。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.cloudflare.com/client/v4"
KEYS = ("CF_API_TOKEN", "CF_ACCOUNT_ID")


def load_env() -> tuple[str, str]:
    values = {k: os.environ.get(k, "") for k in KEYS}
    env_file = os.environ.get("CF_ENV_FILE")
    if not all(values.values()) and env_file:
        for line in Path(env_file).expanduser().read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().removeprefix("export ").strip()
            if key in values and not values[key]:
                values[key] = value.strip().strip("\"'")
    missing = [k for k, v in values.items() if not v]
    if missing:
        sys.exit(f"error: set {' and '.join(missing)} (or point CF_ENV_FILE at a file with them)")
    return values["CF_API_TOKEN"], values["CF_ACCOUNT_ID"]


def api(token: str, method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        # 4xx でも Cloudflare は errors[] を JSON で返すので、本文を読んで返す
        return json.load(e)


def github_repo(remote: str, cwd: Path) -> tuple[str, str]:
    """配信ブランチを push する remote の owner と repo 名。"""
    url = subprocess.run(
        ["git", "-C", str(cwd), "remote", "get-url", remote],
        capture_output=True,
        text=True,
    ).stdout.strip()
    m = re.search(r"[:/]([^/:]+)/([^/:]+?)(?:\.git)?/?$", url)
    if not m:
        sys.exit(f"error: no owner/repo in remote '{remote}': {url or '(none)'}")
    return m.group(1), m.group(2)
