from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "cloud-api-smoke"
    / "shared-kswic-correspondence-smoke-agent"
    / "main.py"
)
SPEC = spec_from_file_location("shared_kswic_correspondence_smoke_agent", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_denial_routes_to_rev_cycle_queue() -> None:
    result = MODULE.main(
        {
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
            "rev_cycle_queue": "KSWIC_DENIALS",
            "execute_live_follow_up": False,
            "delay_seconds": 0,
            "shared_folder_path": "Shared",
            "source_kind": "synthetic_profile",
            "claim_number": "CLM-5521907",
            "service_description": "Powered wheelchair, HCPCS K0823",
        }
    )

    assert result.primary_route == "rev_cycle_denial_queue"
    assert result.cerner_action == "update_patient_account"
    assert result.rev_cycle_action == "create_denial_work_item"
    assert result.execution_status == "planned"
    assert result.tasks[1].payload["claim_number"] == "CLM-5521907"
    assert result.tasks[1].payload["service_description"] == "Powered wheelchair, HCPCS K0823"


def test_auth_problem_routes_to_cerner_auth_update() -> None:
    result = MODULE.main(
        {
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
            "rev_cycle_queue": "KSWIC_AUTH",
            "execute_live_follow_up": False,
            "delay_seconds": 0,
            "shared_folder_path": "Shared",
            "source_kind": "synthetic_profile",
            "authorization_number": "PA-884201",
            "member_id": "PHH-484920-01",
        }
    )

    assert result.primary_route == "cerner_auth_update"
    assert result.cerner_action == "update_authorization_record"
    assert result.rev_cycle_action == "none"
    assert result.tasks[1].payload["authorization_number"] == "PA-884201"
    assert result.member_id == "PHH-484920-01"


def test_low_confidence_forces_manual_triage() -> None:
    result = MODULE.main(
        {
            "packet_id": "KSWIC-SCN-005",
            "scenario_id": "SCN-005",
            "document_type": "Request for Additional Information",
            "decision_status": "information_requested",
            "fax_category": "prior_authorization",
            "classification_confidence": 0.83,
            "extraction_confidence": 0.89,
            "is_denial_of_service": False,
            "payer_auth_problem": False,
            "missing_information": True,
            "target_record_type": "authorization",
            "payer_portal_action": "submit_missing_docs",
            "rev_cycle_queue": "KSWIC_AUTH",
            "execute_live_follow_up": False,
            "delay_seconds": 0,
            "shared_folder_path": "Shared",
            "source_kind": "synthetic_profile",
            "note_text": "Claim pended due to missing records.",
        }
    )

    assert result.primary_route == "manual_triage"
    assert result.needs_human_review is True
    assert result.execution_status == "skipped"
    assert result.tasks[0].payload["note_text"] == "Claim pended due to missing records."
