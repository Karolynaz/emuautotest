#!/bin/bash
# Paleidžia Emuautotest v1.1.0 grafinį vartotojo interfeisą (UI)
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/apps/v1.1.0/.venv/bin/python3" "$DIR/apps/v1.1.0/run_ui.py" "$@"
