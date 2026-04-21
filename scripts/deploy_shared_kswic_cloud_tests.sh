#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -x ".venv/bin/uipath" ]]; then
  echo "UiPath CLI is not installed in .venv yet."
  echo "Run ./scripts/bootstrap_uipath.sh first."
  exit 1
fi

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

: "${UIPATH_TENANT:=HLS_SE_Team}"
: "${UIPATH_URL:=https://cloud.uipath.com/uipathlabs/${UIPATH_TENANT}}"
: "${UIPATH_FOLDER_PATH:=Shared}"
if [[ -z "${UIPATH_BASE_URL:-}" ]]; then
  UIPATH_BASE_URL="$UIPATH_URL"
fi

FOLDER_PATH="${UIPATH_FOLDER_PATH:-Shared}"

deploy_project() {
  local project_path="$1"
  local label="$2"
  local output

  set +e
  output="$("$ROOT/.venv/bin/uipath" deploy --tenant "$project_path" 2>&1)"
  local status=$?
  set -e

  printf '%s\n' "$output"

  if [[ $status -eq 0 ]]; then
    return 0
  fi
  if [[ "$output" == *"Package already exists"* ]]; then
    echo "Package for ${label} already exists in the tenant feed. Continuing."
    return 0
  fi
  return $status
}

echo "Publishing shared-kswic-correspondence-smoke-agent to the tenant feed..."
deploy_project "cloud-api-smoke/shared-kswic-correspondence-smoke-agent" \
  "shared-kswic-correspondence-smoke-agent"

echo "Publishing shared-kswic-correspondence-maestro-test to the tenant feed..."
deploy_project "maestro-process-tests/shared-kswic-correspondence-maestro-test" \
  "shared-kswic-correspondence-maestro-test"

echo "Reconciling explicit Shared-folder releases in '${FOLDER_PATH}'..."
"$ROOT/.venv/bin/python" "$ROOT/scripts/setup_shared_kswic_cloud_tests.py" --folder-path "$FOLDER_PATH" "$@"
