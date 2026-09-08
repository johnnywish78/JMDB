"""Wrapper to start the JMDB FastAPI backend."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.server import app, _auth_token  # noqa: E402
import uvicorn  # noqa: E402


def main() -> int:
    print(f"JMDB API token: {_auth_token[:8]}…", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=18932, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
