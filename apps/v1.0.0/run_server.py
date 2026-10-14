#!/usr/bin/env python3
"""Entry point for Emuautotest MCP Server."""

import argparse
import sys
from pathlib import Path

# Ensure package is on sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from emuautotest.server import server

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Emuautotest MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport type (default: stdio)",
    )
    args = parser.parse_args()

    server.run(transport=args.transport)
