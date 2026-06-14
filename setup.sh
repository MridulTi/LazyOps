#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON=${PYTHON:-python3}

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python 3 is required. Install it or set PYTHON=python3"
  exit 1
fi

echo "Installing LazyOps package..."
"$PYTHON" -m pip install --upgrade pip setuptools wheel
"$PYTHON" -m pip install --user -e "$ROOT_DIR"

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
  SHELL_RC=""
  if [[ -n "${ZSH_VERSION-}" ]]; then
    SHELL_RC="$HOME/.zshrc"
  elif [[ -n "${BASH_VERSION-}" ]]; then
    SHELL_RC="$HOME/.bashrc"
  else
    SHELL_RC="$HOME/.profile"
  fi
  echo "Adding ~/.local/bin to PATH in $SHELL_RC"
  printf '\n# Added by LazyOps installer\nexport PATH="\$HOME/.local/bin:\$PATH"\n' >> "$SHELL_RC"
  echo "Please restart your shell or run: source $SHELL_RC"
fi

if ! command -v lazyops >/dev/null 2>&1; then
  echo "Creating shell alias for lazyops command..."
  SHELL_RC=""
  if [[ -n "${ZSH_VERSION-}" ]]; then
    SHELL_RC="$HOME/.zshrc"
  elif [[ -n "${BASH_VERSION-}" ]]; then
    SHELL_RC="$HOME/.bashrc"
  else
    SHELL_RC="$HOME/.profile"
  fi
  grep -qxF "alias lazyops='python3 -m lazyops_cli.cli'" "$SHELL_RC" 2>/dev/null || \
    printf '\n# Alias for LazyOps CLI\nalias lazyops=\'python3 -m lazyops_cli.cli\'\n' >> "$SHELL_RC"
  echo "Added alias to $SHELL_RC"
  echo "Use: source $SHELL_RC or open a new shell to activate the alias"
fi

echo "Installation complete. You can run: lazyops --help"
