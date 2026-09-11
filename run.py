#!/usr/bin/env python3

import argparse

import uvicorn

from app.config import DEFAULT_PORT, HOST
from app.database.migrations import migrate


def main():
    parser = argparse.ArgumentParser(description="JMDB")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
    )
    args = parser.parse_args()

    migrate()

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
