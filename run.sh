#!/bin/bash
# Paleidžia naujausią Emuautotest MCP serverio versiją
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LATEST_VERSION="v1.0.0"

exec "$DIR/apps/$LATEST_VERSION/.venv/bin/python3" "$DIR/apps/$LATEST_VERSION/run_server.py" "$@"
