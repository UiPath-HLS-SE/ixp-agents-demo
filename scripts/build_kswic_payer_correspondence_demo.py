#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "demo_resources" / "kswic-payer-correspondence-demo"
PACKET_ROOT = OUTPUT_ROOT / "generated_packets"
MAESTRO_ROOT = OUTPUT_ROOT / "maestro"
AUTOMATION_ROOT = OUTPUT_ROOT / "automation_stubs"
SYNTHETIC_ROOT = REPO_ROOT.parent / "synthetic-record-generator" / "SyntheticRecordGenerator"

if not SYNTHETIC_ROOT.exists():
    raise SystemExit(
        "Synthetic record generator helpers are missing. Expected sibling directory at "
        f"{SYNTHETIC_ROOT}"
    )

sys.path.insert(0, str(SYNTHETIC_ROOT))

from generate_synthetic_patient_pdf import (  # noqa: E402
    Canvas,
    MARGIN,
    PAGE_H,
    PAGE_W,
    PDFDocument,
    draw_kv_grid,
    draw_section_header,
    draw_signature_block,
    draw_table,
    fit_text_to_width,
)


def currency(value: float | None) -> str:
    if value is None:
        return "-"
    return f"${value:,.2f}"


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def confidence_for(field_name: str, value: Any) -> float:
    if value in (None, "", []):
        return 0.0
    high = {
        "document_type",
        "document_family",
        "payer_name",
        "member_name",
        "member_id",
        "claim_number",
        "authorization_number",
        "decision_status",
    }
    medium = {
        "reason_text",
        "service_description",
        "documents_requested",
        "next_steps",
    }
    if field_name in high:
        return 0.98
    if field_name in medium:
        return 0.92
    return 0.95


SCENARIOS: list[dict[str, Any]] = [
    {
        "scenario_id": "SCN-001",
        "document_type": "Prior Authorization Approval Letter",
        "document_family": "prior_auth",
        "sender_name": "Prairie Horizon Health Plan",
        "sender_address": "4800 East Meadow Park Drive, Topeka, KS 66607",
        "sender_phone": "(800) 555-2101",
        "sender_fax": "(800) 555-2102",
        "recipient_name": "Kansas Sunflower Women's Imaging Center",
        "recipient_role": "Provider",
        "recipient_address": "1777 North Prairie View Blvd, Wichita, KS 67203",
        "line_of_business": "Commercial PPO",
        "clinical_area": "Advanced Imaging",
        "summary": "Approval for CT abdomen/pelvis with contrast requested by KSWIC imaging scheduling.",
        "channel": "fax",
        "member_name": "Avery Sutton",
        "member_id": "PHH-484920-01",
        "member_dob": "1988-04-17",
        "provider_name": "Kansas Sunflower Women's Imaging Center",
        "provider_npi": "1881357012",
        "ordering_provider": "Dr. Lena Ortiz",
        "policy_or_group_id": "KS-77014",
        "claim_number": "",
        "authorization_number": "PA-884201",
        "service_description": "CT abdomen/pelvis with contrast",
        "requested_units": "1",
        "approved_units": "1",
        "dates": {
            "request_received": "2026-02-04",
            "decision_date": "2026-02-06",
            "service_date": "2026-02-12",
            "authorization_start": "2026-02-07",
            "authorization_end": "2026-03-07",
            "response_deadline": "",
        },
        "decision_status": "approved",
        "reason_category": "medical_necessity_met",
        "reason_codes": ["MED-NEC-APP"],
        "reason_text": "Submitted records support medical necessity under imaging guidelines.",
        "financials": {
            "billed_amount": None,
            "allowed_amount": None,
            "plan_paid": None,
            "member_responsibility": None,
        },
        "documents_requested": [],
        "next_steps": [
            "Update the Cerner authorization record with the approved authorization number and validity window.",
            "Release the imaging visit from the auth workqueue once the scheduled service date is confirmed.",
        ],
    },
    {
        "scenario_id": "SCN-003",
        "document_type": "Prior Authorization Denial Letter",
        "document_family": "prior_auth",
        "sender_name": "Flint Hills CareNet",
        "sender_address": "300 Meridian Center, Hutchinson, KS 67501",
        "sender_phone": "(866) 555-3101",
        "sender_fax": "(866) 555-3104",
        "recipient_name": "Kansas Sunflower Women's Imaging Center",
        "recipient_role": "Provider",
        "recipient_address": "1777 North Prairie View Blvd, Wichita, KS 67203",
        "line_of_business": "Commercial HMO",
        "clinical_area": "Sleep Medicine",
        "summary": "Denied in-lab sleep study; home sleep test recommended first.",
        "channel": "fax",
        "member_name": "Mila Hart",
        "member_id": "FHC-228174-02",
        "member_dob": "1979-11-08",
        "provider_name": "Kansas Sunflower Women's Imaging Center",
        "provider_npi": "1881357012",
        "ordering_provider": "Dr. Naomi Beck",
        "policy_or_group_id": "FHC-99120",
        "claim_number": "",
        "authorization_number": "PA-118943",
        "service_description": "In-lab polysomnography",
        "requested_units": "1",
        "approved_units": "0",
        "dates": {
            "request_received": "2026-02-14",
            "decision_date": "2026-02-16",
            "service_date": "2026-02-24",
            "authorization_start": "",
            "authorization_end": "",
            "response_deadline": "2026-02-26",
        },
        "decision_status": "denied",
        "reason_category": "medical_necessity_not_met",
        "reason_codes": ["UM-102", "ALT-CARE-01"],
        "reason_text": "Clinical criteria for in-lab polysomnography were not met and a home sleep test must be completed first.",
        "financials": {
            "billed_amount": None,
            "allowed_amount": None,
            "plan_paid": None,
            "member_responsibility": None,
        },
        "documents_requested": [],
        "next_steps": [
            "Create an auth follow-up task in Cerner and route the case to the KSWIC authorization team.",
            "Use the payer portal to confirm peer-to-peer and reconsideration deadlines before the sleep study date.",
        ],
    },
    {
        "scenario_id": "SCN-004",
        "document_type": "Claim Denial Letter",
        "document_family": "claims",
        "sender_name": "North Plains Select",
        "sender_address": "901 Oak Harbor Row, Omaha, NE 68114",
        "sender_phone": "(877) 555-4401",
        "sender_fax": "(877) 555-4408",
        "recipient_name": "KSWIC Revenue Cycle Billing Office",
        "recipient_role": "Provider Billing Office",
        "recipient_address": "1777 North Prairie View Blvd, Wichita, KS 67203",
        "line_of_business": "Commercial PPO",
        "clinical_area": "Durable Medical Equipment",
        "summary": "Claim denied for powered wheelchair due to insufficient supporting documentation.",
        "channel": "fax",
        "member_name": "Jordan Pike",
        "member_id": "NPS-332845-01",
        "member_dob": "1967-07-30",
        "provider_name": "KSWIC Revenue Cycle Billing Office",
        "provider_npi": "1457965210",
        "ordering_provider": "Dr. Reese Barlow",
        "policy_or_group_id": "NPS-12040",
        "claim_number": "CLM-5521907",
        "authorization_number": "",
        "service_description": "Powered wheelchair, HCPCS K0823",
        "requested_units": "1",
        "approved_units": "0",
        "dates": {
            "request_received": "",
            "decision_date": "2026-02-19",
            "service_date": "2026-01-22",
            "authorization_start": "",
            "authorization_end": "",
            "response_deadline": "2026-03-20",
        },
        "decision_status": "denied",
        "reason_category": "medical_necessity_not_met",
        "reason_codes": ["CO-50", "N290"],
        "reason_text": "The service was denied because records received did not establish medical necessity for a powered wheelchair.",
        "financials": {
            "billed_amount": 4280.00,
            "allowed_amount": 0.00,
            "plan_paid": 0.00,
            "member_responsibility": 0.00,
        },
        "documents_requested": [
            "Face-to-face mobility evaluation",
            "Physical therapy functional assessment",
            "Detailed written order",
        ],
        "next_steps": [
            "Open a denial case in the rev cycle system and add a patient-account note in Cerner.",
            "Prepare a portal reconsideration package with the missing clinical support if the account remains collectible.",
        ],
    },
    {
        "scenario_id": "SCN-005",
        "document_type": "Request for Additional Information",
        "document_family": "claims",
        "sender_name": "Sun Prairie Medicaid Advantage",
        "sender_address": "88 Capitol Trace, Jefferson City, MO 65101",
        "sender_phone": "(844) 555-5100",
        "sender_fax": "(844) 555-5105",
        "recipient_name": "KSWIC Revenue Cycle Billing Office",
        "recipient_role": "Provider Billing Office",
        "recipient_address": "1777 North Prairie View Blvd, Wichita, KS 67203",
        "line_of_business": "Managed Medicaid",
        "clinical_area": "Outpatient Surgery",
        "summary": "Claim pended due to missing operative report and itemized bill.",
        "channel": "fax",
        "member_name": "Darius Wynn",
        "member_id": "SPM-775114-05",
        "member_dob": "1991-12-14",
        "provider_name": "KSWIC Revenue Cycle Billing Office",
        "provider_npi": "1457965210",
        "ordering_provider": "Dr. Tessa Lin",
        "policy_or_group_id": "SPM-22041",
        "claim_number": "CLM-8100241",
        "authorization_number": "",
        "service_description": "Outpatient surgery facility claim",
        "requested_units": "",
        "approved_units": "",
        "dates": {
            "request_received": "",
            "decision_date": "2026-02-21",
            "service_date": "2026-02-03",
            "authorization_start": "",
            "authorization_end": "",
            "response_deadline": "2026-03-08",
        },
        "decision_status": "pended",
        "reason_category": "missing_information",
        "reason_codes": ["PEND-DOCS-14"],
        "reason_text": "Additional documentation is required to complete adjudication of the outpatient surgery claim.",
        "financials": {
            "billed_amount": 7325.88,
            "allowed_amount": None,
            "plan_paid": None,
            "member_responsibility": None,
        },
        "documents_requested": ["Operative report", "Itemized bill", "Implant log"],
        "next_steps": [
            "Create a patient-account follow-up in Cerner so the chart and billing packet can be assembled.",
            "Upload the requested documents through the payer portal before the submission deadline.",
        ],
    },
    {
        "scenario_id": "SCN-006",
        "document_type": "Appeal Receipt Acknowledgment",
        "document_family": "appeal",
        "sender_name": "Prairie Horizon Health Plan",
        "sender_address": "4800 East Meadow Park Drive, Topeka, KS 66607",
        "sender_phone": "(800) 555-2101",
        "sender_fax": "(800) 555-2102",
        "recipient_name": "KSWIC Appeals Desk",
        "recipient_role": "Provider",
        "recipient_address": "1777 North Prairie View Blvd, Wichita, KS 67203",
        "line_of_business": "Commercial EPO",
        "clinical_area": "Infusion Therapy",
        "summary": "Acknowledgment of first-level appeal for a denied infusion therapy claim.",
        "channel": "fax",
        "member_name": "Paige Dorsey",
        "member_id": "PHH-664200-01",
        "member_dob": "1984-03-09",
        "provider_name": "KSWIC Appeals Desk",
        "provider_npi": "1457965210",
        "ordering_provider": "Dr. Aaron Pike",
        "policy_or_group_id": "KS-81220",
        "claim_number": "CLM-6005121",
        "authorization_number": "",
        "service_description": "Infusion therapy appeal acknowledgment",
        "requested_units": "",
        "approved_units": "",
        "dates": {
            "request_received": "2026-02-18",
            "decision_date": "2026-02-22",
            "service_date": "2026-01-14",
            "authorization_start": "",
            "authorization_end": "",
            "response_deadline": "2026-03-24",
        },
        "decision_status": "appeal_received",
        "reason_category": "appeal_tracking",
        "reason_codes": ["APP-RCVD-01"],
        "reason_text": "The first-level appeal was accepted for review and a standard determination is expected within 30 calendar days.",
        "financials": {
            "billed_amount": 1865.42,
            "allowed_amount": 0.00,
            "plan_paid": 0.00,
            "member_responsibility": 0.00,
        },
        "documents_requested": [],
        "next_steps": [
            "Update the appeal tracker in the rev cycle system and record the appeal case number.",
            "Hold outbound payer follow-up unless the expected decision timeframe is missed.",
        ],
    },
    {
        "scenario_id": "SCN-007",
        "document_type": "Appeal Determination Overturn Letter",
        "document_family": "appeal",
        "sender_name": "Sun Prairie Medicare Advantage",
        "sender_address": "88 Capitol Trace, Jefferson City, MO 65101",
        "sender_phone": "(844) 555-5100",
        "sender_fax": "(844) 555-5105",
        "recipient_name": "KSWIC Appeals Desk",
        "recipient_role": "Provider",
        "recipient_address": "1777 North Prairie View Blvd, Wichita, KS 67203",
        "line_of_business": "Medicare Advantage",
        "clinical_area": "Specialty Imaging",
        "summary": "Initial denial overturned after review of specialist notes.",
        "channel": "fax",
        "member_name": "Eliana Brooks",
        "member_id": "SPM-109448-02",
        "member_dob": "1958-05-27",
        "provider_name": "KSWIC Appeals Desk",
        "provider_npi": "1457965210",
        "ordering_provider": "Dr. Nate Fulton",
        "policy_or_group_id": "SPM-60519",
        "claim_number": "CLM-4400192",
        "authorization_number": "PA-4400192A",
        "service_description": "Appeal overturn for specialist imaging request",
        "requested_units": "1",
        "approved_units": "1",
        "dates": {
            "request_received": "2026-02-01",
            "decision_date": "2026-02-24",
            "service_date": "2026-01-10",
            "authorization_start": "2026-02-24",
            "authorization_end": "2026-03-31",
            "response_deadline": "",
        },
        "decision_status": "overturned",
        "reason_category": "medical_necessity_met_on_appeal",
        "reason_codes": ["OVT-APP-02"],
        "reason_text": "Additional specialist documentation demonstrated medical necessity and the prior denial was reversed.",
        "financials": {
            "billed_amount": 1865.42,
            "allowed_amount": 1865.42,
            "plan_paid": 1678.88,
            "member_responsibility": 186.54,
        },
        "documents_requested": [],
        "next_steps": [
            "Update the rev cycle appeal tracker to closed-overturned and note that reprocessing is expected.",
            "If the authorization is required downstream, update the Cerner authorization record with the reinstated decision.",
        ],
    },
    {
        "scenario_id": "SCN-009",
        "document_type": "Explanation of Benefits",
        "document_family": "claims",
        "sender_name": "North Plains Select",
        "sender_address": "901 Oak Harbor Row, Omaha, NE 68114",
        "sender_phone": "(877) 555-4401",
        "sender_fax": "(877) 555-4408",
        "recipient_name": "Member and provider copy",
        "recipient_role": "Member",
        "recipient_address": "Wichita, KS 67203",
        "line_of_business": "Commercial PPO",
        "clinical_area": "Office Visit and Labs",
        "summary": "Paid office visit and lab panel with deductible and coinsurance applied.",
        "channel": "portal_notice",
        "member_name": "Riley Mercer",
        "member_id": "NPS-118290-01",
        "member_dob": "1995-09-21",
        "provider_name": "Kansas Sunflower Women's Imaging Center",
        "provider_npi": "1881357012",
        "ordering_provider": "Dr. Maya Voss",
        "policy_or_group_id": "NPS-42117",
        "claim_number": "CLM-7224508",
        "authorization_number": "",
        "service_description": "Office visit and lab panel",
        "requested_units": "",
        "approved_units": "",
        "dates": {
            "request_received": "",
            "decision_date": "2026-02-25",
            "service_date": "2026-02-04",
            "authorization_start": "",
            "authorization_end": "",
            "response_deadline": "",
        },
        "decision_status": "paid",
        "reason_category": "claim_paid",
        "reason_codes": ["PAID"],
        "reason_text": "Claim processed per plan benefits with deductible and coinsurance applied.",
        "financials": {
            "billed_amount": 640.00,
            "allowed_amount": 425.00,
            "plan_paid": 297.50,
            "member_responsibility": 127.50,
        },
        "documents_requested": [],
        "next_steps": [
            "Add a patient-account note in Cerner if the EOB needs to be reconciled against the claim balance.",
            "No payer-portal follow-up is required unless the remittance and EOB disagree.",
        ],
    },
    {
        "scenario_id": "SCN-010",
        "document_type": "Coordination of Benefits Questionnaire Letter",
        "document_family": "member_admin",
        "sender_name": "Prairie Horizon Health Plan",
        "sender_address": "4800 East Meadow Park Drive, Topeka, KS 66607",
        "sender_phone": "(800) 555-2101",
        "sender_fax": "(800) 555-2102",
        "recipient_name": "Member and provider copy",
        "recipient_role": "Member",
        "recipient_address": "Wichita, KS 67203",
        "line_of_business": "Commercial PPO",
        "clinical_area": "Coordination of Benefits",
        "summary": "Request to verify whether the member has other active insurance coverage.",
        "channel": "fax",
        "member_name": "Cameron Vale",
        "member_id": "PHH-551002-03",
        "member_dob": "1974-01-04",
        "provider_name": "Kansas Sunflower Women's Imaging Center",
        "provider_npi": "1881357012",
        "ordering_provider": "Dr. Nia Walsh",
        "policy_or_group_id": "KS-33207",
        "claim_number": "CLM-8892014",
        "authorization_number": "",
        "service_description": "COB verification request",
        "requested_units": "",
        "approved_units": "",
        "dates": {
            "request_received": "",
            "decision_date": "2026-02-26",
            "service_date": "2026-02-02",
            "authorization_start": "",
            "authorization_end": "",
            "response_deadline": "2026-03-18",
        },
        "decision_status": "information_requested",
        "reason_category": "cob_verification",
        "reason_codes": ["COB-PEND-11"],
        "reason_text": "Claim processing is delayed pending verification of other active insurance coverage.",
        "financials": {
            "billed_amount": 920.00,
            "allowed_amount": None,
            "plan_paid": None,
            "member_responsibility": None,
        },
        "documents_requested": ["Completed COB questionnaire", "Proof of active or inactive secondary coverage"],
        "next_steps": [
            "Add a coverage follow-up note to the patient account in Cerner so front office or billing staff can obtain the response.",
            "If the patient returns updated insurance information, submit the COB update through the payer portal.",
        ],
    },
    {
        "scenario_id": "SCN-011",
        "document_type": "Overpayment Recovery Notice",
        "document_family": "payment_integrity",
        "sender_name": "Sun Prairie Medicaid Advantage",
        "sender_address": "88 Capitol Trace, Jefferson City, MO 65101",
        "sender_phone": "(844) 555-5100",
        "sender_fax": "(844) 555-5105",
        "recipient_name": "KSWIC Revenue Cycle Billing Office",
        "recipient_role": "Provider Billing Office",
        "recipient_address": "1777 North Prairie View Blvd, Wichita, KS 67203",
        "line_of_business": "Managed Medicaid",
        "clinical_area": "Payment Integrity",
        "summary": "Recovery initiated for duplicate payment on outpatient claim.",
        "channel": "fax",
        "member_name": "Hayden Cole",
        "member_id": "SPM-402884-08",
        "member_dob": "1982-08-18",
        "provider_name": "KSWIC Revenue Cycle Billing Office",
        "provider_npi": "1457965210",
        "ordering_provider": "Dr. Elise Monroe",
        "policy_or_group_id": "SPM-70218",
        "claim_number": "CLM-1045507",
        "authorization_number": "",
        "service_description": "Duplicate outpatient payment recovery",
        "requested_units": "",
        "approved_units": "",
        "dates": {
            "request_received": "",
            "decision_date": "2026-02-28",
            "service_date": "2026-01-11",
            "authorization_start": "",
            "authorization_end": "",
            "response_deadline": "2026-03-30",
        },
        "decision_status": "recoupment",
        "reason_category": "duplicate_payment",
        "reason_codes": ["RC-202", "DUP-PMT"],
        "reason_text": "Duplicate reimbursement was identified during post-payment review and recovery will occur through offset.",
        "financials": {
            "billed_amount": 912.33,
            "allowed_amount": 912.33,
            "plan_paid": 912.33,
            "member_responsibility": 0.00,
        },
        "documents_requested": ["Remittance advice copy", "Posting audit trail if disputing"],
        "next_steps": [
            "Create a recoupment work item in the rev cycle system and note the impending offset date.",
            "Add a Cerner patient-account note only if the recovery affects open A/R or collection logic.",
        ],
    },
    {
        "scenario_id": "SCN-014",
        "document_type": "Pharmacy Exception Denial",
        "document_family": "pharmacy",
        "sender_name": "HeartlandRx Benefit Services",
        "sender_address": "2202 Cedar Exchange, Tulsa, OK 74103",
        "sender_phone": "(855) 555-1400",
        "sender_fax": "(855) 555-1406",
        "recipient_name": "Kansas Sunflower Women's Imaging Center",
        "recipient_role": "Prescriber and provider copy",
        "recipient_address": "1777 North Prairie View Blvd, Wichita, KS 67203",
        "line_of_business": "PBM / Pharmacy Benefit",
        "clinical_area": "Rheumatology",
        "summary": "Requested biologic denied pending trial of preferred formulary alternative.",
        "channel": "fax",
        "member_name": "Sasha Glenn",
        "member_id": "HRX-901114-01",
        "member_dob": "1990-06-11",
        "provider_name": "Kansas Sunflower Women's Imaging Center",
        "provider_npi": "1881357012",
        "ordering_provider": "Dr. Priya Shah",
        "policy_or_group_id": "HRX-61122",
        "claim_number": "",
        "authorization_number": "RX-PA-661921",
        "service_description": "Biologic formulary exception request",
        "requested_units": "30-day supply",
        "approved_units": "0",
        "dates": {
            "request_received": "2026-02-20",
            "decision_date": "2026-03-01",
            "service_date": "2026-03-03",
            "authorization_start": "",
            "authorization_end": "",
            "response_deadline": "2026-03-15",
        },
        "decision_status": "denied",
        "reason_category": "step_therapy",
        "reason_codes": ["RX-STEP-17"],
        "reason_text": "Formulary exception criteria were not met because the preferred step-therapy alternatives have not been trialed.",
        "financials": {
            "billed_amount": None,
            "allowed_amount": None,
            "plan_paid": None,
            "member_responsibility": None,
        },
        "documents_requested": ["Trial-and-failure history", "Prescriber clinical rationale"],
        "next_steps": [
            "Create a Cerner auth workqueue item for pharmacy follow-up and attach the preferred-alternative list.",
            "Use the payer portal to submit additional step-therapy documentation or a formulary-exception appeal.",
        ],
    },
]

IXP_FIELDS: list[dict[str, str]] = [
    {"name": "document_type", "group": "classification", "type": "choice"},
    {"name": "document_family", "group": "classification", "type": "choice"},
    {"name": "line_of_business", "group": "classification", "type": "text"},
    {"name": "payer_name", "group": "sender_recipient", "type": "text"},
    {"name": "recipient_name", "group": "sender_recipient", "type": "text"},
    {"name": "member_name", "group": "member", "type": "text"},
    {"name": "member_id", "group": "member", "type": "text"},
    {"name": "member_dob", "group": "member", "type": "date"},
    {"name": "provider_name", "group": "provider", "type": "text"},
    {"name": "provider_npi", "group": "provider", "type": "text"},
    {"name": "claim_number", "group": "financial", "type": "text"},
    {"name": "authorization_number", "group": "authorization", "type": "text"},
    {"name": "policy_or_group_id", "group": "member", "type": "text"},
    {"name": "service_description", "group": "service", "type": "text"},
    {"name": "decision_status", "group": "decision", "type": "choice"},
    {"name": "reason_category", "group": "decision", "type": "choice"},
    {"name": "reason_codes", "group": "decision", "type": "list"},
    {"name": "reason_text", "group": "decision", "type": "text"},
    {"name": "request_received", "group": "dates", "type": "date"},
    {"name": "decision_date", "group": "dates", "type": "date"},
    {"name": "service_date", "group": "dates", "type": "date"},
    {"name": "authorization_start", "group": "dates", "type": "date"},
    {"name": "authorization_end", "group": "dates", "type": "date"},
    {"name": "response_deadline", "group": "dates", "type": "date"},
    {"name": "requested_units", "group": "service", "type": "text"},
    {"name": "approved_units", "group": "service", "type": "text"},
    {"name": "billed_amount", "group": "financial", "type": "currency"},
    {"name": "allowed_amount", "group": "financial", "type": "currency"},
    {"name": "plan_paid", "group": "financial", "type": "currency"},
    {"name": "member_responsibility", "group": "financial", "type": "currency"},
    {"name": "documents_requested", "group": "follow_up", "type": "list"},
]

AUTOMATION_STUBS: list[dict[str, Any]] = [
    {
        "automation_id": "dummy_payer_portal_follow_up",
        "display_name": "Dummy - Payer Portal Follow Up",
        "system": "Synthetic payer portal",
        "supported_actions": [
            "check_status",
            "upload_missing_documents",
            "submit_reconsideration",
            "submit_cob_update",
            "request_recoupment_detail",
        ],
        "required_inputs": [
            "document_id",
            "member_id",
            "payer_name",
            "claim_number",
            "authorization_number",
            "action",
        ],
        "outputs": [
            "portal_reference_number",
            "portal_status",
            "submitted_at",
            "notes",
        ],
    },
    {
        "automation_id": "dummy_cerner_auth_update",
        "display_name": "Dummy - Cerner Auth Record Update",
        "system": "Synthetic Cerner",
        "supported_actions": [
            "create_or_update_auth_record",
            "route_to_auth_workqueue",
            "close_auth_follow_up",
        ],
        "required_inputs": [
            "document_id",
            "member_id",
            "authorization_number",
            "decision_status",
            "service_description",
        ],
        "outputs": [
            "cerner_auth_record_id",
            "workqueue_name",
            "update_status",
        ],
    },
    {
        "automation_id": "dummy_cerner_patient_account_update",
        "display_name": "Dummy - Cerner Patient Account Note",
        "system": "Synthetic Cerner",
        "supported_actions": [
            "add_patient_account_note",
            "add_coverage_follow_up",
            "post_payment_summary",
            "note_denial_reversal",
        ],
        "required_inputs": [
            "document_id",
            "member_id",
            "claim_number",
            "decision_status",
            "note_text",
        ],
        "outputs": [
            "patient_account_reference",
            "note_id",
            "update_status",
        ],
    },
    {
        "automation_id": "dummy_rev_cycle_work_item",
        "display_name": "Dummy - Rev Cycle Work Item",
        "system": "Synthetic rev cycle platform",
        "supported_actions": [
            "create_denial_case",
            "update_appeal_tracker",
            "create_recoupment_case",
        ],
        "required_inputs": [
            "document_id",
            "claim_number",
            "decision_status",
            "priority",
            "owner_queue",
            "action",
        ],
        "outputs": [
            "work_item_id",
            "owner_queue",
            "status",
            "notes",
        ],
    },
]


def header(c: Canvas, scenario: dict[str, Any], title: str, page_num: int, total_pages: int) -> None:
    c.set_fill(0.94, 0.95, 0.96)
    c.rect(MARGIN, PAGE_H - 74, PAGE_W - 2 * MARGIN, 54, fill=True, stroke=False)
    c.set_stroke(0.18, 0.18, 0.18)
    c.set_line_width(1)
    c.rect(MARGIN, PAGE_H - 74, PAGE_W - 2 * MARGIN, 54, fill=False, stroke=True)
    sender = fit_text_to_width(c, str(scenario["sender_name"]).upper(), PAGE_W - 260, size=12, font="F2")
    c.text(MARGIN + 10, PAGE_H - 38, sender, font="F2", size=12, color=(0.08, 0.08, 0.08))
    c.text(MARGIN + 10, PAGE_H - 56, fit_text_to_width(c, title, PAGE_W - 260, size=10, font="F2"), font="F2", size=10, color=(0.08, 0.08, 0.08))
    c.text(PAGE_W - MARGIN - 86, PAGE_H - 38, f"Page {page_num}/{total_pages}", font="F2", size=9, color=(0.08, 0.08, 0.08))
    c.text(PAGE_W - MARGIN - 132, PAGE_H - 56, str(scenario["scenario_id"]), font="F1", size=8.5, color=(0.18, 0.18, 0.18))

    c.set_fill(0.96, 0.96, 0.96)
    c.rect(0, 0, PAGE_W, 22, fill=True, stroke=False)
    c.set_stroke(0.2, 0.2, 0.2)
    c.line(0, 22, PAGE_W, 22)
    c.text(
        MARGIN,
        7,
        "Synthetic payer correspondence for KSWIC demo only. All names, IDs, addresses, and numbers are fictional.",
        font="F2",
        size=7.2,
        color=(0.08, 0.08, 0.08),
    )


def paragraph(c: Canvas, x: float, y_top: float, text: str, max_width: float, *, size: float = 8.5, leading: float = 10.8) -> float:
    return c.wrapped_text(
        x,
        y_top,
        text,
        max_width=max_width,
        leading=leading,
        font="F1",
        size=size,
        color=(0.08, 0.08, 0.08),
    )


def bullet_list(c: Canvas, x: float, y_top: float, lines: list[str], max_width: float) -> float:
    y = y_top
    for line in lines:
        y = c.wrapped_text(
            x,
            y,
            line,
            max_width=max_width,
            leading=10.6,
            font="F1",
            size=8.3,
            color=(0.08, 0.08, 0.08),
            bullet=True,
        )
        y -= 1
    return y


def build_text_packet(scenario: dict[str, Any]) -> str:
    dates = scenario["dates"]
    financials = scenario["financials"]
    lines = [
        f"{scenario['document_type']}",
        f"Scenario ID: {scenario['scenario_id']}",
        f"Sender: {scenario['sender_name']}",
        f"Recipient: {scenario['recipient_name']}",
        f"Member: {scenario['member_name']} ({scenario['member_id']})",
        f"Member DOB: {scenario['member_dob']}",
        f"Provider: {scenario['provider_name']} ({scenario['provider_npi']})",
        f"Claim Number: {scenario['claim_number'] or 'N/A'}",
        f"Authorization Number: {scenario['authorization_number'] or 'N/A'}",
        f"Line Of Business: {scenario['line_of_business']}",
        f"Clinical Area: {scenario['clinical_area']}",
        f"Decision Status: {scenario['decision_status']}",
        f"Reason Category: {scenario['reason_category']}",
        f"Reason Codes: {', '.join(scenario['reason_codes'])}",
        f"Reason Text: {scenario['reason_text']}",
        f"Request Received: {dates['request_received'] or 'N/A'}",
        f"Decision Date: {dates['decision_date'] or 'N/A'}",
        f"Service Date: {dates['service_date'] or 'N/A'}",
        f"Authorization Window: {(dates['authorization_start'] or 'N/A')} to {(dates['authorization_end'] or 'N/A')}",
        f"Response Deadline: {dates['response_deadline'] or 'N/A'}",
        f"Summary: {scenario['summary']}",
        f"Service Description: {scenario['service_description']}",
        f"Requested Units: {scenario['requested_units'] or 'N/A'}",
        f"Approved Units: {scenario['approved_units'] or 'N/A'}",
        f"Billed Amount: {currency(financials['billed_amount'])}",
        f"Allowed Amount: {currency(financials['allowed_amount'])}",
        f"Plan Paid: {currency(financials['plan_paid'])}",
        f"Member Responsibility: {currency(financials['member_responsibility'])}",
        "Documents Requested: " + (", ".join(scenario["documents_requested"]) if scenario["documents_requested"] else "None"),
        "Next Steps:",
    ]
    lines.extend(f"- {step}" for step in scenario["next_steps"])
    return "\n".join(lines) + "\n"


def render_fax_cover(doc: PDFDocument, scenario: dict[str, Any]) -> None:
    c = Canvas()
    header(c, scenario, "Inbound Payer Correspondence Fax Cover", 1, 2)
    y = PAGE_H - 96
    y = draw_section_header(c, MARGIN, y, PAGE_W - 2 * MARGIN, "Transmission Summary")
    y = draw_kv_grid(
        c,
        MARGIN,
        y,
        PAGE_W - 2 * MARGIN,
        [
            ("To", str(scenario["recipient_name"])),
            ("From", str(scenario["sender_name"])),
            ("Recipient Role", str(scenario["recipient_role"])),
            ("Channel", str(scenario["channel"])),
            ("Fax Ref", f"{slugify(str(scenario['scenario_id']))}-FAX"),
            ("Total Pages", "2"),
            ("Decision Status", str(scenario["decision_status"])),
            ("Reason Category", str(scenario["reason_category"])),
        ],
        cols=2,
        label_w=106,
    )
    y = draw_section_header(c, MARGIN, y, PAGE_W - 2 * MARGIN, "Member and Account Snapshot")
    y = draw_kv_grid(
        c,
        MARGIN,
        y,
        PAGE_W - 2 * MARGIN,
        [
            ("Member Name", str(scenario["member_name"])),
            ("Member ID", str(scenario["member_id"])),
            ("Member DOB", str(scenario["member_dob"])),
            ("Provider", str(scenario["provider_name"])),
            ("Claim Number", str(scenario["claim_number"] or "N/A")),
            ("Authorization", str(scenario["authorization_number"] or "N/A")),
            ("Policy/Group", str(scenario["policy_or_group_id"])),
            ("Clinical Area", str(scenario["clinical_area"])),
        ],
        cols=2,
        label_w=104,
    )
    y = draw_section_header(c, MARGIN, y, PAGE_W - 2 * MARGIN, "Scenario Summary")
    c.set_stroke(0.2, 0.2, 0.2)
    c.rect(MARGIN, y - 92, PAGE_W - 2 * MARGIN, 92, fill=False, stroke=True)
    y = paragraph(c, MARGIN + 8, y - 12, str(scenario["summary"]), PAGE_W - 2 * MARGIN - 16, size=9.2, leading=11.4)
    y = draw_section_header(c, MARGIN, y - 10, PAGE_W - 2 * MARGIN, "Operational Intake Notes")
    notes = [
        f"Ordering provider: {scenario['ordering_provider']}.",
        f"Requested service: {scenario['service_description']}.",
        f"Requested units: {scenario['requested_units'] or 'Not listed'}; approved units: {scenario['approved_units'] or 'Not listed'}.",
        f"Response deadline: {scenario['dates']['response_deadline'] or 'Not stated in notice'}.",
    ]
    bullet_list(c, MARGIN + 4, y - 2, notes, PAGE_W - 2 * MARGIN - 12)
    doc.add_page(c.to_bytes(), c.used_images)


def render_correspondence_page(doc: PDFDocument, scenario: dict[str, Any]) -> None:
    c = Canvas()
    header(c, scenario, str(scenario["document_type"]), 2, 2)
    y = PAGE_H - 96

    c.text(MARGIN, y - 10, str(scenario["sender_name"]), font="F2", size=10.5, color=(0.08, 0.08, 0.08))
    c.text(MARGIN, y - 22, str(scenario["sender_address"]), font="F1", size=8.2, color=(0.18, 0.18, 0.18))
    c.text(MARGIN, y - 34, f"Phone {scenario['sender_phone']}  |  Fax {scenario['sender_fax']}", font="F1", size=8.2, color=(0.18, 0.18, 0.18))

    c.text(PAGE_W - MARGIN - 136, y - 10, f"Decision Date: {scenario['dates']['decision_date'] or 'N/A'}", font="F2", size=8.6, color=(0.08, 0.08, 0.08))
    c.text(PAGE_W - MARGIN - 136, y - 22, f"Ref: {scenario['scenario_id']}", font="F1", size=8.2, color=(0.18, 0.18, 0.18))
    c.text(PAGE_W - MARGIN - 136, y - 34, f"Channel: {scenario['channel']}", font="F1", size=8.2, color=(0.18, 0.18, 0.18))

    y -= 48
    y = draw_section_header(c, MARGIN, y, PAGE_W - 2 * MARGIN, "Decision Summary")
    y = draw_kv_grid(
        c,
        MARGIN,
        y,
        PAGE_W - 2 * MARGIN,
        [
            ("Document Type", str(scenario["document_type"])),
            ("Decision", str(scenario["decision_status"])),
            ("Member", str(scenario["member_name"])),
            ("Member ID", str(scenario["member_id"])),
            ("Provider", str(scenario["provider_name"])),
            ("Provider NPI", str(scenario["provider_npi"])),
            ("Claim Number", str(scenario["claim_number"] or "N/A")),
            ("Authorization", str(scenario["authorization_number"] or "N/A")),
            ("Line Of Business", str(scenario["line_of_business"])),
            ("Clinical Area", str(scenario["clinical_area"])),
        ],
        cols=2,
        label_w=108,
    )

    y = draw_section_header(c, MARGIN, y, PAGE_W - 2 * MARGIN, "Service and Financial Details")
    rows = [
        ["Service", str(scenario["service_description"]), "Units", str(scenario["requested_units"] or "N/A")],
        ["Approved", str(scenario["approved_units"] or "N/A"), "Service Date", str(scenario["dates"]["service_date"] or "N/A")],
        ["Billed", currency(scenario["financials"]["billed_amount"]), "Allowed", currency(scenario["financials"]["allowed_amount"])],
        ["Plan Paid", currency(scenario["financials"]["plan_paid"]), "Member Resp", currency(scenario["financials"]["member_responsibility"])],
    ]
    y = draw_table(
        c,
        MARGIN,
        y,
        widths=[120, 180, 110, 130],
        headers=["Field", "Value", "Field", "Value"],
        rows=rows,
        row_h=20,
        header_h=20,
        font_size=8.1,
    )

    y = draw_section_header(c, MARGIN, y, PAGE_W - 2 * MARGIN, "Reason and Instructions")
    c.set_stroke(0.2, 0.2, 0.2)
    c.rect(MARGIN, y - 92, PAGE_W - 2 * MARGIN, 92, fill=False, stroke=True)
    y = paragraph(
        c,
        MARGIN + 8,
        y - 12,
        f"Reason codes: {', '.join(scenario['reason_codes'])}. {scenario['reason_text']}",
        PAGE_W - 2 * MARGIN - 16,
        size=8.7,
        leading=10.8,
    )

    docs_requested = scenario["documents_requested"]
    if docs_requested:
        y = draw_section_header(c, MARGIN, y - 4, PAGE_W - 2 * MARGIN, "Requested Attachments")
        rows = [[str(index + 1), item] for index, item in enumerate(docs_requested)]
        y = draw_table(
            c,
            MARGIN,
            y,
            widths=[50, PAGE_W - 2 * MARGIN - 50],
            headers=["#", "Document or action item"],
            rows=rows,
            row_h=18,
            header_h=20,
            font_size=8.2,
        )

    y = draw_section_header(c, MARGIN, y, PAGE_W - 2 * MARGIN, "Operational Next Steps")
    y = bullet_list(c, MARGIN + 4, y - 2, list(scenario["next_steps"]), PAGE_W - 2 * MARGIN - 12)
    draw_signature_block(
        c,
        MARGIN,
        max(88, y - 20),
        210,
        "Taylor Brooks",
        "Utilization Management Coordinator",
        f"{scenario['dates']['decision_date'] or '2026-02-01'} 09:12",
    )
    doc.add_page(c.to_bytes(), c.used_images)


def render_packet(scenario: dict[str, Any], pdf_path: Path) -> None:
    doc = PDFDocument()
    render_fax_cover(doc, scenario)
    render_correspondence_page(doc, scenario)
    doc.save(str(pdf_path))


def build_ixp_record(scenario: dict[str, Any], pdf_path: Path, text_path: Path) -> dict[str, Any]:
    dates = scenario["dates"]
    financials = scenario["financials"]
    field_values = {
        "document_type": scenario["document_type"],
        "document_family": scenario["document_family"],
        "line_of_business": scenario["line_of_business"],
        "payer_name": scenario["sender_name"],
        "recipient_name": scenario["recipient_name"],
        "member_name": scenario["member_name"],
        "member_id": scenario["member_id"],
        "member_dob": scenario["member_dob"],
        "provider_name": scenario["provider_name"],
        "provider_npi": scenario["provider_npi"],
        "claim_number": scenario["claim_number"],
        "authorization_number": scenario["authorization_number"],
        "policy_or_group_id": scenario["policy_or_group_id"],
        "service_description": scenario["service_description"],
        "decision_status": scenario["decision_status"],
        "reason_category": scenario["reason_category"],
        "reason_codes": scenario["reason_codes"],
        "reason_text": scenario["reason_text"],
        "request_received": dates["request_received"],
        "decision_date": dates["decision_date"],
        "service_date": dates["service_date"],
        "authorization_start": dates["authorization_start"],
        "authorization_end": dates["authorization_end"],
        "response_deadline": dates["response_deadline"],
        "requested_units": scenario["requested_units"],
        "approved_units": scenario["approved_units"],
        "billed_amount": financials["billed_amount"],
        "allowed_amount": financials["allowed_amount"],
        "plan_paid": financials["plan_paid"],
        "member_responsibility": financials["member_responsibility"],
        "documents_requested": scenario["documents_requested"],
    }
    return {
        "document_id": slugify(f"{scenario['scenario_id']}_{scenario['document_type']}"),
        "source_pdf": str(pdf_path.relative_to(OUTPUT_ROOT)),
        "source_text": str(text_path.relative_to(OUTPUT_ROOT)),
        "classification": {
            "document_type": scenario["document_type"],
            "document_family": scenario["document_family"],
            "confidence": 0.97,
        },
        "fields": {
            key: {
                "value": value,
                "confidence": confidence_for(key, value),
            }
            for key, value in field_values.items()
        },
    }


def infer_denial_of_service(record: dict[str, Any]) -> bool:
    family = str(record["classification"]["document_family"])
    status = str(record["fields"]["decision_status"]["value"] or "").lower()
    reason_category = str(record["fields"]["reason_category"]["value"] or "").lower()
    if status not in {"denied", "upheld"}:
        return False
    if family not in {"claims", "appeal"}:
        return False
    if family == "claims":
        return True
    if family == "appeal" and reason_category not in {"appeal_tracking", "medical_necessity_met_on_appeal"}:
        return True
    return reason_category in {"coverage_exclusion", "timely_filing"}


def infer_payer_auth_problem(record: dict[str, Any]) -> bool:
    family = str(record["classification"]["document_family"])
    status = str(record["fields"]["decision_status"]["value"] or "").lower()
    reason_category = str(record["fields"]["reason_category"]["value"] or "").lower()
    if family not in {"prior_auth", "pharmacy"}:
        return False
    return status in {"denied", "partially_approved"} or reason_category in {"step_therapy", "missing_information"}


def determine_priority(record: dict[str, Any], denial_of_service: bool, payer_auth_problem: bool) -> str:
    family = str(record["classification"]["document_family"])
    status = str(record["fields"]["decision_status"]["value"] or "").lower()
    if denial_of_service or family in {"payment_integrity", "appeal"}:
        return "high"
    if payer_auth_problem or status in {"pended", "information_requested"}:
        return "medium"
    return "low"


def queue_for(record: dict[str, Any], denial_of_service: bool, payer_auth_problem: bool) -> str:
    family = str(record["classification"]["document_family"])
    status = str(record["fields"]["decision_status"]["value"] or "").lower()
    if family in {"prior_auth", "pharmacy"}:
        return "KSWIC Authorization Team"
    if family == "appeal":
        return "KSWIC Appeals"
    if family == "payment_integrity":
        return "KSWIC Rev Cycle Integrity"
    if denial_of_service:
        return "KSWIC Rev Cycle Denials"
    if payer_auth_problem:
        return "KSWIC Authorization Team"
    if family == "member_admin":
        return "KSWIC Eligibility Follow Up"
    if family == "claims" and status == "pended":
        return "KSWIC Billing Follow Up"
    if family == "claims" and status == "paid":
        return "KSWIC Payment Posting"
    return "KSWIC Intake Review"


def build_task(
    automation_id: str,
    action: str,
    rationale: str,
    record: dict[str, Any],
    *,
    note_text: str = "",
    owner_queue: str = "",
    priority: str = "",
) -> dict[str, Any]:
    return {
        "automation_id": automation_id,
        "action": action,
        "rationale": rationale,
        "inputs": {
            "document_id": record["document_id"],
            "member_id": record["fields"]["member_id"]["value"],
            "payer_name": record["fields"]["payer_name"]["value"],
            "claim_number": record["fields"]["claim_number"]["value"],
            "authorization_number": record["fields"]["authorization_number"]["value"],
            "decision_status": record["fields"]["decision_status"]["value"],
            "service_description": record["fields"]["service_description"]["value"],
            "priority": priority,
            "owner_queue": owner_queue,
            "note_text": note_text,
        },
    }


def route_record(record: dict[str, Any]) -> dict[str, Any]:
    family = str(record["classification"]["document_family"])
    status = str(record["fields"]["decision_status"]["value"] or "").lower()
    denial_of_service = infer_denial_of_service(record)
    payer_auth_problem = infer_payer_auth_problem(record)
    priority = determine_priority(record, denial_of_service, payer_auth_problem)
    owner_queue = queue_for(record, denial_of_service, payer_auth_problem)

    tasks: list[dict[str, Any]] = []
    if family in {"prior_auth", "pharmacy"}:
        if status in {"approved", "overturned"}:
            tasks.append(
                build_task(
                    "dummy_cerner_auth_update",
                    "create_or_update_auth_record",
                    "Authorization-style notice should update the Cerner auth record.",
                    record,
                    owner_queue=owner_queue,
                    priority=priority,
                )
            )
        if status == "denied":
            tasks.append(
                build_task(
                    "dummy_cerner_auth_update",
                    "route_to_auth_workqueue",
                    "Denied auth correspondence needs auth follow-up in Cerner.",
                    record,
                    owner_queue=owner_queue,
                    priority=priority,
                )
            )
            tasks.append(
                build_task(
                    "dummy_payer_portal_follow_up",
                    "check_status" if family == "prior_auth" else "submit_reconsideration",
                    "Authorization or pharmacy denial requires payer-portal follow-up.",
                    record,
                    owner_queue=owner_queue,
                    priority=priority,
                )
            )
        if status == "partially_approved":
            tasks.append(
                build_task(
                    "dummy_cerner_auth_update",
                    "create_or_update_auth_record",
                    "Partial approval should update authorized units in Cerner.",
                    record,
                    owner_queue=owner_queue,
                    priority=priority,
                )
            )
            tasks.append(
                build_task(
                    "dummy_payer_portal_follow_up",
                    "check_status",
                    "Partial approval needs clarification on remaining units.",
                    record,
                    owner_queue=owner_queue,
                    priority=priority,
                )
            )
    elif family == "claims":
        if status == "denied":
            tasks.append(
                build_task(
                    "dummy_rev_cycle_work_item",
                    "create_denial_case",
                    "Claim denial should open a rev-cycle denial work item.",
                    record,
                    owner_queue=owner_queue,
                    priority=priority,
                )
            )
            tasks.append(
                build_task(
                    "dummy_cerner_patient_account_update",
                    "add_patient_account_note",
                    "Claim denial should be visible on the Cerner patient account.",
                    record,
                    note_text="Synthetic denial correspondence routed from payer intake.",
                    owner_queue=owner_queue,
                    priority=priority,
                )
            )
            tasks.append(
                build_task(
                    "dummy_payer_portal_follow_up",
                    "check_status",
                    "Billing denial needs payer portal review for reconsideration options.",
                    record,
                    owner_queue=owner_queue,
                    priority=priority,
                )
            )
        elif status == "pended":
            tasks.append(
                build_task(
                    "dummy_cerner_patient_account_update",
                    "add_patient_account_note",
                    "Missing-information notices should create a patient-account follow-up note.",
                    record,
                    note_text="Synthetic pended claim awaiting records upload.",
                    owner_queue=owner_queue,
                    priority=priority,
                )
            )
            tasks.append(
                build_task(
                    "dummy_payer_portal_follow_up",
                    "upload_missing_documents",
                    "Pended claim requires document upload through the payer portal.",
                    record,
                    owner_queue=owner_queue,
                    priority=priority,
                )
            )
        elif status == "paid":
            tasks.append(
                build_task(
                    "dummy_cerner_patient_account_update",
                    "post_payment_summary",
                    "Paid EOB can be logged for downstream reconciliation when needed.",
                    record,
                    note_text="Synthetic EOB received and marked informational.",
                    owner_queue=owner_queue,
                    priority=priority,
                )
            )
    elif family == "appeal":
        tasks.append(
            build_task(
                "dummy_rev_cycle_work_item",
                "update_appeal_tracker",
                "Appeal correspondence should update the appeal tracker.",
                record,
                owner_queue=owner_queue,
                priority=priority,
            )
        )
        if status == "overturned":
            tasks.append(
                build_task(
                    "dummy_cerner_patient_account_update",
                    "note_denial_reversal",
                    "An overturn should be reflected on the patient account if claim follow-up continues.",
                    record,
                    note_text="Synthetic appeal overturn received.",
                    owner_queue=owner_queue,
                    priority=priority,
                )
            )
    elif family == "member_admin":
        tasks.append(
            build_task(
                "dummy_cerner_patient_account_update",
                "add_coverage_follow_up",
                "COB correspondence should create coverage follow-up in Cerner.",
                record,
                note_text="Synthetic COB verification request received.",
                owner_queue=owner_queue,
                priority=priority,
            )
        )
        tasks.append(
            build_task(
                "dummy_payer_portal_follow_up",
                "submit_cob_update",
                "Coverage updates flow back through the payer portal once patient details are confirmed.",
                record,
                owner_queue=owner_queue,
                priority=priority,
            )
        )
    elif family == "payment_integrity":
        tasks.append(
            build_task(
                "dummy_rev_cycle_work_item",
                "create_recoupment_case",
                "Recoupment notices should create a rev-cycle payment-integrity work item.",
                record,
                owner_queue=owner_queue,
                priority=priority,
            )
        )
        tasks.append(
            build_task(
                "dummy_payer_portal_follow_up",
                "request_recoupment_detail",
                "Teams often review the offset detail in the portal before disputing.",
                record,
                owner_queue=owner_queue,
                priority=priority,
            )
        )

    return {
        "document_id": record["document_id"],
        "document_type": record["classification"]["document_type"],
        "document_family": family,
        "denial_of_service": denial_of_service,
        "payer_auth_problem": payer_auth_problem,
        "priority": priority,
        "owner_queue": owner_queue,
        "tasks": tasks,
    }


def build_ixp_contract() -> dict[str, Any]:
    return {
        "demo_name": "KSWIC Payer Correspondence Intake",
        "description": "Starter IXP field contract for payer-correspondence classification and extraction.",
        "guidance": [
            "Treat the inbound file as potentially mixed-content because cover sheets and payer letters may share the same fax packet.",
            "Classify the correspondence first, then extract only the fields that are present in the payer notice.",
            "Route decision logic such as denial-of-service and payer-auth-problem downstream in Maestro or coded logic instead of forcing it into extraction prompts.",
        ],
        "fields": IXP_FIELDS,
    }


def build_maestro_spec() -> dict[str, Any]:
    return {
        "process_name": "KSWIC Payer Correspondence Intake",
        "trigger": "Inbound fax or portal notice arrives",
        "variables": [
            "packet_path",
            "ixp_document_type",
            "ixp_document_family",
            "ixp_confidence",
            "denial_of_service",
            "payer_auth_problem",
            "owner_queue",
            "automation_tasks",
        ],
        "steps": [
            {"id": "start", "type": "message_start", "name": "Fax received"},
            {"id": "persist_packet", "type": "service_task", "name": "Store packet and create intake case"},
            {"id": "ixp_extract", "type": "service_task", "name": "Run IXP classification and extraction"},
            {"id": "confidence_gate", "type": "exclusive_gateway", "name": "Extraction confidence acceptable?"},
            {"id": "classification_validation", "type": "user_task", "name": "Classification validation / human triage"},
            {"id": "route_logic", "type": "service_task", "name": "Apply routing rules"},
            {"id": "parallel_dispatch", "type": "parallel_gateway", "name": "Dispatch downstream automations"},
            {"id": "cerner_auth", "type": "service_task", "name": "Dummy Cerner auth update"},
            {"id": "cerner_account", "type": "service_task", "name": "Dummy Cerner patient account update"},
            {"id": "rev_cycle", "type": "service_task", "name": "Dummy rev cycle work item"},
            {"id": "payer_portal", "type": "service_task", "name": "Dummy payer portal follow-up"},
            {"id": "complete", "type": "end_event", "name": "Case routed"},
        ],
    }


def build_bpmn() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Definitions_kswic" targetNamespace="https://uipath-demo/kswic">
  <bpmn:process id="KSWICPayerCorrespondenceIntake" name="KSWIC Payer Correspondence Intake" isExecutable="false">
    <bpmn:startEvent id="Start_FaxReceived" name="Fax received">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:serviceTask id="Task_PersistPacket" name="Store packet and create intake case">
      <bpmn:incoming>Flow_1</bpmn:incoming>
      <bpmn:outgoing>Flow_2</bpmn:outgoing>
    </bpmn:serviceTask>
    <bpmn:serviceTask id="Task_IXPExtract" name="Run IXP classification and extraction">
      <bpmn:incoming>Flow_2</bpmn:incoming>
      <bpmn:outgoing>Flow_3</bpmn:outgoing>
    </bpmn:serviceTask>
    <bpmn:exclusiveGateway id="Gateway_Confidence" name="Confidence acceptable?">
      <bpmn:incoming>Flow_3</bpmn:incoming>
      <bpmn:outgoing>Flow_4</bpmn:outgoing>
      <bpmn:outgoing>Flow_5</bpmn:outgoing>
    </bpmn:exclusiveGateway>
    <bpmn:userTask id="Task_Validation" name="Classification validation or human triage">
      <bpmn:incoming>Flow_4</bpmn:incoming>
      <bpmn:outgoing>Flow_6</bpmn:outgoing>
    </bpmn:userTask>
    <bpmn:serviceTask id="Task_RouteLogic" name="Apply routing rules">
      <bpmn:incoming>Flow_5</bpmn:incoming>
      <bpmn:incoming>Flow_6</bpmn:incoming>
      <bpmn:outgoing>Flow_7</bpmn:outgoing>
    </bpmn:serviceTask>
    <bpmn:parallelGateway id="Gateway_Dispatch" name="Dispatch downstream automations">
      <bpmn:incoming>Flow_7</bpmn:incoming>
      <bpmn:outgoing>Flow_8</bpmn:outgoing>
      <bpmn:outgoing>Flow_9</bpmn:outgoing>
      <bpmn:outgoing>Flow_10</bpmn:outgoing>
      <bpmn:outgoing>Flow_11</bpmn:outgoing>
    </bpmn:parallelGateway>
    <bpmn:serviceTask id="Task_CernerAuth" name="Dummy Cerner auth update">
      <bpmn:incoming>Flow_8</bpmn:incoming>
      <bpmn:outgoing>Flow_12</bpmn:outgoing>
    </bpmn:serviceTask>
    <bpmn:serviceTask id="Task_CernerAccount" name="Dummy Cerner patient account update">
      <bpmn:incoming>Flow_9</bpmn:incoming>
      <bpmn:outgoing>Flow_13</bpmn:outgoing>
    </bpmn:serviceTask>
    <bpmn:serviceTask id="Task_RevCycle" name="Dummy rev cycle work item">
      <bpmn:incoming>Flow_10</bpmn:incoming>
      <bpmn:outgoing>Flow_14</bpmn:outgoing>
    </bpmn:serviceTask>
    <bpmn:serviceTask id="Task_PayerPortal" name="Dummy payer portal follow-up">
      <bpmn:incoming>Flow_11</bpmn:incoming>
      <bpmn:outgoing>Flow_15</bpmn:outgoing>
    </bpmn:serviceTask>
    <bpmn:parallelGateway id="Gateway_Join" name="Join downstream updates">
      <bpmn:incoming>Flow_12</bpmn:incoming>
      <bpmn:incoming>Flow_13</bpmn:incoming>
      <bpmn:incoming>Flow_14</bpmn:incoming>
      <bpmn:incoming>Flow_15</bpmn:incoming>
      <bpmn:outgoing>Flow_16</bpmn:outgoing>
    </bpmn:parallelGateway>
    <bpmn:endEvent id="End_Complete" name="Case routed">
      <bpmn:incoming>Flow_16</bpmn:incoming>
    </bpmn:endEvent>

    <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_FaxReceived" targetRef="Task_PersistPacket" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_PersistPacket" targetRef="Task_IXPExtract" />
    <bpmn:sequenceFlow id="Flow_3" sourceRef="Task_IXPExtract" targetRef="Gateway_Confidence" />
    <bpmn:sequenceFlow id="Flow_4" sourceRef="Gateway_Confidence" targetRef="Task_Validation" name="No" />
    <bpmn:sequenceFlow id="Flow_5" sourceRef="Gateway_Confidence" targetRef="Task_RouteLogic" name="Yes" />
    <bpmn:sequenceFlow id="Flow_6" sourceRef="Task_Validation" targetRef="Task_RouteLogic" />
    <bpmn:sequenceFlow id="Flow_7" sourceRef="Task_RouteLogic" targetRef="Gateway_Dispatch" />
    <bpmn:sequenceFlow id="Flow_8" sourceRef="Gateway_Dispatch" targetRef="Task_CernerAuth" />
    <bpmn:sequenceFlow id="Flow_9" sourceRef="Gateway_Dispatch" targetRef="Task_CernerAccount" />
    <bpmn:sequenceFlow id="Flow_10" sourceRef="Gateway_Dispatch" targetRef="Task_RevCycle" />
    <bpmn:sequenceFlow id="Flow_11" sourceRef="Gateway_Dispatch" targetRef="Task_PayerPortal" />
    <bpmn:sequenceFlow id="Flow_12" sourceRef="Task_CernerAuth" targetRef="Gateway_Join" />
    <bpmn:sequenceFlow id="Flow_13" sourceRef="Task_CernerAccount" targetRef="Gateway_Join" />
    <bpmn:sequenceFlow id="Flow_14" sourceRef="Task_RevCycle" targetRef="Gateway_Join" />
    <bpmn:sequenceFlow id="Flow_15" sourceRef="Task_PayerPortal" targetRef="Gateway_Join" />
    <bpmn:sequenceFlow id="Flow_16" sourceRef="Gateway_Join" targetRef="End_Complete" />
  </bpmn:process>
</bpmn:definitions>
"""


def build_flow_markdown() -> str:
    return """# KSWIC Payer Correspondence Maestro Flow

This demo flow keeps the platform boundary explicit:

- IXP classifies the incoming payer correspondence and extracts core fields.
- Maestro owns orchestration, confidence gating, and multi-system routing.
- Dummy downstream automations stand in for Cerner, payer portals, and rev cycle systems.

```mermaid
flowchart LR
  A[Fax or portal notice arrives] --> B[Store packet and create intake case]
  B --> C[IXP classify and extract]
  C --> D{Confidence acceptable?}
  D -- No --> E[Classification validation or human triage]
  D -- Yes --> F[Apply routing rules]
  E --> F
  F --> G{Needs downstream actions?}
  G --> H[Dummy Cerner auth update]
  G --> I[Dummy Cerner patient account update]
  G --> J[Dummy rev cycle work item]
  G --> K[Dummy payer portal follow-up]
  H --> L[Case routed]
  I --> L
  J --> L
  K --> L
```

## Routing logic

- `denial_of_service = true` when a claim-side denial is extracted from payer correspondence.
- `payer_auth_problem = true` when a prior-auth or pharmacy-auth notice indicates an authorization-side follow-up.
- Cerner auth tasks are reserved for prior-auth and pharmacy-auth notices.
- Cerner patient-account notes are reserved for claim, COB, and payment-posting style notices.
- Rev cycle work items are reserved for denials, appeals, and recoupments.
- Payer-portal actions are reserved for status checks, uploads, reconsiderations, COB updates, and recoupment review.
"""


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_ground_truth_lines(record: dict[str, Any], route: dict[str, Any]) -> list[dict[str, Any]]:
    fields = record["fields"]
    values = {
        "document_type": fields["document_type"]["value"],
        "document_family": fields["document_family"]["value"],
        "payer_name": fields["payer_name"]["value"],
        "member_name": fields["member_name"]["value"],
        "member_id": fields["member_id"]["value"],
        "claim_number": fields["claim_number"]["value"],
        "authorization_number": fields["authorization_number"]["value"],
        "decision_status": fields["decision_status"]["value"],
        "reason_text": fields["reason_text"]["value"],
        "denial_of_service": bool_text(route["denial_of_service"]),
        "payer_auth_problem": bool_text(route["payer_auth_problem"]),
        "owner_queue": route["owner_queue"],
    }
    lines = []
    for key, value in values.items():
        lines.append(
            {
                "doc_id": record["document_id"],
                "canonical_field": key,
                "value": value,
                "annotator_id": "synthetic-demo-builder",
            }
        )
    return lines


def main() -> None:
    PACKET_ROOT.mkdir(parents=True, exist_ok=True)
    MAESTRO_ROOT.mkdir(parents=True, exist_ok=True)
    AUTOMATION_ROOT.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, Any]] = []
    ixp_documents: list[dict[str, Any]] = []
    routed_documents: list[dict[str, Any]] = []
    ground_truth_lines: list[dict[str, Any]] = []

    for scenario in SCENARIOS:
        stem = slugify(f"{scenario['scenario_id']}_{scenario['document_type']}")
        scenario_dir = PACKET_ROOT / stem
        scenario_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = scenario_dir / f"{stem}.pdf"
        json_path = scenario_dir / f"{stem}.json"
        text_path = scenario_dir / f"{stem}.txt"

        render_packet(scenario, pdf_path)
        write_json(json_path, scenario)
        text_path.write_text(build_text_packet(scenario), encoding="utf-8")

        ixp_record = build_ixp_record(scenario, pdf_path, text_path)
        route = route_record(ixp_record)

        manifest.append(
            {
                "document_id": ixp_record["document_id"],
                "scenario_id": scenario["scenario_id"],
                "document_type": scenario["document_type"],
                "document_family": scenario["document_family"],
                "pdf": str(pdf_path.relative_to(OUTPUT_ROOT)),
                "json": str(json_path.relative_to(OUTPUT_ROOT)),
                "text": str(text_path.relative_to(OUTPUT_ROOT)),
            }
        )
        ixp_documents.append(ixp_record)
        routed_documents.append(route)
        ground_truth_lines.extend(build_ground_truth_lines(ixp_record, route))

    write_json(OUTPUT_ROOT / "scenario_catalog.json", SCENARIOS)
    write_json(OUTPUT_ROOT / "packet_manifest.json", manifest)
    write_json(OUTPUT_ROOT / "ixp_extraction_contract.json", build_ixp_contract())
    write_json(
        OUTPUT_ROOT / "simulated_ixp_output.json",
        {
            "demo_name": "KSWIC Payer Correspondence Intake",
            "documents": ixp_documents,
        },
    )
    write_json(
        OUTPUT_ROOT / "simulated_maestro_run.json",
        {
            "process_name": "KSWIC Payer Correspondence Intake",
            "documents": routed_documents,
        },
    )

    ground_truth_path = OUTPUT_ROOT / "ground_truth.jsonl"
    ground_truth_path.write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in ground_truth_lines),
        encoding="utf-8",
    )

    write_json(MAESTRO_ROOT / "kswic_payer_correspondence_flow.json", build_maestro_spec())
    (MAESTRO_ROOT / "kswic_payer_correspondence.bpmn").write_text(build_bpmn(), encoding="utf-8")
    (MAESTRO_ROOT / "kswic_payer_correspondence_flow.md").write_text(build_flow_markdown(), encoding="utf-8")

    for stub in AUTOMATION_STUBS:
        write_json(AUTOMATION_ROOT / f"{stub['automation_id']}.json", stub)

    print(f"Wrote KSWIC payer-correspondence demo assets under {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
