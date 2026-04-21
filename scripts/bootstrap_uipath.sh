#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

find_python() {
  local candidates=()
  if [[ -n "${UIPATH_PYTHON:-}" ]]; then
    candidates+=("${UIPATH_PYTHON}")
  fi

  local on_path
  on_path="$(command -v python3.12 || true)"
  [[ -n "$on_path" ]] && candidates+=("$on_path")
  on_path="$(command -v python3.11 || true)"
  [[ -n "$on_path" ]] && candidates+=("$on_path")
  on_path="$(command -v python3 || true)"
  [[ -n "$on_path" ]] && candidates+=("$on_path")

  candidates+=(
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12"
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    [[ -x "$candidate" ]] || continue
    if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

PYTHON_BIN="$(find_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "No Python 3.11+ interpreter was found."
  echo "Install Python 3.11 or 3.12, or set UIPATH_PYTHON to a compatible interpreter."
  exit 1
fi

echo "Using Python interpreter: $PYTHON_BIN"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Creating repo-local virtual environment at .venv"
  "$PYTHON_BIN" -m venv .venv
fi

echo "Upgrading pip and installing uv into .venv"
./.venv/bin/python -m pip install --upgrade pip uv

echo "Syncing project dependencies with uv"
./.venv/bin/uv sync

echo "Installed UiPath CLI version:"
./.venv/bin/uipath --version
