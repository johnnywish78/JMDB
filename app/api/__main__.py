"""CLI entry: python -m app.api [--port N] [--host 127.0.0.1] [--token-file P].

Used by Electron in managed mode: Electron spawns this process, waits for
/api/health, then reads the generated token from the token file.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jmdb-api")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8737)
    parser.add_argument("--token-file", default="", help="write the launch token here")
    parser.add_argument("--token", default="", help="explicit token (tests/dev)")
    args = parser.parse_args(argv)

    token = args.token or secrets.token_urlsafe(32)
    if args.token_file:
        path = Path(args.token_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"token": token, "port": args.port}), "utf-8")
        os.chmod(path, 0o600)

    from app.api.server import run_server

    print(f"JMDB API listening on http://{args.host}:{args.port}", flush=True)
    run_server(host=args.host, port=args.port, token=token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
