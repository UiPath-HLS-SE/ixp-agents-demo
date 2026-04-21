from __future__ import annotations

from datetime import UTC, datetime
import json
import time
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, Field


DecisionStatus: TypeAlias = Literal[
    "approved",
    "denied",
    "pended",
    "appeal_received",
    "overturned",
    "paid",
    "information_requested",
    "partially_approved",
    "recoupment",
]
FaxCategory: TypeAlias = Literal[
    "prior_authorization",
    "claim_denial",
    "appeal",
    "payment_posting",
    "eligibility",
    "other",
]
PortalAction: TypeAlias = Literal[
    "confirm_auth",
    "submit_missing_docs",
    "start_appeal",
    "check_claim_status",
    "none",
]
TargetRecordType: TypeAlias = Literal["patient_account", "authorization", "none"]
RouteCode: TypeAlias = Literal[
    "cerner_auth_update",
    "cerner_patient_account_update",
    "payer_portal_follow_up",
    "rev_cycle_denial_queue",
    "manual_triage",
]
TaskStatus: TypeAlias = Literal["planned", "executed", "not_needed"]
ExecutionStatus: TypeAlias = Literal["planned", "executed", "skipped"]


class GraphInput(BaseModel):
    packet_id: str = Field(
        default="KSWIC-SCN-004",
        description="Demo business identifier for the payer-correspondence packet.",
    )
    scenario_id: str = Field(
        default="SCN-004",
        description="Scenario identifier from the synthetic correspondence catalog.",
    )
    document_type: str = Field(
        default="Claim Denial Letter",
        description="Human-readable document family extracted from the fax packet.",
    )
    decision_status: DecisionStatus = Field(
        default="denied",
        description="High-level decision or lifecycle status extracted from the correspondence.",
    )
    fax_category: FaxCategory = Field(
        default="claim_denial",
        description="Normalized classification bucket for Maestro routing.",
    )
    classification_confidence: float = Field(
        default=0.97,
        ge=0.0,
        le=1.0,
        description="Confidence score for document-family classification.",
    )
    extraction_confidence: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Confidence score for critical field extraction.",
    )
    is_denial_of_service: bool = Field(
        default=True,
        description="True when the correspondence indicates a denial requiring revenue-cycle follow-up.",
    )
    payer_auth_problem: bool = Field(
        default=False,
        description="True when the notice reflects an authorization issue rather than a clean denial.",
    )
    missing_information: bool = Field(
        default=False,
        description="True when the payer is requesting additional records or documentation.",
    )
    target_record_type: TargetRecordType = Field(
        default="patient_account",
        description="Cerner record target for the downstream update.",
    )
    payer_portal_action: PortalAction = Field(
        default="start_appeal",
        description="Dummy downstream payer-portal action to simulate.",
    )
    rev_cycle_queue: str | None = Field(
        default="KSWIC_DENIALS",
        description="Dummy rev-cycle queue for denial and follow-up work items.",
    )
    execute_live_follow_up: bool = Field(
        default=False,
        description="When true, simulate the downstream automations by waiting for delay_seconds before returning.",
    )
    delay_seconds: int = Field(
        default=0,
        ge=0,
        le=300,
        description="Optional artificial delay so Shared-folder smoke jobs stay visible in Orchestrator.",
    )
    shared_folder_path: str = Field(
        default="Shared",
        description="Folder path associated with this smoke job.",
    )
    source_kind: str = Field(
        default="synthetic_profile",
        description="Trace label for how this payload was produced, such as synthetic_profile or live_ixp.",
    )
    source_pdf: str | None = Field(
        default=None,
        description="Optional source PDF path for traceability.",
    )
    ixp_document_id: str | None = Field(
        default=None,
        description="Optional live IXP document identifier.",
    )
    member_id: str | None = Field(
        default=None,
        description="Optional member identifier extracted from the correspondence.",
    )
    claim_number: str | None = Field(
        default=None,
        description="Optional claim number extracted from the correspondence.",
    )
    authorization_number: str | None = Field(
        default=None,
        description="Optional authorization number extracted from the correspondence.",
    )
    service_description: str | None = Field(
        default=None,
        description="Optional service description extracted from the correspondence.",
    )
    note_text: str | None = Field(
        default=None,
        description="Optional extracted note text or rationale summary.",
    )


class AutomationTask(BaseModel):
    system: Literal["payer_portal", "cerner", "rev_cycle"]
    action: str
    status: TaskStatus
    payload: dict[str, Any]


class GraphOutput(BaseModel):
    packet_id: str
    scenario_id: str
    document_type: str
    source_kind: str
    source_pdf: str | None
    ixp_document_id: str | None
    member_id: str | None
    claim_number: str | None
    authorization_number: str | None
    service_description: str | None
    correspondence_category: FaxCategory
    primary_route: RouteCode
    is_denial_of_service: bool
    payer_auth_problem: bool
    missing_information: bool
    needs_human_review: bool
    payer_portal_action: PortalAction
    cerner_action: str
    rev_cycle_action: str
    action_summary: str
    tasks: list[AutomationTask]
    execution_status: ExecutionStatus
    execution_detail: str
    sleep_applied_seconds: int
    timestamp_utc: str


REVIEW_CONFIDENCE_THRESHOLD = 0.90

GraphInput.model_rebuild()
AutomationTask.model_rebuild()
GraphOutput.model_rebuild()


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _needs_human_review(payload: GraphInput) -> bool:
    return (
        payload.classification_confidence < REVIEW_CONFIDENCE_THRESHOLD
        or payload.extraction_confidence < REVIEW_CONFIDENCE_THRESHOLD
        or payload.fax_category == "other"
    )


def _resolve_route(payload: GraphInput, needs_human_review: bool) -> tuple[RouteCode, PortalAction, str, str]:
    portal_action = payload.payer_portal_action

    if needs_human_review:
        return ("manual_triage", portal_action, "none", "create_manual_triage")

    if payload.payer_auth_problem or (
        payload.target_record_type == "authorization"
        and payload.decision_status in {"approved", "partially_approved"}
    ):
        if portal_action == "none":
            portal_action = "confirm_auth"
        return (
            "cerner_auth_update",
            portal_action,
            "update_authorization_record",
            "none",
        )

    if payload.missing_information or payload.decision_status in {"pended", "information_requested"}:
        if portal_action == "none":
            portal_action = "submit_missing_docs"
        return (
            "payer_portal_follow_up",
            portal_action,
            "log_patient_account_note",
            "none",
        )

    if payload.is_denial_of_service or payload.decision_status in {"denied", "appeal_received"}:
        if portal_action == "none":
            portal_action = "start_appeal"
        return (
            "rev_cycle_denial_queue",
            portal_action,
            "update_patient_account",
            "create_denial_work_item",
        )

    if payload.decision_status in {"paid", "overturned"} or payload.target_record_type == "patient_account":
        if portal_action == "none":
            portal_action = "check_claim_status"
        return (
            "cerner_patient_account_update",
            portal_action,
            "update_patient_account",
            "none",
        )

    return ("manual_triage", portal_action, "none", "create_manual_triage")


def _build_tasks(
    payload: GraphInput,
    *,
    payer_portal_action: PortalAction,
    cerner_action: str,
    rev_cycle_action: str,
    task_status: TaskStatus,
) -> list[AutomationTask]:
    tasks: list[AutomationTask] = []
    context_payload = {
        "member_id": payload.member_id,
        "claim_number": payload.claim_number,
        "authorization_number": payload.authorization_number,
        "service_description": payload.service_description,
        "note_text": payload.note_text,
        "source_kind": payload.source_kind,
        "source_pdf": payload.source_pdf,
        "ixp_document_id": payload.ixp_document_id,
    }

    tasks.append(
        AutomationTask(
            system="payer_portal",
            action=payer_portal_action,
            status="not_needed" if payer_portal_action == "none" else task_status,
            payload={
                "packet_id": payload.packet_id,
                "scenario_id": payload.scenario_id,
                "document_type": payload.document_type,
                "portal_action": payer_portal_action,
                "shared_folder_path": payload.shared_folder_path,
                **context_payload,
            },
        )
    )
    tasks.append(
        AutomationTask(
            system="cerner",
            action=cerner_action,
            status="not_needed" if cerner_action == "none" else task_status,
            payload={
                "packet_id": payload.packet_id,
                "scenario_id": payload.scenario_id,
                "target_record_type": payload.target_record_type,
                "cerner_action": cerner_action,
                **context_payload,
            },
        )
    )
    tasks.append(
        AutomationTask(
            system="rev_cycle",
            action=rev_cycle_action,
            status="not_needed" if rev_cycle_action == "none" else task_status,
            payload={
                "packet_id": payload.packet_id,
                "scenario_id": payload.scenario_id,
                "queue_name": payload.rev_cycle_queue,
                "rev_cycle_action": rev_cycle_action,
                **context_payload,
            },
        )
    )
    return tasks


def _action_summary(
    route: RouteCode,
    *,
    payer_portal_action: PortalAction,
    cerner_action: str,
    rev_cycle_action: str,
    needs_human_review: bool,
) -> str:
    summary = (
        f"Primary route: {route}. "
        f"Payer portal: {payer_portal_action}. "
        f"Cerner: {cerner_action}. "
        f"Rev cycle: {rev_cycle_action}."
    )
    if needs_human_review:
        return summary + " Human review required because the extraction confidence gate did not pass."
    return summary


def main(input: GraphInput | dict[str, Any]) -> GraphOutput:
    payload = input if isinstance(input, GraphInput) else GraphInput.model_validate(input)
    needs_human_review = _needs_human_review(payload)
    route, payer_portal_action, cerner_action, rev_cycle_action = _resolve_route(
        payload,
        needs_human_review,
    )

    sleep_applied_seconds = payload.delay_seconds if payload.execute_live_follow_up else 0
    if sleep_applied_seconds > 0:
        time.sleep(sleep_applied_seconds)

    execution_status: ExecutionStatus
    execution_detail: str
    task_status: TaskStatus
    if needs_human_review:
        execution_status = "skipped"
        execution_detail = (
            "Confidence gate did not pass, so the smoke agent returned a manual-triage plan only."
        )
        task_status = "planned"
    elif payload.execute_live_follow_up:
        execution_status = "executed"
        execution_detail = (
            "Dummy downstream automations were simulated in-process "
            f"for {sleep_applied_seconds}s."
        )
        task_status = "executed"
    else:
        execution_status = "planned"
        execution_detail = (
            "Plan only. Set execute_live_follow_up=true to keep the Shared-folder job visible "
            "while the dummy downstream actions simulate."
        )
        task_status = "planned"

    tasks = _build_tasks(
        payload,
        payer_portal_action=payer_portal_action,
        cerner_action=cerner_action,
        rev_cycle_action=rev_cycle_action,
        task_status=task_status,
    )

    output = GraphOutput(
        packet_id=payload.packet_id,
        scenario_id=payload.scenario_id,
        document_type=payload.document_type,
        source_kind=payload.source_kind,
        source_pdf=payload.source_pdf,
        ixp_document_id=payload.ixp_document_id,
        member_id=payload.member_id,
        claim_number=payload.claim_number,
        authorization_number=payload.authorization_number,
        service_description=payload.service_description,
        correspondence_category=payload.fax_category,
        primary_route=route,
        is_denial_of_service=payload.is_denial_of_service,
        payer_auth_problem=payload.payer_auth_problem,
        missing_information=payload.missing_information,
        needs_human_review=needs_human_review,
        payer_portal_action=payer_portal_action,
        cerner_action=cerner_action,
        rev_cycle_action=rev_cycle_action,
        action_summary=_action_summary(
            route,
            payer_portal_action=payer_portal_action,
            cerner_action=cerner_action,
            rev_cycle_action=rev_cycle_action,
            needs_human_review=needs_human_review,
        ),
        tasks=tasks,
        execution_status=execution_status,
        execution_detail=execution_detail,
        sleep_applied_seconds=sleep_applied_seconds,
        timestamp_utc=_iso_utc(_now_utc()),
    )

    print(
        json.dumps(
            {
                "marker": "shared_kswic_correspondence_smoke_agent",
                "packet_id": output.packet_id,
                "scenario_id": output.scenario_id,
                "source_kind": output.source_kind,
                "primary_route": output.primary_route,
                "needs_human_review": output.needs_human_review,
                "execution_status": output.execution_status,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return output
