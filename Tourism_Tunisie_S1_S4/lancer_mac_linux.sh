#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
