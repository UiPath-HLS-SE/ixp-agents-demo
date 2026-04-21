from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "scripts" / "kswic_live_ixp_adapter.py"
SMOKE_AGENT_PATH = (
    ROOT
    / "cloud-api-smoke"
    / "shared-kswic-correspondence-smoke-agent"
    / "main.py"
)


def _load_module(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ADAPTER = _load_module("kswic_live_ixp_adapter", ADAPTER_PATH)
SMOKE_AGENT = _load_module("shared_kswic_correspondence_smoke_agent_live", SMOKE_AGENT_PATH)


def test_live_ixp_auth_denial_maps_to_auth_follow_up() -> None:
    results = ADAPTER.load_live_ixp_results()
    record = ADAPTER.select_live_ixp_result(
        results,
        packet_name="scn_003_prior_authorization_denial_letter",
    )
    payload = ADAPTER.live_ixp_result_to_smoke_payload(record)

    assert payload["source_kind"] == "live_ixp"
    assert payload["decision_status"] == "denied"
    assert payload["fax_category"] == "prior_authorization"
    assert payload["payer_auth_problem"] is True
    assert payload["target_record_type"] == "authorization"
    assert payload["authorization_number"] == "PA-118943"
    assert payload["member_id"] == "FHC-228174-02"

    result = SMOKE_AGENT.main(payload)
    assert result.primary_route == "cerner_auth_update"
    assert result.payer_portal_action == "start_appeal"
    assert result.authorization_number == "PA-118943"


def test_live_ixp_missing_docs_maps_to_portal_follow_up() -> None:
    results = ADAPTER.load_live_ixp_results()
    record = ADAPTER.select_live_ixp_result(
        results,
        packet_name="scn_005_request_for_additional_information",
    )
    payload = ADAPTER.live_ixp_result_to_smoke_payload(record)

    assert payload["source_kind"] == "live_ixp"
    assert payload["decision_status"] == "pended"
    assert payload["missing_information"] is True
    assert payload["target_record_type"] == "patient_account"
    assert (
        payload["note_text"]
        == "Claim pended due to missing operative report and itemized bill."
    )

    result = SMOKE_AGENT.main(payload)
    assert result.primary_route == "payer_portal_follow_up"
    assert result.cerner_action == "log_patient_account_note"
    assert result.tasks[0].payload["ixp_document_id"] == record["document_id"]
