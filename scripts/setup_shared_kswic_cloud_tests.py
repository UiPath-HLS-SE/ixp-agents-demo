#!/usr/bin/env python3
"""Provision Shared-folder releases for the KSWIC cloud smoke packages."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx

from uipath_cloud_auth import (
    AuthState,
    load_runtime_env,
    request_with_auth_refresh,
    resolve_folder_id,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FOLDER_PATH = os.environ.get("UIPATH_FOLDER_PATH", "Shared")


@dataclass(frozen=True)
class PublishableAsset:
    package_id: str
    release_name: str
    description: str
    project_dir: Path
    entry_point_path: str


ASSETS: tuple[PublishableAsset, ...] = (
    PublishableAsset(
        package_id="shared-kswic-correspondence-smoke-agent",
        release_name="Shared KSWIC Correspondence Smoke Agent",
        description=(
            "Shared-folder smoke agent for KSWIC payer-correspondence routing."
        ),
        project_dir=ROOT / "cloud-api-smoke" / "shared-kswic-correspondence-smoke-agent",
        entry_point_path="main",
    ),
    PublishableAsset(
        package_id="shared-kswic-correspondence-maestro-test",
        release_name="Shared KSWIC Correspondence Maestro Test",
        description=(
            "Shared-folder Maestro wrapper that starts the KSWIC smoke agent."
        ),
        project_dir=ROOT
        / "maestro-process-tests"
        / "shared-kswic-correspondence-maestro-test",
        entry_point_path="/content/Process.bpmn#Event_start",
    ),
)


class OrchestratorError(RuntimeError):
    pass


class OrchestratorClient:
    def __init__(self, base_url: str, auth_state: AuthState) -> None:
        self.base_url = base_url.rstrip("/") + "/orchestrator_"
        self.auth_state = auth_state
        self.http = httpx.Client(timeout=60.0)

    def close(self) -> None:
        self.http.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        folder_id: int | None = None,
        expected: tuple[int, ...] = (200,),
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        response = request_with_auth_refresh(
            self.http,
            method,
            self.base_url + path,
            self.auth_state,
            folder_id=folder_id,
            **kwargs,
        )
        if response.status_code not in expected:
            detail = response.text
            if len(detail) > 2000:
                detail = detail[:2000] + "..."
            raise OrchestratorError(
                f"{method.upper()} {path} failed with HTTP {response.status_code}: {detail}"
            )
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def get(
        self,
        path: str,
        *,
        folder_id: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self.request("GET", path, folder_id=folder_id, params=params)
        return {} if payload is None else payload

    def post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        folder_id: int | None = None,
        expected: tuple[int, ...] = (200, 201),
    ) -> dict[str, Any] | None:
        return self.request(
            "POST",
            path,
            folder_id=folder_id,
            expected=expected,
            json=body,
        )

    def patch(
        self,
        path: str,
        body: dict[str, Any],
        *,
        folder_id: int | None = None,
        expected: tuple[int, ...] = (200, 204),
    ) -> dict[str, Any] | None:
        return self.request(
            "PATCH",
            path,
            folder_id=folder_id,
            expected=expected,
            json=body,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or update Shared-folder releases for the KSWIC smoke assets."
    )
    parser.add_argument(
        "--folder-path",
        default=os.environ.get("UIPATH_FOLDER_PATH", DEFAULT_FOLDER_PATH),
        help="Target folder path. Defaults to UIPATH_FOLDER_PATH or Shared.",
    )
    parser.add_argument(
        "--prefer-client-credentials",
        action="store_true",
        help="Prefer unattended client credentials before desktop auth cache refresh.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the provisioning summary as JSON only.",
    )
    return parser.parse_args()


def odata_single(items: list[dict[str, Any]], name: str, *, field: str = "Name") -> dict[str, Any] | None:
    for item in items:
        if item.get(field) == name:
            return item
    return None


def semver_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def latest_package_version(
    client: OrchestratorClient,
    asset: PublishableAsset,
) -> str:
    data = client.get(
        "/odata/Processes",
        params={"$filter": f"Id eq '{asset.package_id}'", "$top": 100},
    )
    versions = sorted(
        {
            str(item.get("Version") or "")
            for item in data.get("value", [])
            if item.get("Id") == asset.package_id and item.get("Version")
        },
        key=semver_key,
    )
    if not versions:
        raise OrchestratorError(
            f"Published package '{asset.package_id}' was not found. Deploy {asset.project_dir} first."
        )
    return versions[-1]


def get_or_create_release(
    client: OrchestratorClient,
    *,
    folder_id: int,
    asset: PublishableAsset,
    version: str,
) -> dict[str, Any]:
    data = client.get(
        "/odata/Releases",
        folder_id=folder_id,
        params={"$filter": f"Name eq '{asset.release_name}'", "$top": 10},
    )
    existing = odata_single(data.get("value", []), asset.release_name)
    if existing is None:
        created = client.post(
            "/odata/Releases",
            {
                "Name": asset.release_name,
                "ProcessKey": asset.package_id,
                "ProcessVersion": version,
                "EntryPointPath": asset.entry_point_path,
                "Description": asset.description,
            },
            folder_id=folder_id,
        )
        if created is None:
            raise OrchestratorError(
                f"Release creation returned no payload for {asset.release_name}."
            )
        created["_codex_status"] = "created"
        return created

    current_version = str(existing.get("ProcessVersion") or "")
    current_entry_point_path = str(existing.get("EntryPointPath") or "")
    if current_version != version or current_entry_point_path != asset.entry_point_path:
        client.patch(
            f"/odata/Releases({existing['Id']})",
            {
                "ProcessVersion": version,
                "EntryPointPath": asset.entry_point_path,
            },
            folder_id=folder_id,
        )
        refreshed = client.get(
            "/odata/Releases",
            folder_id=folder_id,
            params={"$filter": f"Name eq '{asset.release_name}'", "$top": 10},
        )
        updated = odata_single(refreshed.get("value", []), asset.release_name)
        if updated is None:
            raise OrchestratorError(
                f"Release '{asset.release_name}' disappeared after patch."
            )
        updated["_codex_status"] = "updated"
        updated["_codex_previous_version"] = current_version
        return updated

    existing["_codex_status"] = "unchanged"
    return existing


def main() -> int:
    args = parse_args()
    auth_state = load_runtime_env(
        prefer_cli_auth_cache=not args.prefer_client_credentials,
    )
    base_url = os.environ["UIPATH_URL"].rstrip("/")

    client = OrchestratorClient(base_url, auth_state)
    try:
        folder_id = resolve_folder_id(client.http, base_url, args.folder_path, auth_state)
        actions: list[dict[str, Any]] = []
        for asset in ASSETS:
            version = latest_package_version(client, asset)
            release = get_or_create_release(
                client,
                folder_id=folder_id,
                asset=asset,
                version=version,
            )
            actions.append(
                {
                    "package_id": asset.package_id,
                    "release_name": asset.release_name,
                    "folder_path": args.folder_path,
                    "project_dir": str(asset.project_dir),
                    "entry_point_path": asset.entry_point_path,
                    "status": release.get("_codex_status"),
                    "process_version": release.get("ProcessVersion", version),
                    "previous_version": release.get("_codex_previous_version"),
                    "release_id": release.get("Id"),
                    "release_key": release.get("Key"),
                }
            )
    finally:
        client.close()

    if args.json:
        print(json.dumps({"folder_path": args.folder_path, "releases": actions}, indent=2))
    else:
        print(f"Shared-folder release state for {args.folder_path}:")
        for action in actions:
            line = (
                f"- {action['release_name']} "
                f"[{action['status']}] "
                f"version={action['process_version']} "
                f"package={action['package_id']}"
            )
            if action["previous_version"]:
                line += f" previous={action['previous_version']}"
            print(line)
        print(json.dumps({"folder_path": args.folder_path, "releases": actions}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
