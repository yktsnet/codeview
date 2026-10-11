"""Pages プロジェクトの状態とデプロイ履歴を見る。

    codeview cf-status [--project NAME]

デプロイが1件も無い場合、GitHub App が対象リポを見えていない可能性が高い
（配信ブランチへの push は起きているのに反応が無いなら、ほぼこれ）。
"""

from __future__ import annotations

import argparse
import sys

from codeview import config
from codeview.cloudflare import api as _api
from codeview.cloudflare import github_repo, load_env


def api(token: str, path: str) -> dict:
    return _api(token, "GET", path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="codeview cf-status", description="Show the Pages project and recent deployments.")
    parser.add_argument("--project", help="Pages project name (default: the repo name)")
    args = parser.parse_args(argv)
    try:
        cfg = config.load()
    except config.ConfigError as e:
        sys.exit(f"error: {e}")
    _, repo = github_repo(cfg.publish_remote, cfg.source.parent)
    project_name = args.project or repo

    token, account = load_env()
    acc = f"/accounts/{account}"

    project = api(token, f"{acc}/pages/projects/{project_name}").get("result") or {}
    source = project.get("source") or {}
    source_config = source.get("config") or {}
    print(f"project      {project.get('name')}")
    print(f"production   {project.get('production_branch')}")
    print(
        f"source       {source.get('type')} {source_config.get('owner')}/{source_config.get('repo_name')}"
    )
    print(f"deployments  enabled={source_config.get('deployments_enabled')}")
    # main には public/ が無く、preview が有効だと push のたびに必ず失敗が積まれる
    print(f"preview      {source_config.get('preview_deployment_setting')}")
    print(f"subdomain    {project.get('subdomain')}")

    # カスタムドメインは追加できても検証が通るまで配信されない。status を見ないと分からない
    domains = api(token, f"{acc}/pages/projects/{project_name}/domains").get("result") or []
    print(f"\ndomains      {len(domains)}")
    for d in domains:
        print(
            f"  {d.get('name')}  status={d.get('status')}"
            f"  cert={(d.get('validation_data') or {}).get('status')}"
        )

    deployments = (
        api(token, f"{acc}/pages/projects/{project_name}/deployments").get("result") or []
    )
    print(f"\ndeployments  {len(deployments)}")
    for d in deployments[:5]:
        stage = d.get("latest_stage") or {}
        trigger = (d.get("deployment_trigger") or {}).get("metadata") or {}
        env = d.get("environment")
        print(
            f"  {d.get('created_on', '')[:19]}  {stage.get('name')}/{stage.get('status')}"
            f"  env={env}  branch={trigger.get('branch')}"
            f"  {(trigger.get('commit_hash') or '')[:8]}"
        )
        if stage.get("status") == "failure":
            print(f"      {d.get('url')}")

    if not deployments:
        print(
            f"\nNo deployments. The Cloudflare GitHub App probably cannot see {repo}.\n"
            "Open Cloudflare Pages at https://github.com/settings/installations and\n"
            f"add {repo} to the selected repositories (browser only).\n"
            "Then run `codeview publish` to push again."
        )
    return 0

