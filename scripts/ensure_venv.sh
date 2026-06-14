#!/usr/bin/env bash
# Ensure LazyOps .venv exists and dependencies are installed.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON=${PYTHON:-python3}
VENV_DIR="$ROOT_DIR/.venv"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python 3 is required. Install it or set PYTHON=python3" >&2
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment at $VENV_DIR ..."
  "$PYTHON" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if ! python -c "import typer, yaml" >/dev/null 2>&1; then
  echo "Installing LazyOps into .venv ..."
  python -m pip install --upgrade pip setuptools wheel
  python -m pip install -e "$ROOT_DIR"
fi

export LAZYOPS_ROOT="$ROOT_DIR"
export LAZYOPS_VENV="$VENV_DIR"
