#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

: "${UIPATH_ENVIRONMENT:=cloud}"
: "${UIPATH_TENANT:=HLS_SE_Team}"
: "${UIPATH_URL:=https://cloud.uipath.com/uipathlabs/${UIPATH_TENANT}}"
: "${UIPATH_FOLDER_PATH:=Shared}"
if [[ -z "${UIPATH_BASE_URL:-}" ]]; then
  UIPATH_BASE_URL="$UIPATH_URL"
fi

if [[ ! -x ".venv/bin/uipath" ]]; then
  echo "UiPath CLI is not installed in .venv yet."
  echo "Run ./scripts/bootstrap_uipath.sh first."
  exit 1
fi

auth_cmd=(./.venv/bin/uipath auth)
auth_mode="${UIPATH_AUTH_MODE:-desktop}"

if [[ "${1:-}" == "--unattended" ]]; then
  auth_mode="unattended"
  shift
elif [[ "${1:-}" == "--desktop" ]]; then
  auth_mode="desktop"
  shift
fi

if [[ -n "${UIPATH_URL:-}" ]]; then
  export UIPATH_URL
fi

if [[ "$auth_mode" == "unattended" ]]; then
  if [[ -z "${UIPATH_CLIENT_ID:-}" || -z "${UIPATH_CLIENT_SECRET:-}" || -z "${UIPATH_BASE_URL:-}" ]]; then
    echo "UIPATH_CLIENT_ID, UIPATH_CLIENT_SECRET, and UIPATH_BASE_URL are required for unattended auth."
    echo "Either populate .env and rerun with --unattended, or rerun without flags for desktop auth."
    exit 1
  fi

  echo "Using unattended client-credentials auth because unattended mode was explicitly requested."
  auth_cmd+=(
    --client-id "$UIPATH_CLIENT_ID"
    --client-secret "$UIPATH_CLIENT_SECRET"
    --base-url "$UIPATH_BASE_URL"
  )
  if [[ -n "${UIPATH_TENANT:-}" ]]; then
    auth_cmd+=(--tenant "$UIPATH_TENANT")
  fi
  if [[ -n "${UIPATH_SCOPE:-}" ]]; then
    auth_cmd+=(--scope "$UIPATH_SCOPE")
  fi
else
  echo "Using interactive desktop/browser auth by default."
  case "${UIPATH_ENVIRONMENT:-cloud}" in
    cloud)
      auth_cmd+=(--cloud)
      ;;
    staging)
      auth_cmd+=(--staging)
      ;;
    alpha)
      auth_cmd+=(--alpha)
      ;;
    *)
      echo "Unsupported UIPATH_ENVIRONMENT='${UIPATH_ENVIRONMENT}'. Use cloud, staging, or alpha."
      exit 1
      ;;
  esac
  if [[ -n "${UIPATH_TENANT:-}" ]]; then
    auth_cmd+=(--tenant "$UIPATH_TENANT")
  fi
fi

"${auth_cmd[@]}" "$@"
