#!/usr/bin/env python3
"""Adapt live KSWIC UM Intake IXP results into the Shared smoke-agent contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS_PATH = (
    ROOT
    / "demo_resources"
    / "kswic-payer-correspondence-demo"
    / "live_ixp"
    / "results.json"
)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return text
    return str(value)


def _meaningful_value(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    if text.lower() in {"n/a", "na", "none", "null"}:
        return None
    return text


def _pick(mapping: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _clean_text(mapping.get(key))
        if value is not None:
            return value
    return None


def _pick_meaningful(mapping: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _meaningful_value(mapping.get(key))
        if value is not None:
            return value
    return None


def load_live_ixp_results(path: str | Path = DEFAULT_RESULTS_PATH) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON array in {path}, got {type(payload).__name__}.")
    return [item for item in payload if isinstance(item, dict)]


def select_live_ixp_result(
    results: list[dict[str, Any]],
    *,
    packet_name: str | None = None,
    scenario_id: str | None = None,
    ixp_document_id: str | None = None,
) -> dict[str, Any]:
    candidates = results

    if packet_name:
        candidates = [item for item in candidates if item.get("packet_name") == packet_name]
    if scenario_id:
        candidates = [item for item in candidates if item.get("scenario_id") == scenario_id]
    if ixp_document_id:
        candidates = [item for item in candidates if item.get("document_id") == ixp_document_id]

    if not candidates:
        raise ValueError(
            "No live IXP result matched the requested selector. "
            f"packet_name={packet_name!r} scenario_id={scenario_id!r} ixp_document_id={ixp_document_id!r}"
        )
    if len(candidates) > 1:
        names = ", ".join(sorted(str(item.get("packet_name") or item.get("scenario_id") or "") for item in candidates))
        raise ValueError(
            "Live IXP selector matched more than one record. "
            f"Refine the selector. Matches: {names}"
        )
    return candidates[0]


def _derive_decision_status(document_type: str, fields: dict[str, Any]) -> str:
    doc_type = document_type.lower()
    note_text = (_pick(fields, "Notes > Notes", "Notes") or "").lower()

    if "partial approval" in doc_type:
        return "partially_approved"
    if "approval" in doc_type and "denial" not in doc_type:
        return "approved"
    if "request for additional information" in doc_type:
        return "pended"
    if "appeal receipt acknowledgment" in doc_type:
        return "appeal_received"
    if "appeal determination overturn" in doc_type or "appeal overturn" in doc_type:
        return "overturned"
    if "explanation of benefits" in doc_type:
        return "paid"
    if "coordination of benefits" in doc_type:
        return "information_requested"
    if "overpayment" in doc_type or "recoupment" in doc_type:
        return "recoupment"
    if "denial" in doc_type:
        return "denied"
    if "paid" in note_text:
        return "paid"
    if "missing" in note_text or "additional documentation" in note_text:
        return "pended"
    return "information_requested"


def _derive_fax_category(document_type: str) -> str:
    doc_type = document_type.lower()

    if "prior authorization" in doc_type or "pharmacy" in doc_type or "network gap exception" in doc_type:
        return "prior_authorization"
    if "appeal" in doc_type:
        return "appeal"
    if "explanation of benefits" in doc_type or "payment" in doc_type or "overpayment" in doc_type:
        return "payment_posting"
    if "eligibility" in doc_type or "termination" in doc_type or "coordination of benefits" in doc_type:
        return "eligibility"
    if "claim" in doc_type or "additional information" in doc_type:
        return "claim_denial"
    return "other"


def _estimate_extraction_confidence(
    *,
    member_id: str | None,
    claim_number: str | None,
    authorization_number: str | None,
    service_description: str | None,
    note_text: str | None,
    request_date: str | None,
) -> float:
    score = 0.86
    if member_id:
        score += 0.03
    if claim_number or authorization_number:
        score += 0.03
    if service_description:
        score += 0.03
    if note_text:
        score += 0.03
    if request_date:
        score += 0.02
    return round(min(score, 0.97), 2)


def live_ixp_result_to_smoke_payload(
    result: dict[str, Any],
    *,
    folder_path: str = "Shared",
    execute_live_follow_up: bool = False,
    delay_seconds: int = 0,
) -> dict[str, Any]:
    fields = result.get("normalized_fields") or {}
    if not isinstance(fields, dict):
        raise ValueError("Live IXP result did not contain normalized_fields.")

    document_type = _clean_text(result.get("document_type")) or "Unknown Document"
    scenario_id = _clean_text(result.get("scenario_id")) or "UNKNOWN"
    packet_name = _clean_text(result.get("packet_name")) or scenario_id.lower()
    member_id = _pick_meaningful(
        fields,
        "Member Information > Member ID",
        "Member ID",
    )
    claim_number = _pick_meaningful(
        fields,
        "Claim Information > Claim Number",
        "Claim Number",
    )
    authorization_number = _pick_meaningful(
        fields,
        "Request Information > Existing Authorization Number",
        "Request Information > Previous Authorization Number",
        "Existing Authorization Number",
        "Previous Authorization Number",
        "Authorization Number",
    )
    service_description = _pick_meaningful(
        fields,
        "Service Lines > Code Description",
        "Request Information > Treatment Type",
    )
    note_text = _pick_meaningful(fields, "Notes > Notes", "Notes")
    request_date = _pick_meaningful(fields, "Request Information > Date of Request")

    decision_status = _derive_decision_status(document_type, fields)
    fax_category = _derive_fax_category(document_type)
    missing_information = decision_status in {"pended", "information_requested"} or (
        note_text is not None and "missing" in note_text.lower()
    )
    payer_auth_problem = fax_category == "prior_authorization" and decision_status in {
        "denied",
        "information_requested",
        "pended",
    }
    is_denial_of_service = fax_category == "claim_denial" and decision_status == "denied"
    target_record_type = "authorization" if fax_category == "prior_authorization" else "patient_account"

    if missing_information:
        payer_portal_action = "submit_missing_docs"
    elif target_record_type == "authorization" and decision_status in {"approved", "partially_approved"}:
        payer_portal_action = "confirm_auth"
    elif decision_status in {"denied", "appeal_received"}:
        payer_portal_action = "start_appeal"
    elif decision_status in {"paid", "overturned", "recoupment"}:
        payer_portal_action = "check_claim_status"
    else:
        payer_portal_action = "check_claim_status"

    if target_record_type == "authorization":
        rev_cycle_queue = "KSWIC_AUTH"
    elif missing_information:
        rev_cycle_queue = "KSWIC_BILLING"
    else:
        rev_cycle_queue = "KSWIC_DENIALS"

    return {
        "packet_id": f"KSWIC-{scenario_id}",
        "scenario_id": scenario_id,
        "document_type": document_type,
        "decision_status": decision_status,
        "fax_category": fax_category,
        "classification_confidence": 0.95 if document_type != "Unknown Document" else 0.88,
        "extraction_confidence": _estimate_extraction_confidence(
            member_id=member_id,
            claim_number=claim_number,
            authorization_number=authorization_number,
            service_description=service_description,
            note_text=note_text,
            request_date=request_date,
        ),
        "is_denial_of_service": is_denial_of_service,
        "payer_auth_problem": payer_auth_problem,
        "missing_information": missing_information,
        "target_record_type": target_record_type,
        "payer_portal_action": payer_portal_action,
        "rev_cycle_queue": rev_cycle_queue,
        "execute_live_follow_up": execute_live_follow_up,
        "delay_seconds": delay_seconds,
        "shared_folder_path": folder_path,
        "source_kind": "live_ixp",
        "source_pdf": _clean_text(result.get("source_pdf")),
        "ixp_document_id": _clean_text(result.get("document_id")),
        "member_id": member_id,
        "claim_number": claim_number,
        "authorization_number": authorization_number,
        "service_description": service_description,
        "note_text": note_text,
    }
