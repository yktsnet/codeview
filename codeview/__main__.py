"""codeview のコマンド。作業ディレクトリの codeview.toml を読み、そこへ生成物を書く。"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import sys
from pathlib import Path

from codeview import build, cf_setup, cf_status, publish

COMMANDS = {
    "build": "generate public/ and functions/",
    "serve": "serve public/ locally to check the pages (Functions do not run)",
    "publish": "build and force-push the generated files to the deploy branch",
    "cf-setup": "create the Cloudflare Pages project, domain and Access app (once)",
    "cf-status": "show the Pages project and recent deployments",
}


def serve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="codeview serve", description=COMMANDS["serve"])
    parser.add_argument("--port", type=int, default=int(os.environ.get("CODEVIEW_PORT", 8787)))
    args = parser.parse_args(argv)
    public = Path(os.environ.get("CODEVIEW_OUT") or Path.cwd()) / "public"
    if not public.is_dir():
        print(f"error: {public} not found; run `codeview build` first", file=sys.stderr)
        return 1
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(public))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"http://localhost:{args.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in COMMANDS:
        width = max(map(len, COMMANDS))
        lines = [f"  {name:<{width}}  {text}" for name, text in COMMANDS.items()]
        print("usage: codeview <command> [options]\n\ncommands:\n" + "\n".join(lines))
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    command, rest = argv[0], argv[1:]
    if command == "serve":
        return serve(rest)
    run = {
        "build": build.main,
        "publish": publish.main,
        "cf-setup": cf_setup.main,
        "cf-status": cf_status.main,
    }[command]
    return run(rest) or 0

if __name__ == "__main__":
    raise SystemExit(main())
