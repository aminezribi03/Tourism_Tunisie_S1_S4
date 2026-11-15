#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
python3 -c 'import sys; assert sys.version_info[:2] == (3,12), "Utilisez Python 3.12"'
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m tourism.etl
.venv/bin/python scripts/configure_powerbi.py
echo "Installation terminee. Lancez bash lancer_mac_linux.sh"
