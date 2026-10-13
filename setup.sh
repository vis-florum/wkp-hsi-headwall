#!/usr/bin/env bash
# Run from any directory; initialize the uv project beside this script.
set -e
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# uv creates .venv, installs this package and its dependencies, and writes uv.lock.
uv sync --python 3.12

echo "Setup complete. From this repository, run: uv run hsi-helios-eiff"
