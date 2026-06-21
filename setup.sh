#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/ensure_venv.sh
source "$ROOT_DIR/scripts/ensure_venv.sh"

chmod +x "$ROOT_DIR/lazyops" "$ROOT_DIR/scripts/with-venv" "$ROOT_DIR/scripts/ensure_venv.sh"

LAZYOPS_BIN="$VENV_DIR/bin/lazyops"
if [[ ! -x "$LAZYOPS_BIN" ]]; then
  echo "Installation failed: $LAZYOPS_BIN not found" >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "Warning: git is not installed. lazyops requires git to fetch workflows from lazyops-plugins." >&2
fi

shell_rc_files() {
  local files=()
  case "${SHELL:-}" in
    */zsh) files+=("$HOME/.zshrc") ;;
    */bash) files+=("$HOME/.bashrc") ;;
  esac
  [[ -f "$HOME/.zshrc" ]] && [[ " ${files[*]} " != *" $HOME/.zshrc "* ]] && files+=("$HOME/.zshrc")
  [[ -f "$HOME/.bashrc" ]] && [[ " ${files[*]} " != *" $HOME/.bashrc "* ]] && files+=("$HOME/.bashrc")
  if [[ ${#files[@]} -eq 0 ]]; then
    files+=("$HOME/.profile")
  fi
  printf '%s\n' "${files[@]}"
}

setup_shell_alias() {
  local marker alias_line export_line tmp rc_file
  marker="# LazyOps CLI"
  alias_line="alias lazyops='$ROOT_DIR/lazyops'"
  export_line="export LAZYOPS_ROOT='$ROOT_DIR'"

  while IFS= read -r rc_file; do
    [[ -z "$rc_file" ]] && continue
    tmp="$(mktemp)"
    touch "$rc_file"
    grep -v "^alias lazyops=" "$rc_file" \
      | grep -v "^export LAZYOPS_ROOT=" \
      | grep -Fv "$marker" > "$tmp" || true

    {
      cat "$tmp"
      echo ""
      echo "$marker"
      echo "$export_line"
      echo "$alias_line"
    } > "${rc_file}.lazyops.tmp"
    mv "${rc_file}.lazyops.tmp" "$rc_file"
    rm -f "$tmp"

    echo "Configured global lazyops alias in $rc_file"
  done < <(shell_rc_files)

  echo "  $export_line"
  echo "  $alias_line"
  echo "Reload your shell: source ~/.zshrc  (or source ~/.bashrc)"
}

setup_shell_alias

echo ""
echo "Installation complete."
echo "  From anywhere: lazyops --help   (after: source ~/.zshrc)"
echo "  From repo:     $ROOT_DIR/lazyops --help"
echo ""
echo "Next steps:"
echo "  lazyops source init https://github.com/MridulTi/lazyops-plugins.git --ref v1.0.0"
echo "  lazyops pack add aws"
echo "  lazyops run"
echo ""
echo "  PyPI install: pipx install lazyops-cli"
echo ""
echo "  Activate venv: source $VENV_DIR/bin/activate"
