"""Cloudflare Pages プロジェクト + カスタムドメイン + Access を一度だけ作る。

    codeview cf-setup code.example.net [--project NAME]

Pages は、設定の `[publish]` の remote（GitHub）の配信ブランチを見る。プロジェクト名の
既定はそのリポ名。日常の配信には使わない（codeview publish の push だけで配信が走る）。
資格情報の渡し方は codeview/cloudflare.py。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.parse

from codeview import config
from codeview.cloudflare import api, github_repo, load_env


def step(label: str, result: dict) -> dict:
    if result.get("success"):
        print(f"ok    {label}")
    else:
        messages = "; ".join(m.get("message", "") for m in result.get("errors", []))
        print(f"NG    {label}: {messages}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="codeview cf-setup", description="Create the Pages project, domain and Access app.")
    parser.add_argument("host", help="custom domain, e.g. code.example.net")
    parser.add_argument("--project", help="Pages project name (default: the repo name)")
    args = parser.parse_args(argv)
    host = args.host
    zone_name = host.split(".", 1)[1]

    try:
        cfg = config.load()
    except config.ConfigError as e:
        sys.exit(f"error: {e}")
    branch = cfg.publish_branch
    owner, repo = github_repo(cfg.publish_remote, cfg.source.parent)
    project_name = args.project or repo

    token, account = load_env()
    acc = f"/accounts/{account}"

    verify = api(token, "GET", "/user/tokens/verify")
    if not verify.get("success"):
        sys.exit("error: invalid API token")
    print("ok    token")

    zones = api(token, "GET", "/zones?" + urllib.parse.urlencode({"name": zone_name}))
    results = zones.get("result") or []
    if not results:
        sys.exit(f"error: zone not found: {zone_name}")
    zone_id = results[0]["id"]

    step(
        "pages project",
        api(
            token,
            "POST",
            f"{acc}/pages/projects",
            {
                "name": project_name,
                "production_branch": branch,
                "source": {
                    "type": "github",
                    "config": {
                        "owner": owner,
                        "repo_name": repo,
                        "production_branch": branch,
                        "deployments_enabled": True,
                        # main には public/ が無く、プレビュービルドが必ず失敗する
                        "preview_deployment_setting": "none",
                    },
                },
                "build_config": {"destination_dir": "public"},
            },
        ),
    )

    # 既存プロジェクトにも効かせる（作成時の指定は再実行では通らない）
    step(
        "disable preview",
        api(
            token,
            "PATCH",
            f"{acc}/pages/projects/{project_name}",
            {
                "source": {
                    "type": "github",
                    "config": {
                        "owner": owner,
                        "repo_name": repo,
                        "production_branch": branch,
                        "deployments_enabled": True,
                        "preview_deployment_setting": "none",
                    },
                }
            },
        ),
    )

    step(
        "custom domain",
        api(token, "POST", f"{acc}/pages/projects/{project_name}/domains", {"name": host}),
    )

    # プロジェクト名が空いていないと Cloudflare はサフィックスを足す（`<project>-xxx.pages.dev` のように）。
    # <project>.pages.dev を決め打ちすると他人のプロジェクトを指す CNAME ができる
    project = api(token, "GET", f"{acc}/pages/projects/{project_name}").get("result") or {}
    subdomain = project.get("subdomain")
    if not subdomain:
        sys.exit("error: cannot read the project's subdomain")
    print(f"ok    subdomain {subdomain}")

    # proxied: false だと Access を素通りする
    existing = (
        api(
            token,
            "GET",
            f"/zones/{zone_id}/dns_records?"
            + urllib.parse.urlencode({"name": host, "type": "CNAME"}),
        ).get("result")
        or []
    )
    record = {"type": "CNAME", "name": host, "content": subdomain, "proxied": True}
    if existing:
        step(
            "dns",
            api(
                token,
                "PUT",
                f"/zones/{zone_id}/dns_records/{existing[0]['id']}",
                record,
            ),
        )
    else:
        step("dns", api(token, "POST", f"/zones/{zone_id}/dns_records", record))

    apps = api(token, "GET", f"{acc}/access/apps").get("result") or []
    app_id = next((a["id"] for a in apps if a.get("domain") == host), None)
    if app_id:
        print("ok    access app (exists)")
    else:
        app = api(
            token,
            "POST",
            f"{acc}/access/apps",
            {
                "name": project_name,
                "domain": host,
                "type": "self_hosted",
                "session_duration": "24h",
                # 空配列は「設定済みの IdP をすべて許可」。IdP の id を調べずに済む
                "allowed_idps": [],
                "auto_redirect_to_identity": False,
            },
        )
        step("access app", app)
        app_id = (app.get("result") or {}).get("id")

    if app_id:
        policies = (
            api(token, "GET", f"{acc}/access/apps/{app_id}/policies").get("result")
            or []
        )
        if policies:
            print(f"ok    policy ({len(policies)} existing)")
        else:
            email = subprocess.run(
                ["git", "config", "user.email"], capture_output=True, text=True
            ).stdout.strip()
            step(
                f"policy ({email})",
                api(
                    token,
                    "POST",
                    f"{acc}/access/apps/{app_id}/policies",
                    {
                        "name": "owner only",
                        "decision": "allow",
                        "include": [{"email": {"email": email}}],
                    },
                ),
            )

    print(
        f"\nCheck in a private window:\n"
        f"  https://{host}  -> asks you to log in\n"
        f"  https://{subdomain}  -> 404\n"
        f"  after login, the site is readable\n"
        f"Do not share the URL until all three hold."
    )
    return 0

