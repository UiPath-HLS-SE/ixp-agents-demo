#!/usr/bin/env python3
"""Shared UiPath cloud auth/runtime helpers for repo-local smoke scripts."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from uipath._cli._auth._oidc_utils import OidcUtils
from uipath._cli._auth._url_utils import resolve_domain
from uipath._utils._auth import parse_access_token
from uipath.platform.identity import IdentityService


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUTH_REFRESH_MIN_TTL_SECONDS = 300


@dataclass
class AuthState:
    prefer_cli_auth_cache: bool
    auth_cache: Path | None
    domain: str
    client_credentials_available: bool


def auth_cache_candidates(repo_root: Path | None = None) -> list[Path]:
    root = repo_root or ROOT
    return [
        root / ".uipath" / ".auth.json",
        Path.home() / ".uipath" / ".auth.json",
    ]


def resolve_auth_cache(repo_root: Path | None = None) -> Path | None:
    existing = [path for path in auth_cache_candidates(repo_root) if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def load_runtime_env(
    prefer_cli_auth_cache: bool = True,
    *,
    repo_root: Path | None = None,
    override: bool = True,
) -> AuthState:
    root = repo_root or ROOT
    load_dotenv(root / ".env", override=override)

    os.environ.setdefault("UIPATH_TENANT", "HLS_SE_Team")
    os.environ.setdefault(
        "UIPATH_URL",
        f"https://cloud.uipath.com/uipathlabs/{os.environ['UIPATH_TENANT']}",
    )
    os.environ.setdefault("UIPATH_FOLDER_PATH", "Shared")
    os.environ.setdefault("UIPATH_BASE_URL", os.environ["UIPATH_URL"])

    auth_cache = resolve_auth_cache(root)
    if prefer_cli_auth_cache and auth_cache is not None:
        auth = json.loads(auth_cache.read_text())
        token = auth.get("access_token")
        if token:
            os.environ["UIPATH_ACCESS_TOKEN"] = token

    base_url = os.environ.get("UIPATH_BASE_URL") or os.environ.get("UIPATH_URL")
    domain = resolve_domain(os.environ.get("UIPATH_URL"), None)
    if not domain and base_url:
        domain = resolve_domain(base_url, None)
    if not domain:
        raise SystemExit(
            "UIPATH_URL or UIPATH_BASE_URL must be set. Run ./scripts/uipath_auth.sh "
            "for desktop auth, or configure unattended credentials in .env."
        )

    client_credentials_available = all(
        os.environ.get(name)
        for name in ("UIPATH_CLIENT_ID", "UIPATH_CLIENT_SECRET", "UIPATH_BASE_URL")
    )

    if not os.environ.get("UIPATH_ACCESS_TOKEN") and not client_credentials_available:
        raise SystemExit(
            "No UiPath auth was available. First try ./scripts/uipath_auth.sh for desktop "
            "login. For unattended operations, set UIPATH_CLIENT_ID, "
            "UIPATH_CLIENT_SECRET, and UIPATH_BASE_URL in .env."
        )

    return AuthState(
        prefer_cli_auth_cache=prefer_cli_auth_cache,
        auth_cache=auth_cache,
        domain=domain,
        client_credentials_available=client_credentials_available,
    )


def build_base_headers(folder_id: int | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {os.environ['UIPATH_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
    }
    if folder_id is not None:
        headers["X-UIPATH-OrganizationUnitId"] = str(folder_id)
    return headers


def token_expiry_epoch(access_token: str) -> float | None:
    try:
        claims = parse_access_token(access_token)
    except Exception:
        return None
    exp = claims.get("exp")
    return float(exp) if exp is not None else None


def _refresh_access_token_from_cli_auth_cache(domain: str, refresh_token: str):
    auth_config = asyncio.run(OidcUtils.get_auth_config(domain))
    client_id = auth_config.get("client_id")
    return IdentityService(domain).refresh_access_token(refresh_token, client_id)


def refresh_access_token_from_auth_cache(
    auth_state: AuthState,
    *,
    reason: str,
    verbose: bool = True,
) -> bool:
    auth_cache = auth_state.auth_cache
    if auth_cache is None or not auth_cache.exists():
        return False

    auth = json.loads(auth_cache.read_text())
    refresh_token = auth.get("refresh_token")
    if not refresh_token:
        return False

    try:
        token_data = _refresh_access_token_from_cli_auth_cache(
            auth_state.domain,
            refresh_token,
        )
    except Exception:
        if verbose:
            print(f"[auth] failed to refresh CLI auth cache ({reason})")
        return False

    auth_cache.write_text(json.dumps(token_data.model_dump(exclude_none=True)))
    os.environ["UIPATH_ACCESS_TOKEN"] = token_data.access_token
    if verbose:
        print(f"[auth] refreshed access token from {auth_cache} ({reason})")
    return True


def refresh_access_token_from_client_credentials(
    auth_state: AuthState,
    *,
    reason: str,
    verbose: bool = True,
) -> bool:
    if not auth_state.client_credentials_available:
        return False

    token_data = {
        "grant_type": "client_credentials",
        "client_id": os.environ["UIPATH_CLIENT_ID"],
        "client_secret": os.environ["UIPATH_CLIENT_SECRET"],
    }
    scope = os.environ.get("UIPATH_SCOPE")
    if scope:
        token_data["scope"] = scope

    try:
        response = httpx.post(
            f"{os.environ['UIPATH_BASE_URL'].rstrip('/')}/identity_/connect/token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
    except httpx.HTTPError:
        if verbose:
            print(f"[auth] failed to mint access token from client credentials ({reason})")
        return False
    if response.status_code >= 400:
        if verbose:
            print(
                "[auth] client credentials token request failed "
                f"({reason}; HTTP {response.status_code})"
            )
        return False

    try:
        token = response.json().get("access_token")
    except ValueError:
        token = None
    if not token:
        if verbose:
            print(f"[auth] token response did not include access_token ({reason})")
        return False

    os.environ["UIPATH_ACCESS_TOKEN"] = token
    if verbose:
        print(f"[auth] minted access token from client credentials ({reason})")
    return True


def refresh_access_token(
    auth_state: AuthState,
    *,
    reason: str,
    verbose: bool = True,
) -> bool:
    refreshers = (
        (
            refresh_access_token_from_auth_cache,
            refresh_access_token_from_client_credentials,
        )
        if auth_state.prefer_cli_auth_cache
        else (
            refresh_access_token_from_client_credentials,
            refresh_access_token_from_auth_cache,
        )
    )
    for refresher in refreshers:
        if refresher(auth_state, reason=reason, verbose=verbose):
            return True
    return False


def ensure_access_token_fresh(
    auth_state: AuthState,
    *,
    min_ttl_seconds: int = DEFAULT_AUTH_REFRESH_MIN_TTL_SECONDS,
    verbose: bool = True,
) -> None:
    access_token = os.environ.get("UIPATH_ACCESS_TOKEN")
    if not access_token:
        if refresh_access_token(auth_state, reason="no access token was set", verbose=verbose):
            access_token = os.environ.get("UIPATH_ACCESS_TOKEN")
        else:
            raise SystemExit(
                "UIPATH_ACCESS_TOKEN is not set. Run ./scripts/uipath_auth.sh or configure unattended credentials."
            )

    exp = token_expiry_epoch(access_token)
    if exp is None:
        return

    remaining = exp - time.time()
    if remaining > min_ttl_seconds:
        return

    reason = f"token expiring in {max(int(remaining), 0)}s"
    if refresh_access_token(auth_state, reason=reason, verbose=verbose):
        return

    if remaining <= 0:
        raise SystemExit(
            "UiPath access token expired and no refresh path was available. "
            "Run ./scripts/uipath_auth.sh or configure unattended credentials in .env."
        )


def request_with_auth_refresh(
    client: httpx.Client,
    method: str,
    url: str,
    auth_state: AuthState,
    *,
    folder_id: int | None = None,
    refresh_verbose: bool = True,
    **kwargs: Any,
) -> httpx.Response:
    ensure_access_token_fresh(auth_state, verbose=refresh_verbose)

    response = client.request(
        method,
        url,
        headers=build_base_headers(folder_id),
        **kwargs,
    )
    if response.status_code != 401:
        return response

    if not refresh_access_token(
        auth_state,
        reason=f"received 401 from {method.upper()} {url}",
        verbose=refresh_verbose,
    ):
        return response

    return client.request(
        method,
        url,
        headers=build_base_headers(folder_id),
        **kwargs,
    )


def resolve_folder_id(
    client: httpx.Client,
    base_url: str,
    folder_path: str,
    auth_state: AuthState,
) -> int:
    response = request_with_auth_refresh(
        client,
        "GET",
        f"{base_url}/orchestrator_/odata/Folders",
        auth_state,
        params={"$top": 200},
    )
    response.raise_for_status()
    items = response.json().get("value", [])
    for item in items:
        display = str(item.get("DisplayName") or "")
        qualified = str(item.get("FullyQualifiedName") or "")
        if folder_path in {display, qualified}:
            folder_id = item.get("Id")
            if isinstance(folder_id, int):
                return folder_id
    raise SystemExit(f"Folder '{folder_path}' was not found in {base_url}.")
