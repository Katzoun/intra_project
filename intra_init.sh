#!/bin/bash

# Nastaveni workspace

mkdir .venv
echo "Workspace directory: $WORKSPACE_DIR"

echo "=== Creating venv ==="
python3 -m venv .venv --system-site-packages
touch .venv/COLCON_IGNORE
source .venv/bin/activate
export PYTHONNOUSERSITE=1
pip install -r requirements.txt
deactivate
echo "=== VENV COMPLETED ==="