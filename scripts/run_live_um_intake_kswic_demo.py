#!/usr/bin/env python3
"""Run a small KSWIC fake-doc batch through the live UM Intake IXP extractor."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path
import sys
import time
from typing import Any

import httpx

from kswic_live_ixp_adapter import live_ixp_result_to_smoke_payload
from uipath_cloud_auth import ensure_access_token_fresh, load_runtime_env


ROOT = Path(__file__).resolve().parent.parent
KSWIC_ROOT = ROOT / "demo_resources" / "kswic-payer-correspondence-demo"
GENERATED_PACKETS_DIR = KSWIC_ROOT / "generated_packets"
DEFAULT_DOCS = (
    "scn_001_prior_authorization_approval_letter",
    "scn_003_prior_authorization_denial_letter",
    "scn_005_request_for_additional_information",
)
DEFAULT_OUTPUT_DIR = KSWIC_ROOT / "live_ixp"
DEFAULT_PROJECT_NAME = "UM Intake"
DEFAULT_PROJECT_TAG = "live"


def _log(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)


def _guess_mime_type(path: str) -> str:
    mime_type, _ = mimetypes.guess_type(path)
    return mime_type or "application/octet-stream"


def _derive_async_result_url(async_url: str, operation_id: str) -> str:
    if "/start?" not in async_url:
        raise ValueError(f"Unsupported async URL shape: {async_url}")
    return async_url.replace("/start?", f"/result/{operation_id}?", 1)


def _extract_operation_status(payload: dict[str, Any]) -> str | None:
    status = (
        payload.get("status")
        or payload.get("Status")
        or payload.get("operationStatus")
        or payload.get("OperationStatus")
    )
    return str(status) if status is not None else None


def _extract_operation_message(payload: dict[str, Any]) -> str | None:
    for key in ("message", "Message", "errorMessage", "ErrorMessage", "detail", "Detail"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def _field_name(field: dict[str, Any]) -> str | None:
    value = (
        field.get("FieldName")
        or field.get("fieldName")
        or field.get("FieldId")
        or field.get("fieldId")
    )
    if value is None:
        return None
    return str(value).strip() or None


def _field_is_missing(field: dict[str, Any]) -> bool:
    value = field.get("IsMissing")
    if value is None:
        value = field.get("isMissing")
    return bool(value)


def _field_values(field: dict[str, Any]) -> list[Any]:
    raw_values = field.get("Values") or field.get("values") or []
    values: list[Any] = []
    for item in raw_values:
        if not isinstance(item, dict):
            continue
        if item.get("Components") or item.get("components"):
            continue
        value = item.get("Value")
        if value is None:
            value = item.get("value")
        values.append(value)
    return values


def _raw_field_values(field: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in (field.get("Values") or field.get("values") or []) if isinstance(item, dict)]


def _value_components(value: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in (value.get("Components") or value.get("components") or []) if isinstance(item, dict)]


def _normalize_leaf_value(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _collect_leaf_fields(field: dict[str, Any], prefix: tuple[str, ...]) -> dict[str, Any]:
    field_name = _field_name(field)
    next_prefix = prefix
    if field_name and field_name not in {"Header", "Body"}:
        next_prefix = (*prefix, field_name)

    flattened: dict[str, Any] = {}
    raw_values = _raw_field_values(field)
    for item in raw_values:
        components = _value_components(item)
        if not components:
            continue
        for component in components:
            flattened.update(_collect_leaf_fields(component, next_prefix))
    if flattened:
        return flattened

    if not next_prefix:
        return {}

    values = [_normalize_leaf_value(value) for value in _field_values(field)]
    values = [value for value in values if value is not None]
    if values:
        flattened[" > ".join(next_prefix)] = values[0] if len(values) == 1 else values
    elif _field_is_missing(field):
        flattened[" > ".join(next_prefix)] = None
    return flattened


def _component_table_rows(field: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    body_fields: list[dict[str, Any]] = []
    for value in _raw_field_values(field):
        for component in _value_components(value):
            if _field_name(component) == "Body":
                body_fields.append(component)

    for body_field in body_fields:
        for value in _raw_field_values(body_field):
            row: dict[str, Any] = {}
            for component in _value_components(value):
                row.update(_collect_leaf_fields(component, ()))
            if row:
                rows.append(row)
    return rows


def _normalize_fields(results_document: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for field in results_document.get("Fields") or results_document.get("fields") or []:
        if not isinstance(field, dict):
            continue
        field_name = _field_name(field)
        if not field_name:
            continue
        field_type = str(field.get("FieldType") or field.get("fieldType") or "").lower()
        if field_type == "table":
            component_rows = _component_table_rows(field)
            if len(component_rows) == 1:
                for key, value in component_rows[0].items():
                    summary[f"{field_name} > {key}"] = value
                continue
            if component_rows:
                continue

        is_missing = _field_is_missing(field)
        values = _field_values(field)
        if is_missing or not values:
            summary[str(field_name)] = None
        elif len(values) == 1:
            summary[str(field_name)] = _normalize_leaf_value(values[0])
        else:
            summary[str(field_name)] = [_normalize_leaf_value(value) for value in values]
    return summary


def _normalize_tables(results_document: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for field in results_document.get("Fields") or results_document.get("fields") or []:
        if not isinstance(field, dict):
            continue
        field_type = field.get("FieldType") or field.get("fieldType")
        if str(field_type).lower() != "table":
            continue
        field_name = _field_name(field)
        if not field_name:
            continue
        values = field.get("Values") or field.get("values") or []
        rows: list[dict[str, Any]] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            cells = value.get("Cells") or value.get("cells") or []
            current: dict[int, dict[str, Any]] = {}
            for cell in cells:
                if not isinstance(cell, dict):
                    continue
                row_index = cell.get("RowIndex")
                if row_index is None:
                    row_index = cell.get("rowIndex")
                col_name = cell.get("ColumnName") or cell.get("columnName")
                col_index = cell.get("ColumnIndex")
                if col_index is None:
                    col_index = cell.get("columnIndex")
                key = str(col_name or f"column_{col_index}")
                cell_value = cell.get("Value")
                if cell_value is None:
                    cell_value = cell.get("value")
                if row_index is None:
                    row_index = len(current)
                current.setdefault(int(row_index), {})[key] = cell_value
            rows.extend(current[index] for index in sorted(current))
        if not rows:
            rows = _component_table_rows(field)
        tables[str(field_name)] = rows
    return tables


class DuClient:
    def __init__(self, *, tenant_url: str, access_token: str, timeout_seconds: int) -> None:
        self._tenant_url = tenant_url.rstrip("/")
        self._http = httpx.Client(timeout=float(timeout_seconds))
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "accept": "application/json",
        }

    def close(self) -> None:
        self._http.close()

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        headers = dict(self._headers)
        headers.update(kwargs.pop("headers", {}))
        response = self._http.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response

    def list_projects(self) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            f"{self._tenant_url}/du_/api/framework/projects?api-version=1",
        )
        return response.json().get("projects") or []

    def get_json(self, url: str) -> dict[str, Any]:
        return self.request("GET", url).json()

    def digitize_document(self, digitization_start_url: str, file_path: Path) -> str:
        with file_path.open("rb") as handle:
            response = self.request(
                "POST",
                digitization_start_url,
                files={
                    "file": (
                        file_path.name,
                        handle,
                        _guess_mime_type(file_path.name),
                    )
                },
            )
        payload = response.json()
        document_id = payload.get("documentId") or payload.get("DocumentId")
        if not document_id:
            raise ValueError(f"Digitization response did not contain documentId: {payload}")
        return str(document_id)

    def extract_document_async(
        self,
        extractor_async_url: str,
        document_id: str,
        *,
        timeout_seconds: int,
        poll_seconds: int,
    ) -> dict[str, Any]:
        response = self.request(
            "POST",
            extractor_async_url,
            json={"documentId": document_id},
        )
        payload = response.json()
        operation_id = payload.get("operationId")
        if not operation_id:
            raise ValueError(f"Extraction start response did not contain operationId: {payload}")

        result_url = _derive_async_result_url(extractor_async_url, str(operation_id))
        deadline = time.time() + timeout_seconds
        started_at = time.time()
        poll_count = 0
        last_status: str | None = None

        _log(
            "du_extract_start",
            document_id=document_id,
            operation_id=str(operation_id),
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
        )

        while time.time() < deadline:
            poll_count += 1
            result_payload = self.request("GET", result_url).json()
            status = _extract_operation_status(result_payload)
            nested_result = result_payload.get("result")
            extraction_result = result_payload.get("extractionResult") or result_payload.get("ExtractionResult")
            if extraction_result is None and isinstance(nested_result, dict):
                extraction_result = nested_result.get("extractionResult") or nested_result.get("ExtractionResult")
            if poll_count == 1 or status != last_status:
                _log(
                    "du_extract_poll",
                    document_id=document_id,
                    operation_id=str(operation_id),
                    poll_count=poll_count,
                    seconds_elapsed=round(time.time() - started_at, 1),
                    operation_status=status,
                    has_extraction_result=bool(extraction_result),
                    message=_extract_operation_message(result_payload),
                )
            last_status = status
            if extraction_result:
                _log(
                    "du_extract_done",
                    document_id=document_id,
                    operation_id=str(operation_id),
                    poll_count=poll_count,
                    seconds_elapsed=round(time.time() - started_at, 1),
                    operation_status=status,
                )
                return nested_result if isinstance(nested_result, dict) else result_payload
            if status and str(status).lower() in {"failed", "faulted"}:
                raise RuntimeError(
                    f"Extraction failed for document {document_id}: {_extract_operation_message(result_payload) or result_payload}"
                )
            time.sleep(poll_seconds)
        _log(
            "du_extract_timeout",
            document_id=document_id,
            operation_id=str(operation_id),
            poll_count=poll_count,
            seconds_elapsed=round(time.time() - started_at, 1),
            operation_status=last_status,
        )
        raise TimeoutError(f"Extraction did not complete within {timeout_seconds} seconds.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run selected KSWIC fake PDFs through the live UM Intake IXP extractor."
    )
    parser.add_argument(
        "--project-name",
        default=DEFAULT_PROJECT_NAME,
        help="DU/IXP project name to use. Defaults to UM Intake.",
    )
    parser.add_argument(
        "--tag-name",
        default=DEFAULT_PROJECT_TAG,
        help="Project version tag to use when available. Defaults to live.",
    )
    parser.add_argument(
        "--doc",
        action="append",
        help="Packet folder name under generated_packets. Can be passed multiple times.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Per-document extraction timeout.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=5,
        help="Polling interval for async extraction.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for live IXP artifacts.",
    )
    return parser.parse_args()


def _choose_project(projects: list[dict[str, Any]], project_name: str) -> dict[str, Any]:
    wanted = project_name.strip().lower()
    for project in projects:
        if str(project.get("name", "")).strip().lower() == wanted:
            return project
    available = ", ".join(sorted(str(project.get("name", "")) for project in projects[:25]))
    raise SystemExit(f"DU project {project_name!r} not found. Sample available projects: {available}")


def _choose_live_extractor(
    project_details: dict[str, Any],
    tag_name: str,
) -> tuple[dict[str, Any], int | None, str | None, str | None]:
    versions = project_details.get("projectVersions") or []
    normalized_tag = tag_name.strip().lower()
    tag_aliases = {"production": "live"}
    matched_tag = tag_aliases.get(normalized_tag, normalized_tag)

    selected_version: dict[str, Any] | None = None
    tagged_versions = [
        version
        for version in versions
        if str(version.get("tag") or "").strip().lower() == matched_tag
    ]
    if tagged_versions:
        selected_version = max(
            tagged_versions,
            key=lambda item: int(item.get("version") or 0),
        )
    else:
        deployed_versions = [v for v in versions if v.get("deployed")]
        if deployed_versions:
            selected_version = max(
                deployed_versions,
                key=lambda item: int(item.get("version") or 0),
            )
        elif versions:
            selected_version = max(
                versions,
                key=lambda item: int(item.get("version") or 0),
            )
    if selected_version is None:
        raise SystemExit("Project details did not expose any projectVersions.")

    version_number = int(selected_version.get("version") or 0)
    version_name = str(selected_version.get("versionName") or version_number)
    version_tag = str(selected_version.get("tag") or "").strip() or None
    extractors = [
        extractor
        for extractor in (project_details.get("extractors") or [])
        if int(extractor.get("projectVersion") or 0) == version_number
    ]
    if not extractors:
        raise SystemExit(f"No extractor was found for project version {version_number}.")
    return extractors[0], version_number, version_name, version_tag


def _load_source_metadata(packet_dir: Path) -> dict[str, Any]:
    json_paths = sorted(packet_dir.glob("*.json"))
    if not json_paths:
        return {}
    return json.loads(json_paths[0].read_text())


def _result_file_name(packet_name: str) -> str:
    return f"{packet_name}.json"


def _summary_markdown(
    *,
    project_name: str,
    project_id: str,
    project_version: int | None,
    project_version_name: str | None,
    project_tag_name: str | None,
    results: list[dict[str, Any]],
) -> str:
    def pick_first(mapping: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = mapping.get(key)
            if value not in (None, "", []):
                return value
        return ""

    lines = [
        "# Live UM Intake IXP Run",
        "",
        f"- Project: `{project_name}` (`{project_id}`)",
        f"- Version: `{project_version_name or project_version}`",
        f"- Tag: `{project_tag_name or 'n/a'}`",
        f"- Documents processed: `{len(results)}`",
        "",
        "| Packet | Scenario | Status | Member ID | Ref/Claim | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in results:
        normalized = item.get("normalized_fields") or {}
        member_id = pick_first(
            normalized,
            "Member Information > Member ID",
            "Member ID",
            "member_id",
        )
        ref = pick_first(
            normalized,
            "Request Information > Previous Authorization Number",
            "Request Information > Existing Authorization Number",
            "Previous Authorization Number",
            "Existing Authorization Number",
            "Authorization Number",
            "Claim Number",
        )
        notes = pick_first(
            normalized,
            "Notes > Notes",
            "Notes",
            "Request Information > Treatment Type",
            "Service Lines > Code Description",
        )
        if isinstance(notes, str) and len(notes) > 80:
            notes = notes[:77] + "..."
        lines.append(
            f"| `{item['packet_name']}` | `{item.get('scenario_id','')}` | `{item['status']}` | "
            f"`{member_id}` | `{ref}` | {notes} |"
        )
    return "\n".join(lines) + "\n"


def _review_payloads(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for item in results:
        if item.get("status") != "success":
            continue
        normalized = item.get("normalized_fields") or {}
        smoke_preview = live_ixp_result_to_smoke_payload(item)
        payloads.append(
            {
                "packet_name": item.get("packet_name"),
                "scenario_id": item.get("scenario_id"),
                "document_id": item.get("document_id"),
                "document_type": item.get("document_type"),
                "project_name": item.get("project_name"),
                "project_version_name": item.get("project_version_name"),
                "project_tag_name": item.get("project_tag_name"),
                "source_pdf": item.get("source_pdf"),
                "review_required": True,
                "review_mode": "interim_json_review",
                "review_focus": [
                    "document_type",
                    "member_id",
                    "authorization_or_claim_number",
                    "service_description",
                    "routing_flags",
                ],
                "extracted_preview": {
                    "member_id": normalized.get("Member Information > Member ID"),
                    "authorization_number": normalized.get("Request Information > Existing Authorization Number"),
                    "claim_number": normalized.get("Claim Number"),
                    "service_description": normalized.get("Service Lines > Code Description")
                    or normalized.get("Request Information > Treatment Type"),
                    "note_text": normalized.get("Notes > Notes") or normalized.get("Notes"),
                    "provider_name": normalized.get("Provider Information > Servicing Provider > Provider Name"),
                    "request_date": normalized.get("Request Information > Date of Request"),
                },
                "maestro_routing_preview": {
                    "decision_status": smoke_preview["decision_status"],
                    "fax_category": smoke_preview["fax_category"],
                    "is_denial_of_service": smoke_preview["is_denial_of_service"],
                    "payer_auth_problem": smoke_preview["payer_auth_problem"],
                    "missing_information": smoke_preview["missing_information"],
                    "target_record_type": smoke_preview["target_record_type"],
                    "payer_portal_action": smoke_preview["payer_portal_action"],
                    "rev_cycle_queue": smoke_preview["rev_cycle_queue"],
                },
                "action_app_gap": {
                    "supported_maestro_pattern": "User task -> Create Action App task",
                    "required_input_type": "ContentValidationData",
                    "missing_piece_in_this_repo": (
                        "Live IXP API output is available, but DU validation artifacts and the deployed "
                        "Action App task are not yet created in Studio Web."
                    ),
                },
            }
        )
    return payloads


def _review_summary_markdown(review_payloads: list[dict[str, Any]]) -> str:
    lines = [
        "# Extraction Review Queue",
        "",
        "These payloads are reviewer-oriented summaries derived from the live `UM Intake` run.",
        "They are not yet UiPath `ContentValidationData` artifacts.",
        "",
        "| Packet | Type | Member ID | Auth/Claim | Suggested Route | Review Mode |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in review_payloads:
        preview = item.get("extracted_preview") or {}
        route = item.get("maestro_routing_preview") or {}
        ref = preview.get("authorization_number") or preview.get("claim_number") or ""
        lines.append(
            f"| `{item.get('packet_name')}` | `{item.get('document_type')}` | "
            f"`{preview.get('member_id') or ''}` | `{ref}` | "
            f"`{route.get('fax_category')}/{route.get('decision_status')}` | `{item.get('review_mode')}` |"
        )
    lines.extend(
        [
            "",
            "To turn this into a true Maestro review step, follow the UiPath-supported path:",
            "1. Create DU validation artifacts in an RPA workflow.",
            "2. Create an Action App task with `validationData: ContentValidationData`.",
            "3. Bind a Maestro User task to that Action App and pause for reviewer approval.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    auth_state = load_runtime_env()
    ensure_access_token_fresh(auth_state)
    access_token = os.environ["UIPATH_ACCESS_TOKEN"]
    tenant_url = os.environ["UIPATH_URL"].rstrip("/")

    packet_names = args.doc or list(DEFAULT_DOCS)
    packet_dirs = [GENERATED_PACKETS_DIR / name for name in packet_names]
    for packet_dir in packet_dirs:
        if not packet_dir.exists():
            raise SystemExit(f"Packet directory not found: {packet_dir}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    client = DuClient(
        tenant_url=tenant_url,
        access_token=access_token,
        timeout_seconds=max(args.timeout_seconds, 30),
    )

    try:
        project = _choose_project(client.list_projects(), args.project_name)
        project_details = client.get_json(str(project["detailsUrl"]))
        extractor, version_number, version_name, version_tag = _choose_live_extractor(
            project_details,
            args.tag_name,
        )
        extractor_details = client.get_json(str(extractor["detailsUrl"]))
        async_url = extractor_details.get("asyncUrl")
        if not async_url:
            raise SystemExit(f"Selected extractor did not expose asyncUrl: {extractor_details}")

        _log(
            "du_project_selected",
            project_id=project.get("id"),
            project_name=project.get("name"),
            project_version=version_number,
            project_version_name=version_name,
            project_tag=version_tag,
            extractor_id=extractor.get("id"),
        )

        results: list[dict[str, Any]] = []
        for packet_dir in packet_dirs:
            pdf_paths = sorted(packet_dir.glob("*.pdf"))
            if not pdf_paths:
                results.append(
                    {
                        "packet_name": packet_dir.name,
                        "scenario_id": _load_source_metadata(packet_dir).get("scenario_id"),
                        "status": "error",
                        "error": "No PDF was found in packet directory.",
                    }
                )
                continue

            pdf_path = pdf_paths[0]
            source_metadata = _load_source_metadata(packet_dir)
            try:
                _log(
                    "document_start",
                    packet_name=packet_dir.name,
                    scenario_id=source_metadata.get("scenario_id"),
                    source_pdf=str(pdf_path),
                )
                document_id = client.digitize_document(str(project["digitizationStartUrl"]), pdf_path)
                _log(
                    "document_digitized",
                    packet_name=packet_dir.name,
                    scenario_id=source_metadata.get("scenario_id"),
                    document_id=document_id,
                )
                extraction_payload = client.extract_document_async(
                    str(async_url),
                    document_id,
                    timeout_seconds=args.timeout_seconds,
                    poll_seconds=args.poll_seconds,
                )
                extraction_result = (
                    extraction_payload.get("extractionResult")
                    or extraction_payload.get("ExtractionResult")
                    or {}
                )
                results_document = (
                    extraction_result.get("ResultsDocument")
                    or extraction_result.get("resultsDocument")
                    or {}
                )
                normalized_fields = _normalize_fields(results_document)
                normalized_tables = _normalize_tables(results_document)

                raw_output_path = raw_dir / _result_file_name(packet_dir.name)
                raw_output_path.write_text(
                    json.dumps(
                        {
                            "packet_name": packet_dir.name,
                            "scenario_id": source_metadata.get("scenario_id"),
                            "project_name": project.get("name"),
                            "project_id": project.get("id"),
                            "project_version": version_number,
                            "project_version_name": version_name,
                            "project_tag_name": version_tag,
                            "document_id": document_id,
                            "source_pdf": str(pdf_path),
                            "extraction_payload": extraction_payload,
                        },
                        indent=2,
                        ensure_ascii=True,
                        sort_keys=True,
                    )
                )

                results.append(
                    {
                        "packet_name": packet_dir.name,
                        "scenario_id": source_metadata.get("scenario_id"),
                        "source_pdf": str(pdf_path),
                        "document_type": source_metadata.get("document_type"),
                        "status": "success",
                        "document_id": document_id,
                        "project_name": project.get("name"),
                        "project_id": project.get("id"),
                        "project_version": version_number,
                        "project_version_name": version_name,
                        "project_tag_name": version_tag,
                        "normalized_fields": normalized_fields,
                        "normalized_tables": normalized_tables,
                        "raw_output_path": str(raw_output_path),
                    }
                )
                _log(
                    "document_done",
                    packet_name=packet_dir.name,
                    scenario_id=source_metadata.get("scenario_id"),
                    document_id=document_id,
                    normalized_field_count=len(normalized_fields),
                    normalized_table_count=len(normalized_tables),
                )
            except Exception as exc:
                results.append(
                    {
                        "packet_name": packet_dir.name,
                        "scenario_id": source_metadata.get("scenario_id"),
                        "source_pdf": str(pdf_path),
                        "document_type": source_metadata.get("document_type"),
                        "status": "error",
                        "error": str(exc),
                    }
                )
                _log(
                    "document_error",
                    packet_name=packet_dir.name,
                    scenario_id=source_metadata.get("scenario_id"),
                    source_pdf=str(pdf_path),
                    error=str(exc),
                )

        manifest = {
            "project_name": project.get("name"),
            "project_id": project.get("id"),
            "project_version": version_number,
            "project_version_name": version_name,
            "project_tag_name": version_tag,
            "documents": results,
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=True, sort_keys=True)
        )
        (output_dir / "results.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=True, sort_keys=True)
        )
        (output_dir / "summary.md").write_text(
            _summary_markdown(
                project_name=str(project.get("name")),
                project_id=str(project.get("id")),
                project_version=version_number,
                project_version_name=version_name,
                project_tag_name=version_tag,
                results=results,
            )
        )
        review_payloads = _review_payloads(results)
        (output_dir / "review_payloads.json").write_text(
            json.dumps(review_payloads, indent=2, ensure_ascii=True, sort_keys=True)
        )
        (output_dir / "review_summary.md").write_text(
            _review_summary_markdown(review_payloads)
        )
    finally:
        client.close()

    print(
        json.dumps(
            {
                "project_name": project.get("name"),
                "project_id": project.get("id"),
                "project_version": version_number,
                "project_version_name": version_name,
                "project_tag_name": version_tag,
                "output_dir": str(output_dir),
                "processed": len(results),
                "successes": len([item for item in results if item.get("status") == "success"]),
                "errors": len([item for item in results if item.get("status") != "success"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
