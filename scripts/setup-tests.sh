#!/usr/bin/env bash
set -e

# Install Python packages required for running tests
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# Verify important packages are installed
python - <<'PY'
import flake8, pytest, httpx
print('flake8', flake8.__version__)
print('pytest', pytest.__version__)
print('httpx', httpx.__version__)
PY

