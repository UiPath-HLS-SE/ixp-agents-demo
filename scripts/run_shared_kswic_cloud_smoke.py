#!/usr/bin/env python3
"""Invoke the Shared-folder KSWIC smoke agent or Maestro test process."""

from __future__ import annotations

import argparse
import httpx
import json
import os
from pathlib import Path
import time
from typing import Any

from uipath_cloud_auth import (
    ensure_access_token_fresh,
    load_runtime_env,
    request_with_auth_refresh,
    resolve_folder_id,
)
from kswic_live_ixp_adapter import (
    DEFAULT_RESULTS_PATH as DEFAULT_LIVE_IXP_RESULTS_PATH,
    live_ixp_result_to_smoke_payload,
    load_live_ixp_results,
    select_live_ixp_result,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FOLDER_PATH = os.environ.get("UIPATH_FOLDER_PATH", "Shared")
SMOKE_RELEASE_NAME = "Shared KSWIC Correspondence Smoke Agent"
MAESTRO_RELEASE_NAME = "Shared KSWIC Correspondence Maestro Test"
TARGET_ENTRYPOINTS = {
    "smoke": "main",
    "maestro": "/content/Process.bpmn#Event_start",
}
TERMINAL_STATES = {"successful", "faulted", "stopped", "canceled"}
PROFILE_INPUTS: dict[str, dict[str, Any]] = {
    "denial": {
        "packet_id": "KSWIC-SCN-004",
        "scenario_id": "SCN-004",
        "document_type": "Claim Denial Letter",
        "decision_status": "denied",
        "fax_category": "claim_denial",
        "classification_confidence": 0.97,
        "extraction_confidence": 0.95,
        "is_denial_of_service": True,
        "payer_auth_problem": False,
        "missing_information": False,
        "target_record_type": "patient_account",
        "payer_portal_action": "start_appeal",
        "execute_live_follow_up": False,
        "delay_seconds": 0,
        "source_kind": "synthetic_profile",
    },
    "missing_docs": {
        "packet_id": "KSWIC-SCN-005",
        "scenario_id": "SCN-005",
        "document_type": "Request for Additional Information",
        "decision_status": "information_requested",
        "fax_category": "prior_authorization",
        "classification_confidence": 0.96,
        "extraction_confidence": 0.93,
        "is_denial_of_service": False,
        "payer_auth_problem": False,
        "missing_information": True,
        "target_record_type": "authorization",
        "payer_portal_action": "submit_missing_docs",
        "execute_live_follow_up": False,
        "delay_seconds": 0,
        "source_kind": "synthetic_profile",
    },
    "auth_problem": {
        "packet_id": "KSWIC-SCN-001",
        "scenario_id": "SCN-001",
        "document_type": "Prior Authorization Approval Letter",
        "decision_status": "approved",
        "fax_category": "prior_authorization",
        "classification_confidence": 0.98,
        "extraction_confidence": 0.97,
        "is_denial_of_service": False,
        "payer_auth_problem": True,
        "missing_information": False,
        "target_record_type": "authorization",
        "payer_portal_action": "confirm_auth",
        "execute_live_follow_up": False,
        "delay_seconds": 0,
        "source_kind": "synthetic_profile",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Invoke the Shared-folder KSWIC smoke release or Maestro release."
    )
    parser.add_argument(
        "--target",
        choices=("smoke", "maestro"),
        default="maestro",
        help="Which published release to invoke.",
    )
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILE_INPUTS),
        default="denial",
        help="Built-in payload profile to use when --input-file is omitted.",
    )
    parser.add_argument(
        "--input-file",
        help="Optional JSON payload file. Overrides --profile.",
    )
    parser.add_argument(
        "--live-ixp-results-file",
        default=str(DEFAULT_LIVE_IXP_RESULTS_PATH),
        help="Path to the live IXP results.json artifact bundle.",
    )
    parser.add_argument(
        "--live-ixp-packet",
        help="Packet folder name from live IXP results.json to adapt into the smoke-agent payload.",
    )
    parser.add_argument(
        "--live-ixp-scenario",
        help="Scenario id from live IXP results.json to adapt into the smoke-agent payload.",
    )
    parser.add_argument(
        "--live-ixp-document-id",
        help="IXP document id from live IXP results.json to adapt into the smoke-agent payload.",
    )
    parser.add_argument(
        "--folder-path",
        default=os.environ.get("UIPATH_FOLDER_PATH", DEFAULT_FOLDER_PATH),
        help="Folder path to invoke in. Defaults to UIPATH_FOLDER_PATH or Shared.",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Poll the job until it reaches a terminal state.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Maximum time to wait when --wait is used.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=5,
        help="Polling interval when --wait is used.",
    )
    parser.add_argument(
        "--prefer-client-credentials",
        action="store_true",
        help="Prefer unattended client credentials before desktop auth cache refresh.",
    )
    return parser.parse_args()


def load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.input_file:
        return json.loads(Path(args.input_file).read_text())

    if args.live_ixp_packet or args.live_ixp_scenario or args.live_ixp_document_id:
        results = load_live_ixp_results(args.live_ixp_results_file)
        result = select_live_ixp_result(
            results,
            packet_name=args.live_ixp_packet,
            scenario_id=args.live_ixp_scenario,
            ixp_document_id=args.live_ixp_document_id,
        )
        return live_ixp_result_to_smoke_payload(
            result,
            folder_path=args.folder_path,
        )

    payload = dict(PROFILE_INPUTS[args.profile])
    payload["rev_cycle_queue"] = payload.get("rev_cycle_queue") or "KSWIC_DENIALS"
    payload["shared_folder_path"] = args.folder_path
    return payload


def release_name_for_target(target: str) -> str:
    return SMOKE_RELEASE_NAME if target == "smoke" else MAESTRO_RELEASE_NAME


def invoke_release(
    auth_state: Any,
    *,
    base_url: str,
    folder_path: str,
    release_name: str,
    entry_point_path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    client = httpx.Client(timeout=30)
    folder_id = resolve_folder_id(client, base_url, folder_path, auth_state)
    try:
        release_response = request_with_auth_refresh(
            client,
            "GET",
            f"{base_url}/orchestrator_/odata/Releases",
            auth_state,
            folder_id=folder_id,
            params={"$filter": f"Name eq '{release_name}'", "$top": 5},
        )
        release_response.raise_for_status()
        releases = release_response.json().get("value", [])
        if not releases:
            raise SystemExit(
                f"Release '{release_name}' was not found in folder '{folder_path}'."
            )

        release = releases[0]
        start_response = request_with_auth_refresh(
            client,
            "POST",
            f"{base_url}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs",
            auth_state,
            folder_id=folder_id,
            json={
                "startInfo": {
                    "ReleaseKey": str(release["Key"]),
                    "ReleaseName": release_name,
                    "RunAsMe": True,
                    "InputArguments": json.dumps(payload),
                    "EntryPointPath": entry_point_path,
                }
            },
        )
        start_response.raise_for_status()
        jobs = start_response.json().get("value", [])
        if not jobs:
            raise SystemExit(
                f"StartJobs returned no jobs for release '{release_name}' in folder '{folder_path}'."
            )
        return jobs[0]
    finally:
        client.close()


def poll_job(
    auth_state: Any,
    *,
    base_url: str,
    folder_path: str,
    job_id: int,
    timeout_seconds: int,
    poll_seconds: int,
) -> dict[str, Any]:
    client = httpx.Client(timeout=30)
    folder_id = resolve_folder_id(client, base_url, folder_path, auth_state)
    deadline = time.time() + timeout_seconds
    try:
        while time.time() < deadline:
            response = request_with_auth_refresh(
                client,
                "GET",
                f"{base_url}/orchestrator_/odata/Jobs",
                auth_state,
                folder_id=folder_id,
                params={"$filter": f"Id eq {job_id}", "$top": 1},
            )
            response.raise_for_status()
            jobs = response.json().get("value", [])
            if jobs:
                job = jobs[0]
                state = str(job.get("State") or "").lower()
                output_arguments: dict[str, Any] | None = None
                if job.get("OutputArguments"):
                    try:
                        output_arguments = json.loads(job["OutputArguments"])
                    except json.JSONDecodeError:
                        output_arguments = {"raw": job["OutputArguments"]}
                summary = {
                    "job_id": job.get("Id"),
                    "job_key": job.get("Key"),
                    "state": job.get("State"),
                    "start_time": job.get("StartTime"),
                    "end_time": job.get("EndTime"),
                    "output_arguments": output_arguments,
                    "info": job.get("Info"),
                }
                if state in TERMINAL_STATES:
                    return summary
            time.sleep(poll_seconds)
    finally:
        client.close()
    raise SystemExit(
        f"Timed out waiting for job {job_id} in folder '{folder_path}' after {timeout_seconds}s."
    )


def main() -> int:
    args = parse_args()
    auth_state = load_runtime_env(
        prefer_cli_auth_cache=not args.prefer_client_credentials,
    )
    ensure_access_token_fresh(auth_state)
    base_url = os.environ["UIPATH_URL"].rstrip("/")

    payload = load_payload(args)
    release_name = release_name_for_target(args.target)
    job = invoke_release(
        auth_state,
        base_url=base_url,
        folder_path=args.folder_path,
        release_name=release_name,
        entry_point_path=TARGET_ENTRYPOINTS[args.target],
        payload=payload,
    )

    summary: dict[str, Any] = {
        "target": args.target,
        "release_name": release_name,
        "folder_path": args.folder_path,
        "payload_source": payload.get("source_kind", "unspecified"),
        "payload_bytes": len(json.dumps(payload)),
        "job_id": job.get("Id"),
        "job_key": job.get("Key"),
        "state": job.get("State"),
    }
    if payload.get("source_kind") == "live_ixp":
        summary["live_ixp"] = {
            "packet_id": payload.get("packet_id"),
            "scenario_id": payload.get("scenario_id"),
            "ixp_document_id": payload.get("ixp_document_id"),
            "source_pdf": payload.get("source_pdf"),
        }
    if args.wait:
        summary["final"] = poll_job(
            auth_state,
            base_url=base_url,
            folder_path=args.folder_path,
            job_id=int(job["Id"]),
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
