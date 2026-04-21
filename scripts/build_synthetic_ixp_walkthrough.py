#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYNTHETIC_ROOT = REPO_ROOT.parent / "synthetic-record-generator" / "SyntheticRecordGenerator" / "output"
SYNTHETIC_GENERATOR_PACKAGE_ROOT = REPO_ROOT.parent / "synthetic-record-generator" / "SyntheticRecordGenerator"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "demo_resources" / "synthetic-ixp-walkthrough"
CURRENT_IXP_TAXONOMY_PATH = REPO_ROOT / "current-state-documents" / "prior-auth-acfc-raisa-universal-v5-taxonomy.json"
PROMPT_RECOMMENDATIONS_PATH = REPO_ROOT / "artifacts" / "fax-ground-truth-eval" / "ixp_prompt_test_recommendations.md"
GROUND_TRUTH_WORKBOOK_NAME = "synthetic_ground_truth.xlsx"
IXP_WORKBOOK_NAME = "synthetic_ixp_results.xlsx"
DEEPRAG_WORKBOOK_NAME = "synthetic_deeprag_results.xlsx"
COMPARISON_WORKBOOK_NAME = "synthetic_ixp_deeprag_ground_truth_comparison.xlsx"
HTML_DASHBOARD_NAME = "comparison_dashboard.html"
SANITIZED_DEMO_GLOBAL_PROMPT = (
    "You are a healthcare document data extraction specialist processing faxed prior authorization requests "
    "for the target health plan. A file may include fax cover sheets, transmission headers, duplicate pages, "
    "referral forms, clinical records, or other attachments before the actual request form. First identify the "
    "first complete prior authorization request form in the file and ignore cover sheets or non-form pages. "
    "Then extract data only from that request form and its continuation pages. If no complete prior authorization "
    "request form is present anywhere in the file, do not force a match to partial lookalike content. In that case, "
    "return null for non-repeating fields and create no rows for repeating groups such as Diagnosis Codes and "
    "Service Lines. Documents may be typed or handwritten. Return null when a field is absent, ambiguous, or "
    "illegible. Do not invent defaults."
)

GT_SCALAR_COLUMN_MAP = {
    "doc_type_id_vs": "__document_type__",
    "episode_type_vs": "Episode Type",
    "urgent_cb_vs": "Urgent",
    "standard_cb_vs": "Standard",
    "member_id_vs": "Member ID",
    "existing_auth_number_vs": "Existing Authorization Number",
    "treating_provider_id_vs": "Treating Provider ID",
    "attending_provider_id_vs": "Attending Provider ID",
    "referring_provider_id_vs": "Referring Provider ID",
    "admission_date_vs": "Admission Date",
    "length_of_stay_vs": "Length of Stay",
    "contact_name_vs": "Contact Name",
    "contact_phone_vs": "Contact Phone",
}

SERVICE_LINE_COLUMN_TO_NAME = {
    "procedure_code": "Procedure Code",
    "start_date": "Start Date",
    "end_date": "End Date",
    "units": "Number of Units",
}

TABLE_COLUMN_ALIASES = {
    "diagnosis code": "Diagnosis Code",
    "diagnosis code ": "Diagnosis Code",
    "procedure code": "Procedure Code",
    "start date": "Start Date",
    "end date": "End Date",
    "number of units": "Number of Units",
    "units": "Number of Units",
}

SAMPLE_TRACKING_COLUMNS = [
    "Fax ID",
    "File Name",
    "LOB",
    "Page Count",
    "Taxonomy (target near even split ext vs. new) ",
    "doc_type_id_vs",
    "complete_ind",
    "Diagnosis Code Count",
    "Procedure Code Count",
    "handwritten_ind",
    "episode_type_vs",
    "urgent_cb_vs",
    "standard_cb_vs",
    "member_id_vs",
    "existing_auth_number_vs",
    "treating_provider_id_vs",
    "attending_provider_id_vs",
    "referring_provider_id_vs",
    "admission_date_vs",
    "length_of_stay_vs",
    "contact_name_vs",
    "contact_phone_vs",
]

for index in range(1, 8):
    SAMPLE_TRACKING_COLUMNS.append(f"diagnosis_code{index}_vs")
for index in range(1, 11):
    SAMPLE_TRACKING_COLUMNS.extend(
        [
            f"procedure_code{index}_vs",
            f"start_date{index}_vs",
            f"end_date{index}_vs",
            f"units{index}_vs",
        ]
    )
SAMPLE_TRACKING_COLUMNS.extend(["synthetic_source_family", "synthetic_note"])

GROUNDED_DEEPRAG_STRATEGIES = {"deep_rag", "jit_deep_rag"}
PROMPT_CHANGE_SPECS = [
    {
        "target": "Global extraction scope",
        "priority": "cross-cutting",
        "current_keys": ["__GLOBAL__"],
        "proposed": (
            "Within the selected prior authorization request form, prefer evidence from the same labeled section as "
            "the target field. Do not borrow IDs, phone numbers, or dates from a different section when a same-section "
            "candidate exists. When a field requires inference, keep the inference local to the same table or labeled block."
        ),
        "why": "Helps reduce section-crossing failures such as wrong IDs, contaminated contact data, and stale carried-forward dates.",
    },
    {
        "target": "Type of Request / Urgent / Standard",
        "priority": "highest",
        "current_keys": ["Type of request"],
        "proposed": (
            "Treat Urgent, Standard, and Retrospective as one mutually exclusive checkbox group. Inspect only the mark "
            "immediately adjacent to each label. If exactly one option is marked, return that label. Ignore unchecked "
            "labels and ignore request-action fields such as Initial, Extension, Changes, or Other Request Type. Return "
            "null if none or multiple are clearly marked."
        ),
        "why": "The current eval recommends making the checkbox-group logic more explicit because urgency outputs are frequently missing.",
    },
    {
        "target": "Episode Type",
        "priority": "highest",
        "current_keys": ["Episode Type"],
        "proposed": (
            "Return exactly one of BH-IP, BH-OP, IP, or OP. First determine inpatient vs outpatient from Treatment "
            "Setting or explicit wording. Then determine BH only from explicit behavioral-health evidence on the request "
            "form, such as behavioral health, psychiatry, psych, mental health, substance use, detox, rehab, or a BH-specific "
            "request form. If BH evidence is present, return BH-IP or BH-OP. Use the canonical tokens BH-IP and BH-OP without spaces."
        ),
        "why": "The repo's prompt recommendations call out repeated BH-IP vs IP mismatches that look like BH detection failures.",
    },
    {
        "target": "Member ID",
        "priority": "highest",
        "current_keys": ["Member ID"],
        "proposed": (
            "Extract only the identifier labeled Member ID, Subscriber ID, Member Number, or Insurance ID in the member-information "
            "block. Preserve all letters, digits, separators, and suffixes exactly as shown, including trailing member segments such as -01. "
            "Do not use provider IDs, NPIs, TINs, fax numbers, authorization numbers, or reference numbers."
        ),
        "why": "Suggested because the current prompt is too generic about preserving the full identifier token, especially suffixes.",
    },
    {
        "target": "Diagnosis Codes",
        "priority": "highest",
        "current_keys": ["Diagnosis Codes", "Diagnosis Code"],
        "proposed": (
            "Each diagnosis row must be a complete ICD-10 code from the current request form. Reject candidates that lack the leading "
            "alpha character or end in a dangling period. When a code is split across adjacent boxes or OCR tokens, merge the visible "
            "parts for the same code before returning it. Prefer the diagnosis section of the current request over history, problem lists, "
            "or attachment-only diagnoses."
        ),
        "why": "Targets truncated codes, dropped leading letters, and diagnoses borrowed from unrelated clinical history.",
    },
    {
        "target": "Service Line Start Date",
        "priority": "highest",
        "current_keys": ["Start Date"],
        "proposed": (
            "Use carry-down only when the start-date cell for the current row is visibly blank and the same service-line table clearly "
            "uses merged or continued cells. Do not borrow dates from the request date, admission date, prior authorization history, "
            "previous packet pages, or unrelated tables. Preserve the year exactly as printed."
        ),
        "why": "The largest table-level problem in the current recommendations is over-broad inference for service-line start dates.",
    },
    {
        "target": "Provider IDs",
        "priority": "medium",
        "current_keys": ["Provider Information > Referring Physician", "Referring Provider ID", "Treating Provider ID", "Attending Provider ID"],
        "proposed": (
            "Search the matching provider block first and prefer labels like Provider ID, Attending ID, Referring ID, Servicing ID, "
            "or plan/provider number before giving up. Keep the do-not-substitute-NPI-or-TIN rule."
        ),
        "why": "Recommended because provider ID fields are mostly missing, which suggests the current prompt is not locating the right labeled block confidently.",
    },
    {
        "target": "Contact block",
        "priority": "medium",
        "current_keys": ["Contact Name", "Contact Phone", "Contact Fax"],
        "proposed": (
            "Contact Name must contain alphabetic name tokens and cannot be only a phone or fax number. Contact Phone and Contact Fax "
            "must come from the same contact/preparer block as Contact Name when such a block exists. Do not swap with provider phone/fax numbers."
        ),
        "why": "The existing recommendations flag contamination between contact fields and nearby provider phone/fax fields.",
    },
    {
        "target": "Length of Stay",
        "priority": "medium",
        "current_keys": ["Length of Stay"],
        "proposed": (
            "Return the single requested LOS day count only when one value is explicitly stated. Do not convert a range such as 3-5 days "
            "or 30-42 into one endpoint unless the form explicitly marks the requested total. If only a range is present, return the range "
            "verbatim or null according to the downstream contract."
        ),
        "why": "Recommended because current outputs often return loose ranges rather than a single normalized requested LOS.",
    },
]


@dataclass(frozen=True)
class SyntheticPacket:
    file_stem: str
    source_pdf_path: Path
    source_json_path: Path
    source_family: str
    source_note: str
    lob: str
    taxonomy_target: str
    page_count: int
    handwritten_ind: bool
    ground_truth_flat: dict[str, Any]
    diagnosis_codes: list[str]
    service_lines: list[dict[str, Any]]
    ixp_fields: dict[str, Any]
    ixp_tables: dict[str, list[dict[str, Any]]]
    deeprag_result: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a synthetic-only IXP walkthrough package from the sibling synthetic-record-generator repo."
    )
    parser.add_argument(
        "--synthetic-root",
        default=str(DEFAULT_SYNTHETIC_ROOT),
        help="Path to synthetic-record-generator/SyntheticRecordGenerator/output",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where walkthrough artifacts should be written.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    headers = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (dict, list))
                    else value
                    for key, value in row.items()
                }
            )


def output_relative_path(path: Path, output_dir: Path) -> str:
    try:
        return path.relative_to(output_dir).as_posix()
    except ValueError:
        return path.as_posix()


def sibling_repo_reference(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT.parent).as_posix()
    except ValueError:
        return path.as_posix()


def rewrite_generated_manifests(generation_root: Path, output_dir: Path) -> None:
    for manifest_path in generation_root.rglob("manifest.json"):
        payload = load_json(manifest_path)
        if not isinstance(payload, list):
            continue

        changed = False
        for item in payload:
            if not isinstance(item, dict):
                continue
            for key in ("pdf", "json"):
                current = item.get(key)
                if not isinstance(current, str):
                    continue
                rewritten = output_relative_path(manifest_path.parent / Path(current).name, output_dir)
                if rewritten != current:
                    item[key] = rewritten
                    changed = True

        if changed:
            write_json(manifest_path, payload)


def mmddyyyy(value: str) -> str:
    year, month, day = value.split("-")
    return f"{month}/{day}/{year}"


def slug_id(prefix: str, index: int) -> str:
    return f"{prefix}-{index:03d}"


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    text = " ".join(str(value).replace("\n", " ").split()).strip()
    return text or None


def boolish(value: Any) -> bool | None:
    text = clean_text(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in {"true", "yes", "1"}:
        return True
    if lowered in {"false", "no", "0"}:
        return False
    return None


def normalize_date_token(text: str) -> str | None:
    iso_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso_match:
        return f"{iso_match.group(2)}{iso_match.group(3)}{iso_match.group(1)}"
    slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
    if slash_match:
        month = int(slash_match.group(1))
        day = int(slash_match.group(2))
        year = int(slash_match.group(3))
        if year < 100:
            year = 2000 + year if year <= 50 else 1900 + year
        return f"{month:02d}{day:02d}{year:04d}"
    return None


def normalize_compare_value(path: str, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [normalize_compare_value(path, item) for item in value]
    if isinstance(value, bool):
        return str(value).lower()
    bool_value = boolish(value)
    if bool_value is not None:
        return str(bool_value).lower()
    text = clean_text(value)
    if text is None:
        return None
    lowered_path = path.lower()
    if "date" in lowered_path:
        return normalize_date_token(text) or "".join(ch for ch in text if ch.isdigit()) or text.casefold()
    if any(token in lowered_path for token in ("fax", "phone")):
        digits = "".join(ch for ch in text if ch.isdigit())
        return digits or text.casefold()
    if any(token in lowered_path for token in ("member id", "authorization number", "provider id", "document_type")):
        return "".join(ch for ch in text if ch.isalnum()).upper()
    if any(token in lowered_path for token in ("units", "length of stay")):
        digits = "".join(ch for ch in text if ch.isdigit())
        return digits or text.casefold()
    return text.casefold()


def compare_verdict(expected: Any, actual: Any, path: str) -> str:
    normalized_expected = normalize_compare_value(path, expected)
    normalized_actual = normalize_compare_value(path, actual)
    if normalized_expected is None and normalized_actual is None:
        return "both_missing"
    if normalized_expected is None:
        return "unexpected_value"
    if normalized_actual is None:
        return "missing"
    if normalized_expected == normalized_actual:
        return "match"
    return "mismatch"


def coerce_column_name(name: str) -> str:
    cleaned = clean_text(name) or name
    return TABLE_COLUMN_ALIASES.get(cleaned.lower(), cleaned)


def flatten_ixp_result(item: dict[str, Any]) -> dict[str, Any]:
    flattened = dict(item.get("normalized_fields") or {})
    if item.get("document_type_name"):
        flattened["__document_type__"] = item["document_type_name"]
    for table_name, rows in (item.get("normalized_tables") or {}).items():
        normalized_table_name = clean_text(table_name) or table_name
        for row_index, row in enumerate(rows or [], start=1):
            if not isinstance(row, dict):
                continue
            for column_name, value in row.items():
                flattened[f"{normalized_table_name}[{row_index}] > {coerce_column_name(str(column_name))}"] = value
    return flattened


def resolve_ixp_value(ixp_flat: dict[str, Any], path: str) -> Any:
    if path in ixp_flat:
        return ixp_flat[path]
    if path == "__document_type__":
        return ixp_flat.get("__document_type__")
    suffix = f"> {path}"
    candidates = [
        (key, value)
        for key, value in ixp_flat.items()
        if key.endswith(suffix) or (clean_text(key) or "") == path
    ]
    if not candidates:
        return None
    non_null = [(key, value) for key, value in candidates if value not in (None, "", [])]
    preferred = non_null or candidates
    preferred.sort(key=lambda item: (len(item[0]), item[0]))
    return preferred[0][1]


def _format_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def html_text(value: Any) -> str:
    return escape(_format_scalar(value))


def _column_name(index: int) -> str:
    name = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _sheet_xml(rows: list[list[Any]]) -> str:
    xml_rows: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        cells: list[str] = []
        for column_index, value in enumerate(row, start=1):
            if value is None:
                continue
            ref = f"{_column_name(column_index)}{row_index}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
                continue
            text = escape(_format_scalar(value))
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>')
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(xml_rows)}</sheetData>"
        "</worksheet>"
    )


def write_xlsx(path: Path, sheets: list[tuple[str, list[list[Any]]]]) -> None:
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    workbook_sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, (name, _) in enumerate(sheets, start=1)
    )
    workbook_rels = "".join(
        f'<Relationship Id="rId{index}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index, _ in enumerate(sheets, start=1)
    )
    content_type_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index, _ in enumerate(sheets, start=1)
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/docProps/core.xml" '
                'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
                '<Override PartName="/docProps/app.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
                f"{content_type_overrides}"
                "</Types>"
            ),
        )
        zf.writestr(
            "_rels/.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="xl/workbook.xml"/>'
                '<Relationship Id="rId2" '
                'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
                'Target="docProps/core.xml"/>'
                '<Relationship Id="rId3" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
                'Target="docProps/app.xml"/>'
                "</Relationships>"
            ),
        )
        zf.writestr(
            "docProps/core.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                'xmlns:dc="http://purl.org/dc/elements/1.1/" '
                'xmlns:dcterms="http://purl.org/dc/terms/" '
                'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                "<dc:title>Synthetic IXP Walkthrough</dc:title>"
                "<dc:creator>Codex</dc:creator>"
                f'<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>'
                f'<dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>'
                "</cp:coreProperties>"
            ),
        )
        zf.writestr(
            "docProps/app.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
                'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
                "<Application>Codex</Application>"
                f"<HeadingPairs><vt:vector size=\"2\" baseType=\"variant\"><vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant><vt:variant><vt:i4>{len(sheets)}</vt:i4></vt:variant></vt:vector></HeadingPairs>"
                f"<TitlesOfParts><vt:vector size=\"{len(sheets)}\" baseType=\"lpstr\">"
                + "".join(f"<vt:lpstr>{escape(name)}</vt:lpstr>" for name, _ in sheets)
                + "</vt:vector></TitlesOfParts>"
                "</Properties>"
            ),
        )
        zf.writestr(
            "xl/workbook.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f"<sheets>{workbook_sheets}</sheets>"
                "</workbook>"
            ),
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f"{workbook_rels}"
                "</Relationships>"
            ),
        )
        for index, (_, rows) in enumerate(sheets, start=1):
            zf.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))


def validate_xlsx(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        return sorted(name for name in zf.namelist() if name.startswith("xl/worksheets/sheet"))


def make_field_guess(
    *,
    path: str,
    value: Any,
    ixp_current: Any,
    confidence: float,
    reasoning: str,
    source_pages: list[int],
    status: str = "grounded",
) -> dict[str, Any]:
    return {
        "path": path,
        "value": value,
        "confidence": confidence,
        "status": status,
        "reasoning": reasoning,
        "source_pages": source_pages,
        "evidence": [
            {
                "page": page,
                "note": reasoning,
            }
            for page in source_pages
        ],
        "current_ixp_value": ixp_current,
    }


def provider_packet(paths: dict[str, Path]) -> SyntheticPacket:
    json_path = paths["json"]
    pdf_path = paths["pdf"]
    payload = load_json(json_path)

    diagnosis_codes = [
        payload["coding"]["principal_icd10"],
        payload["coding"]["secondary_diagnoses"][0][0],
        payload["coding"]["secondary_diagnoses"][1][0],
    ]
    service_lines = [
        {
            "Procedure Code": "52332",
            "Start Date": mmddyyyy(payload["procedure_report"]["date"]),
            "End Date": mmddyyyy(payload["procedure_report"]["date"]),
            "Number of Units": "1",
        }
    ]
    ground_truth = {
        "__document_type__": "Inpatient Prior Auth",
        "Episode Type": "Initial",
        "Urgent": True,
        "Standard": False,
        "Member ID": payload["patient"]["mrn"],
        "Existing Authorization Number": "PA-SYN-24001",
        "Treating Provider ID": "1881630041",
        "Attending Provider ID": "1417028895",
        "Referring Provider ID": "1063497781",
        "Admission Date": mmddyyyy(payload["patient"]["admission_date"]),
        "Length of Stay": "5",
        "Contact Name": payload["patient"]["attending_physician"],
        "Contact Phone": "(615) 555-1101",
    }
    for index, code in enumerate(diagnosis_codes, start=1):
        ground_truth[f"Diagnosis Codes[{index}] > Diagnosis Code"] = code
    for index, line in enumerate(service_lines, start=1):
        for key, value in line.items():
            ground_truth[f"Service Lines[{index}] > {key}"] = value

    ixp_fields = {
        "Member Information > Member ID": payload["patient"]["mrn"],
        "Request Information > Existing Authorization Number": None,
        "Provider Information > Treating Provider ID": "1881630041",
        "Provider Information > Attending Provider ID": "1417028895",
        "Provider Information > Referring Provider ID": None,
        "Request Information > Admission Date": "1/8/2026",
        "Request Information > Length of Stay": "5 days",
        "Request Information > Contact Name": "Harold Kim MD",
        "Request Information > Contact Phone": "615-555-1107",
        "Request Information > Episode Type": None,
        "Request Information > Urgent": True,
        "Request Information > Standard": False,
        "Request Information > Type of Request": "Admission Review",
        "Request Information > Treatment Setting": "Inpatient",
    }
    ixp_tables = {
        "Diagnosis Codes": [{"Diagnosis Code": code} for code in diagnosis_codes],
        "Service Lines": [
            {
                "Procedure Code": "52332",
                "Start Date": mmddyyyy(payload["procedure_report"]["date"]),
                "End Date": mmddyyyy(payload["procedure_report"]["date"]),
                "Number of Units": None,
            }
        ],
    }
    ixp_flat = flatten_ixp_result(
        {
            "document_type_name": ground_truth["__document_type__"],
            "normalized_fields": ixp_fields,
            "normalized_tables": ixp_tables,
        }
    )
    extraction = {
        "Episode Type": "Initial",
        "Urgent": True,
        "Standard": False,
        "Member ID": payload["patient"]["mrn"],
        "Existing Authorization Number": "PA-SYN-24001",
        "Treating Provider ID": "1881630041",
        "Attending Provider ID": "1417028895",
        "Referring Provider ID": "1063497781",
        "Admission Date": mmddyyyy(payload["patient"]["admission_date"]),
        "Length of Stay": "5",
        "Contact Name": payload["patient"]["attending_physician"],
        "Contact Phone": "(615) 555-1101",
        "Diagnosis Codes[1] > Diagnosis Code": diagnosis_codes[0],
        "Diagnosis Codes[2] > Diagnosis Code": diagnosis_codes[1],
        "Diagnosis Codes[3] > Diagnosis Code": diagnosis_codes[2],
        "Service Lines[1] > Procedure Code": "52332",
        "Service Lines[1] > Start Date": mmddyyyy(payload["procedure_report"]["date"]),
        "Service Lines[1] > End Date": mmddyyyy(payload["procedure_report"]["date"]),
        "Service Lines[1] > Number of Units": "1",
    }
    field_guesses = [
        make_field_guess(
            path=path,
            value=value,
            ixp_current=resolve_ixp_value(ixp_flat, path),
            confidence=0.96 if "Diagnosis Codes" not in path else 0.93,
            reasoning="Synthetic demo guess grounded from the provider packet narrative and procedure report.",
            source_pages=[1, 2] if "Member" in path or "Contact" in path else [4, 5],
        )
        for path, value in extraction.items()
    ]
    deeprag_result = {
        "strategy_used": "jit_deep_rag",
        "summary": "Synthetic grounded pass recovered the missing authorization metadata and completed the service-line row.",
        "warnings": [],
        "extraction": extraction,
        "field_guesses": field_guesses,
    }
    return SyntheticPacket(
        file_stem=pdf_path.stem,
        source_pdf_path=pdf_path,
        source_json_path=json_path,
        source_family="provider_records",
        source_note="Freshly generated from synthetic-record-generator via generate_provider_synthetic_records.py.",
        lob="Medicare Advantage",
        taxonomy_target="new",
        page_count=12,
        handwritten_ind=False,
        ground_truth_flat=ground_truth,
        diagnosis_codes=diagnosis_codes,
        service_lines=service_lines,
        ixp_fields=ixp_fields,
        ixp_tables=ixp_tables,
        deeprag_result=deeprag_result,
    )


def base_patient_chart_packet(paths: dict[str, Path]) -> SyntheticPacket:
    json_path = paths["json"]
    pdf_path = paths["pdf"]
    payload = load_json(json_path)

    diagnosis_codes = [payload["problems"][0]["icd10"], payload["problems"][1]["icd10"], payload["problems"][2]["icd10"]]
    stress_date = mmddyyyy(payload["diagnostics"]["stress_test"]["date"])
    service_lines = [
        {
            "Procedure Code": "93015",
            "Start Date": stress_date,
            "End Date": stress_date,
            "Number of Units": "1",
        }
    ]
    ground_truth = {
        "__document_type__": "Outpatient Prior Auth",
        "Episode Type": "New",
        "Urgent": False,
        "Standard": True,
        "Member ID": payload["patient"]["mrn"],
        "Existing Authorization Number": "PA-SYN-24002",
        "Treating Provider ID": "1992874501",
        "Attending Provider ID": "1508921143",
        "Referring Provider ID": "1770554208",
        "Admission Date": stress_date,
        "Length of Stay": "1",
        "Contact Name": payload["patient"]["pcp"],
        "Contact Phone": payload["patient"]["phone"],
    }
    for index, code in enumerate(diagnosis_codes, start=1):
        ground_truth[f"Diagnosis Codes[{index}] > Diagnosis Code"] = code
    for index, line in enumerate(service_lines, start=1):
        for key, value in line.items():
            ground_truth[f"Service Lines[{index}] > {key}"] = value

    ixp_fields = {
        "Member Information > Member ID": payload["patient"]["mrn"],
        "Request Information > Existing Authorization Number": None,
        "Provider Information > Treating Provider ID": "1992874501",
        "Provider Information > Attending Provider ID": "1508921143",
        "Provider Information > Referring Provider ID": None,
        "Request Information > Admission Date": "2/5/2026",
        "Request Information > Length of Stay": None,
        "Request Information > Contact Name": "Nina Patel",
        "Request Information > Contact Phone": payload["patient"]["phone"],
        "Request Information > Episode Type": "Initial",
        "Request Information > Urgent": False,
        "Request Information > Standard": True,
        "Request Information > Type of Request": "Outpatient Diagnostics",
        "Request Information > Treatment Setting": "Outpatient",
    }
    ixp_tables = {
        "Diagnosis Codes": [
            {"Diagnosis Code": diagnosis_codes[0]},
            {"Diagnosis Code": diagnosis_codes[1]},
            {"Diagnosis Code": payload["problems"][4]["icd10"]},
        ],
        "Service Lines": [
            {
                "Procedure Code": "93015",
                "Start Date": stress_date,
                "End Date": stress_date,
                "Number of Units": "2",
            }
        ],
    }
    ixp_flat = flatten_ixp_result(
        {
            "document_type_name": ground_truth["__document_type__"],
            "normalized_fields": ixp_fields,
            "normalized_tables": ixp_tables,
        }
    )
    extraction = {
        "Episode Type": "New",
        "Urgent": False,
        "Standard": True,
        "Member ID": payload["patient"]["mrn"],
        "Existing Authorization Number": "PA-SYN-24002",
        "Treating Provider ID": "1992874501",
        "Attending Provider ID": "1508921143",
        "Referring Provider ID": "1770554208",
        "Admission Date": stress_date,
        "Length of Stay": "1",
        "Contact Name": payload["patient"]["pcp"],
        "Contact Phone": None,
        "Diagnosis Codes[1] > Diagnosis Code": diagnosis_codes[0],
        "Diagnosis Codes[2] > Diagnosis Code": diagnosis_codes[1],
        "Diagnosis Codes[3] > Diagnosis Code": diagnosis_codes[2],
        "Service Lines[1] > Procedure Code": "93015",
        "Service Lines[1] > Start Date": stress_date,
        "Service Lines[1] > End Date": stress_date,
        "Service Lines[1] > Number of Units": "1",
    }
    field_guesses = [
        make_field_guess(
            path=path,
            value=value,
            ixp_current=resolve_ixp_value(ixp_flat, path),
            confidence=0.92 if path == "Contact Phone" else 0.95,
            reasoning="Synthetic grounded pass aligned the outpatient stress-test packet to the requested fields.",
            source_pages=[1, 3] if "Contact" in path or "Member" in path else [5, 6],
        )
        for path, value in extraction.items()
    ]
    deeprag_result = {
        "strategy_used": "deep_rag",
        "summary": "Synthetic DeepRAG pass corrected the episode type, recovered the missing authorization number, and fixed the incorrect unit count.",
        "warnings": ["Synthetic demo note: contact phone intentionally left blank to show a remaining missing field."],
        "extraction": extraction,
        "field_guesses": field_guesses,
    }
    return SyntheticPacket(
        file_stem=pdf_path.stem,
        source_pdf_path=pdf_path,
        source_json_path=json_path,
        source_family="base_patient_chart",
        source_note="Freshly generated from synthetic-record-generator via generate_synthetic_patient_pdf.py.",
        lob="Commercial PPO",
        taxonomy_target="new",
        page_count=18,
        handwritten_ind=False,
        ground_truth_flat=ground_truth,
        diagnosis_codes=diagnosis_codes,
        service_lines=service_lines,
        ixp_fields=ixp_fields,
        ixp_tables=ixp_tables,
        deeprag_result=deeprag_result,
    )


def payer_packet(paths: dict[str, Path]) -> SyntheticPacket:
    json_path = paths["json"]
    pdf_path = paths["pdf"]
    payload = load_json(json_path)

    diagnosis_codes = ["I50.9", "J44.9", "N18.30"]
    service_lines = [
        {
            "Procedure Code": "99223",
            "Start Date": "02/10/2026",
            "End Date": "02/12/2026",
            "Number of Units": "3",
        }
    ]
    ground_truth = {
        "__document_type__": "Extension Review Packet",
        "Episode Type": "Extension",
        "Urgent": False,
        "Standard": True,
        "Member ID": payload["member"]["member_id"],
        "Existing Authorization Number": "PA-SYN-24003",
        "Treating Provider ID": "1023384756",
        "Attending Provider ID": "1407785620",
        "Referring Provider ID": "1156293001",
        "Admission Date": "02/10/2026",
        "Length of Stay": "3",
        "Contact Name": payload["care_manager"],
        "Contact Phone": "(615) 555-2203",
    }
    for index, code in enumerate(diagnosis_codes, start=1):
        ground_truth[f"Diagnosis Codes[{index}] > Diagnosis Code"] = code
    for index, line in enumerate(service_lines, start=1):
        for key, value in line.items():
            ground_truth[f"Service Lines[{index}] > {key}"] = value

    ixp_fields = {
        "Member Information > Member ID": payload["member"]["member_id"],
        "Request Information > Existing Authorization Number": "PA-SYN-24003",
        "Provider Information > Treating Provider ID": "1023384756",
        "Provider Information > Attending Provider ID": "1407785620",
        "Provider Information > Referring Provider ID": None,
        "Request Information > Admission Date": "2/10/2026",
        "Request Information > Length of Stay": "3",
        "Request Information > Contact Name": "Sonia Patel RN CCM",
        "Request Information > Contact Phone": None,
        "Request Information > Episode Type": "Extension",
        "Request Information > Urgent": False,
        "Request Information > Standard": True,
        "Request Information > Type of Request": "Concurrent Review",
        "Request Information > Treatment Setting": "Inpatient",
    }
    ixp_tables = {
        "Diagnosis Codes": [{"Diagnosis Code": diagnosis_codes[0]}, {"Diagnosis Code": diagnosis_codes[1]}],
        "Service Lines": [],
    }
    deeprag_result = {
        "strategy_used": "ixp_hint_only",
        "summary": "Synthetic fallback case with no grounded retrieval. Keep IXP as the reviewable baseline for this packet.",
        "warnings": ["Synthetic demo fallback: skipped grounded retrieval for the payer packet."],
        "extraction": {},
        "field_guesses": [],
    }
    return SyntheticPacket(
        file_stem=pdf_path.stem,
        source_pdf_path=pdf_path,
        source_json_path=json_path,
        source_family="payer_records",
        source_note="Freshly generated from synthetic-record-generator via generate_payer_synthetic_records.py.",
        lob="Medicare Advantage",
        taxonomy_target="extension",
        page_count=14,
        handwritten_ind=False,
        ground_truth_flat=ground_truth,
        diagnosis_codes=diagnosis_codes,
        service_lines=service_lines,
        ixp_fields=ixp_fields,
        ixp_tables=ixp_tables,
        deeprag_result=deeprag_result,
    )


def build_packets(generated_sources: dict[str, dict[str, Path]]) -> list[SyntheticPacket]:
    packets = [
        provider_packet(generated_sources["provider_records"]),
        base_patient_chart_packet(generated_sources["base_patient_chart"]),
        payer_packet(generated_sources["payer_records"]),
    ]
    missing = [str(packet.source_pdf_path) for packet in packets if not packet.source_pdf_path.exists()]
    missing.extend(str(packet.source_json_path) for packet in packets if not packet.source_json_path.exists())
    if missing:
        joined = "\n".join(sorted(set(missing)))
        raise SystemExit(f"Synthetic source files are missing:\n{joined}")
    return packets


def generate_demo_packet_files(output_dir: Path) -> dict[str, dict[str, Path]]:
    package_root = SYNTHETIC_GENERATOR_PACKAGE_ROOT.resolve()
    generation_root = output_dir / "_generated_from_synthetic_record_generator"
    demo_root = output_dir / "demo_packet_files"

    if not package_root.exists():
        sibling_hint = sibling_repo_reference(package_root)
        raise SystemExit(
            "Synthetic walkthrough regeneration requires the sibling "
            f"`{sibling_hint}` repo to be present next to this repo."
        )

    generation_root.mkdir(parents=True, exist_ok=True)
    demo_root.mkdir(parents=True, exist_ok=True)

    for relative in (
        Path("output"),
        Path("Provider Synthetic Records"),
        Path("Payer Synthetic Records"),
        Path("base_patient_chart"),
        Path("provider_records"),
        Path("payer_records"),
    ):
        target = generation_root / relative
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

    for command in (
        ["python3", str(package_root / "generate_synthetic_patient_pdf.py")],
        ["python3", str(package_root / "generate_provider_synthetic_records.py")],
        ["python3", str(package_root / "generate_payer_synthetic_records.py")],
    ):
        subprocess.run(command, cwd=generation_root, check=True)

    rewrite_generated_manifests(generation_root, output_dir)

    source_map = {
        "base_patient_chart": {
            "pdf": generation_root / "output" / "synthetic_patient_chart_case_001.pdf",
            "json": generation_root / "output" / "synthetic_patient_chart_case_001.json",
        },
        "provider_records": {
            "pdf": generation_root / "Provider Synthetic Records" / "record_a_moderate_acuity.pdf",
            "json": generation_root / "Provider Synthetic Records" / "record_a_moderate_acuity.json",
        },
        "payer_records": {
            "pdf": generation_root / "Payer Synthetic Records" / "record_a_high_risk_member.pdf",
            "json": generation_root / "Payer Synthetic Records" / "record_a_high_risk_member.json",
        },
    }

    demo_sources: dict[str, dict[str, Path]] = {}
    for family, paths in source_map.items():
        family_dir = demo_root / family
        family_dir.mkdir(parents=True, exist_ok=True)
        pdf_target = family_dir / paths["pdf"].name
        json_target = family_dir / paths["json"].name
        shutil.copy2(paths["pdf"], pdf_target)
        shutil.copy2(paths["json"], json_target)
        demo_sources[family] = {
            "pdf": pdf_target,
            "json": json_target,
            "generated_pdf": paths["pdf"],
            "generated_json": paths["json"],
        }

    return demo_sources


def normalize_prompt_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def sanitize_prompt_for_demo(text: str) -> str:
    sanitized = text
    replacements = {
        "AmeriHealth Caritas (ACFC)": "the target health plan",
        "AmeriHealth Caritas": "the target health plan",
        "ACFC": "the target health plan",
    }
    for original, replacement in replacements.items():
        sanitized = sanitized.replace(original, replacement)
    return sanitized


def load_current_ixp_prompt_review() -> dict[str, Any]:
    taxonomy = load_json(CURRENT_IXP_TAXONOMY_PATH) if CURRENT_IXP_TAXONOMY_PATH.exists() else {}
    found: dict[str, str] = {}

    def walk(node: Any, trail: str = "") -> None:
        if isinstance(node, dict):
            name = node.get("name")
            instructions = node.get("instructions")
            if isinstance(name, str) and isinstance(instructions, str):
                normalized = normalize_prompt_name(name)
                found.setdefault(normalized, instructions.strip())
                if trail:
                    found.setdefault(f"__trail__::{normalized}", trail)
            for key, value in node.items():
                next_trail = f"{trail}/{key}" if trail else key
                walk(value, next_trail)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{trail}[{index}]")

    walk(taxonomy)
    general_prompt = (
        taxonomy.get("label_groups", [{}])[0].get("instructions")
        if isinstance(taxonomy.get("label_groups"), list) and taxonomy.get("label_groups")
        else SANITIZED_DEMO_GLOBAL_PROMPT
    )

    prompt_changes: list[dict[str, Any]] = []
    for spec in PROMPT_CHANGE_SPECS:
        current_parts = []
        for key in spec["current_keys"]:
            if key == "__GLOBAL__":
                if general_prompt:
                    current_parts.append(general_prompt.strip())
                continue
            current = found.get(normalize_prompt_name(key))
            if current:
                current_parts.append(current)
        prompt_changes.append(
            {
                "target": spec["target"],
                "priority": spec["priority"],
                "current_prompt": sanitize_prompt_for_demo(
                    "\n\n".join(dict.fromkeys(current_parts))
                )
                if current_parts
                else "Current prompt text is omitted from the sanitized demo bundle.",
                "proposed_prompt": spec["proposed"],
                "why": spec["why"],
            }
        )

    return {
        "taxonomy_name": taxonomy.get("name") or "Sanitized demo prompt snapshot",
        "taxonomy_description": taxonomy.get("description") or "Internal source files were omitted from this shareable repo.",
        "taxonomy_path": (
            sibling_repo_reference(CURRENT_IXP_TAXONOMY_PATH)
            if CURRENT_IXP_TAXONOMY_PATH.exists()
            else "Not included in sanitized demo repo."
        ),
        "prompt_recommendations_path": (
            sibling_repo_reference(PROMPT_RECOMMENDATIONS_PATH)
            if PROMPT_RECOMMENDATIONS_PATH.exists()
            else "Not included in sanitized demo repo."
        ),
        "general_prompt": sanitize_prompt_for_demo(general_prompt or ""),
        "prompt_changes": prompt_changes,
    }


def packet_to_sample_tracking_row(packet: SyntheticPacket, index: int) -> dict[str, Any]:
    row: dict[str, Any] = {
        "Fax ID": slug_id("SYNFAX", index),
        "File Name": packet.file_stem,
        "LOB": packet.lob,
        "Page Count": packet.page_count,
        "Taxonomy (target near even split ext vs. new) ": packet.taxonomy_target,
        "doc_type_id_vs": packet.ground_truth_flat["__document_type__"],
        "complete_ind": True,
        "Diagnosis Code Count": len(packet.diagnosis_codes),
        "Procedure Code Count": len(packet.service_lines),
        "handwritten_ind": packet.handwritten_ind,
        "synthetic_source_family": packet.source_family,
        "synthetic_note": packet.source_note,
    }
    inverse_map = {value: key for key, value in GT_SCALAR_COLUMN_MAP.items()}
    for path, value in packet.ground_truth_flat.items():
        if path in inverse_map:
            row[inverse_map[path]] = value
    for index, code in enumerate(packet.diagnosis_codes, start=1):
        row[f"diagnosis_code{index}_vs"] = code
    for index, service_line in enumerate(packet.service_lines, start=1):
        row[f"procedure_code{index}_vs"] = service_line.get("Procedure Code")
        row[f"start_date{index}_vs"] = service_line.get("Start Date")
        row[f"end_date{index}_vs"] = service_line.get("End Date")
        row[f"units{index}_vs"] = service_line.get("Number of Units")
    for column in SAMPLE_TRACKING_COLUMNS:
        row.setdefault(column, None)
    return row


def build_ground_truth_rows(packets: list[SyntheticPacket]) -> list[dict[str, Any]]:
    return [packet_to_sample_tracking_row(packet, index) for index, packet in enumerate(packets, start=1)]


def build_source_manifest(packets: list[SyntheticPacket], output_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for packet in packets:
        rows.append(
            {
                "file_name": packet.file_stem,
                "source_family": packet.source_family,
                "source_pdf_path": output_relative_path(packet.source_pdf_path, output_dir),
                "source_json_path": output_relative_path(packet.source_json_path, output_dir),
                "synthetic_note": packet.source_note,
                "document_type_name": packet.ground_truth_flat["__document_type__"],
                "generated_by_repo": sibling_repo_reference(SYNTHETIC_GENERATOR_PACKAGE_ROOT),
            }
        )
    return rows


def build_ixp_run_payload(packets: list[SyntheticPacket], output_dir: Path) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    results: list[dict[str, Any]] = []
    for index, packet in enumerate(packets, start=1):
        results.append(
            {
                "source_blob_file_path": output_relative_path(packet.source_pdf_path, output_dir),
                "source_file_name": packet.source_pdf_path.name,
                "source_bucket_name": "synthetic-record-generator",
                "status": "success",
                "document_id": slug_id("synthetic-doc", index),
                "document_type_id": re.sub(r"[^a-z0-9]+", "_", packet.ground_truth_flat["__document_type__"].lower()).strip("_"),
                "document_type_name": packet.ground_truth_flat["__document_type__"],
                "normalized_fields": packet.ixp_fields,
                "normalized_tables": packet.ixp_tables,
                "preprocessing_summary": None,
                "output_blob_file_path": None,
                "error": None,
            }
        )
    finished_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "run_id": "synthetic-ixp-walkthrough-20260407",
        "started_at": started_at,
        "finished_at": finished_at,
        "project_name": "UM Intake",
        "project_id": "synthetic-um-intake",
        "tag_name": "Production",
        "project_version": 999,
        "project_version_name": "synthetic-demo",
        "processed_count": len(results),
        "failed_count": 0,
        "results": results,
    }


def build_deeprag_payload(packets: list[SyntheticPacket]) -> dict[str, dict[str, Any]]:
    return {packet.file_stem: packet.deeprag_result for packet in packets}


def build_field_rows(
    packets: list[SyntheticPacket],
    ixp_results: dict[str, dict[str, Any]],
    deeprag_results: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for packet in packets:
        gt = packet.ground_truth_flat
        ixp_flat = flatten_ixp_result(ixp_results.get(packet.file_stem, {}))
        deeprag_result = deeprag_results.get(packet.file_stem) or {}
        strategy = deeprag_result.get("strategy_used") or "missing_output"
        grounded = strategy in GROUNDED_DEEPRAG_STRATEGIES
        deeprag_extraction = deeprag_result.get("extraction") or {}
        all_paths = sorted((set(gt) | set(deeprag_extraction)) - {"__document_type__"})
        for path in all_paths:
            expected = gt.get(path)
            ixp_value = resolve_ixp_value(ixp_flat, path)
            deeprag_value = deeprag_extraction.get(path) if grounded else None
            rows.append(
                {
                    "file_name": packet.file_stem,
                    "path": path,
                    "expected_value": expected,
                    "ixp_value": ixp_value,
                    "ixp_verdict": compare_verdict(expected, ixp_value, path),
                    "deeprag_value": deeprag_value,
                    "deeprag_verdict": "not_comparable" if not grounded else compare_verdict(expected, deeprag_value, path),
                    "deeprag_strategy_used": strategy,
                    "deeprag_comparison_state": "grounded" if grounded else strategy,
                }
            )
    return rows


def build_document_rows(
    packets: list[SyntheticPacket],
    field_rows: list[dict[str, Any]],
    deeprag_results: dict[str, dict[str, Any]],
    output_dir: Path,
) -> list[dict[str, Any]]:
    by_doc: dict[str, list[dict[str, Any]]] = {}
    for row in field_rows:
        by_doc.setdefault(row["file_name"], []).append(row)

    documents: list[dict[str, Any]] = []
    for packet in packets:
        rows = by_doc.get(packet.file_stem, [])
        ixp_counts = Counter(row["ixp_verdict"] for row in rows if row["expected_value"] is not None)
        deeprag_rows = [row for row in rows if row["expected_value"] is not None]
        grounded_rows = [row for row in deeprag_rows if row["deeprag_comparison_state"] == "grounded"]
        deeprag_counts = Counter(
            row["deeprag_verdict"]
            for row in grounded_rows
            if row["deeprag_verdict"] != "not_comparable"
        )
        deeprag_result = deeprag_results.get(packet.file_stem) or {}
        documents.append(
            {
                "file_name": packet.file_stem,
                "source_pdf_path": output_relative_path(packet.source_pdf_path, output_dir),
                "doc_type_id_vs": packet.ground_truth_flat["__document_type__"],
                "expected_field_count": sum(1 for value in packet.ground_truth_flat.values() if value is not None),
                "ixp_match_count": ixp_counts.get("match", 0),
                "ixp_missing_count": ixp_counts.get("missing", 0),
                "ixp_mismatch_count": ixp_counts.get("mismatch", 0),
                "deeprag_strategy_used": deeprag_result.get("strategy_used") or "missing_output",
                "deeprag_extraction_field_count": len(deeprag_result.get("extraction") or {}),
                "deeprag_match_count": deeprag_counts.get("match", 0),
                "deeprag_missing_count": deeprag_counts.get("missing", 0),
                "deeprag_mismatch_count": deeprag_counts.get("mismatch", 0),
                "deeprag_not_comparable_count": len(deeprag_rows) - len(grounded_rows),
                "deeprag_grounded_field_count": len(grounded_rows),
            }
        )
    return documents


def ixp_workbook_sheets(ixp_run: dict[str, Any]) -> list[tuple[str, list[list[Any]]]]:
    results = ixp_run["results"]
    field_columns = sorted({key for item in results for key in (item.get("normalized_fields") or {}).keys()})
    table_columns = sorted(
        {
            cell_name
            for item in results
            for rows in (item.get("normalized_tables") or {}).values()
            for row in rows
            for cell_name in row.keys()
        }
    )

    summary_rows = [
        [
            "run_id",
            "started_at",
            "finished_at",
            "project_name",
            "project_id",
            "tag_name",
            "project_version",
            "project_version_name",
            "processed_count",
            "failed_count",
        ],
        [
            ixp_run["run_id"],
            ixp_run["started_at"],
            ixp_run["finished_at"],
            ixp_run["project_name"],
            ixp_run["project_id"],
            ixp_run["tag_name"],
            ixp_run["project_version"],
            ixp_run["project_version_name"],
            ixp_run["processed_count"],
            ixp_run["failed_count"],
        ],
    ]

    document_rows = [[
        "source_blob_file_path",
        "source_file_name",
        "source_bucket_name",
        "status",
        "document_id",
        "document_type_id",
        "document_type_name",
    ]]
    field_rows = [[
        "source_blob_file_path",
        "source_file_name",
        "status",
        "document_type_name",
        *field_columns,
    ]]
    table_rows = [[
        "source_blob_file_path",
        "source_file_name",
        "status",
        "document_type_name",
        "table_name",
        "row_index",
        *table_columns,
    ]]

    for item in results:
        document_rows.append(
            [
                item["source_blob_file_path"],
                item["source_file_name"],
                item["source_bucket_name"],
                item["status"],
                item["document_id"],
                item["document_type_id"],
                item["document_type_name"],
            ]
        )
        field_rows.append(
            [
                item["source_blob_file_path"],
                item["source_file_name"],
                item["status"],
                item["document_type_name"],
                *[(item.get("normalized_fields") or {}).get(column) for column in field_columns],
            ]
        )
        for table_name, rows in (item.get("normalized_tables") or {}).items():
            for row_index, row in enumerate(rows):
                table_rows.append(
                    [
                        item["source_blob_file_path"],
                        item["source_file_name"],
                        item["status"],
                        item["document_type_name"],
                        table_name,
                        row_index,
                        *[row.get(column) for column in table_columns],
                    ]
                )

    return [
        ("Summary", summary_rows),
        ("Documents", document_rows),
        ("Fields", field_rows),
        ("Tables", table_rows),
    ]


def ground_truth_workbook_sheets(ground_truth_rows: list[dict[str, Any]]) -> list[tuple[str, list[list[Any]]]]:
    rows = [SAMPLE_TRACKING_COLUMNS]
    for item in ground_truth_rows:
        rows.append([item.get(column) for column in SAMPLE_TRACKING_COLUMNS])
    notes = [
        ["note"],
        ["All rows in this workbook are synthetic and derived only from the sibling synthetic-record-generator repo."],
        ["No customer PDFs or production extraction outputs were copied into this workbook."],
        ["The column names intentionally mirror the Sample_Tracking workbook shape used by ixp_pa_sanity/fax_ground_truth_eval.py."],
    ]
    return [("Sample_Tracking", rows), ("Notes", notes)]


def deeprag_workbook_sheets(deeprag_results: dict[str, dict[str, Any]]) -> list[tuple[str, list[list[Any]]]]:
    summary = [["metric", "value"]]
    strategy_counts = Counter(result.get("strategy_used") or "missing_output" for result in deeprag_results.values())
    summary.extend([[f"strategy_{name}", count] for name, count in sorted(strategy_counts.items())])
    summary.append(["document_count", len(deeprag_results)])

    documents = [[
        "file_name",
        "strategy_used",
        "extraction_field_count",
        "warning_count",
        "summary",
    ]]
    extractions = [["file_name", "path", "value"]]
    guesses = [[
        "file_name",
        "path",
        "value",
        "confidence",
        "status",
        "source_pages",
        "current_ixp_value",
        "reasoning",
    ]]

    for file_name, result in sorted(deeprag_results.items()):
        documents.append(
            [
                file_name,
                result.get("strategy_used"),
                len(result.get("extraction") or {}),
                len(result.get("warnings") or []),
                result.get("summary"),
            ]
        )
        for path, value in sorted((result.get("extraction") or {}).items()):
            extractions.append([file_name, path, value])
        for guess in result.get("field_guesses") or []:
            guesses.append(
                [
                    file_name,
                    guess.get("path"),
                    guess.get("value"),
                    guess.get("confidence"),
                    guess.get("status"),
                    ",".join(str(page) for page in (guess.get("source_pages") or [])),
                    guess.get("current_ixp_value"),
                    guess.get("reasoning"),
                ]
            )

    return [
        ("Summary", summary),
        ("Documents", documents),
        ("Extractions", extractions),
        ("FieldGuesses", guesses),
    ]


def comparison_workbook_sheets(
    ground_truth_rows: list[dict[str, Any]],
    document_rows: list[dict[str, Any]],
    field_rows: list[dict[str, Any]],
) -> list[tuple[str, list[list[Any]]]]:
    gt_sheet = [SAMPLE_TRACKING_COLUMNS]
    for item in ground_truth_rows:
        gt_sheet.append([item.get(column) for column in SAMPLE_TRACKING_COLUMNS])

    document_sheet = [list(document_rows[0].keys())]
    for row in document_rows:
        document_sheet.append([row.get(key) for key in document_rows[0].keys()])

    field_sheet = [list(field_rows[0].keys())]
    for row in field_rows:
        field_sheet.append([row.get(key) for key in field_rows[0].keys()])

    ixp_counter = Counter(row["ixp_verdict"] for row in field_rows if row["expected_value"] is not None)
    deeprag_counter = Counter(
        row["deeprag_verdict"]
        for row in field_rows
        if row["expected_value"] is not None and row["deeprag_verdict"] != "not_comparable"
    )
    deeprag_state_counter = Counter(row["deeprag_strategy_used"] for row in document_rows)
    summary = [
        ["metric", "value"],
        ["documents", len(document_rows)],
        ["ixp_match", ixp_counter.get("match", 0)],
        ["ixp_missing", ixp_counter.get("missing", 0)],
        ["ixp_mismatch", ixp_counter.get("mismatch", 0)],
        ["deeprag_match", deeprag_counter.get("match", 0)],
        ["deeprag_missing", deeprag_counter.get("missing", 0)],
        ["deeprag_mismatch", deeprag_counter.get("mismatch", 0)],
    ]
    for strategy, count in sorted(deeprag_state_counter.items()):
        summary.append([f"deeprag_strategy_{strategy}", count])

    return [
        ("Summary", summary),
        ("DocumentSummary", document_sheet),
        ("FieldResults", field_sheet),
        ("GroundTruth", gt_sheet),
    ]


def comparison_summary_markdown(
    packets: list[SyntheticPacket],
    document_rows: list[dict[str, Any]],
    field_rows: list[dict[str, Any]],
) -> str:
    ixp_counter = Counter(row["ixp_verdict"] for row in field_rows if row["expected_value"] is not None)
    deeprag_counter = Counter(
        row["deeprag_verdict"]
        for row in field_rows
        if row["expected_value"] is not None and row["deeprag_verdict"] != "not_comparable"
    )
    strategy_counter = Counter(row["deeprag_strategy_used"] for row in document_rows)
    grounded_docs = sum(1 for row in document_rows if row["deeprag_strategy_used"] in GROUNDED_DEEPRAG_STRATEGIES)
    lines = [
        "# Synthetic IXP Comparison Summary",
        "",
        "All PDFs, JSON payloads, and spreadsheet values in this folder are synthetic.",
        "Nothing here was copied from customer packets or production extraction runs.",
        "",
        f"- Synthetic packets reviewed: `{len(packets)}`",
        f"- Grounded DeepRAG packets: `{grounded_docs}`",
        f"- Fallback DeepRAG packets: `{len(document_rows) - grounded_docs}`",
        "",
        "## IXP Field Verdicts",
        "",
        f"- match: `{ixp_counter.get('match', 0)}`",
        f"- missing: `{ixp_counter.get('missing', 0)}`",
        f"- mismatch: `{ixp_counter.get('mismatch', 0)}`",
        f"- unexpected_value: `{ixp_counter.get('unexpected_value', 0)}`",
        "",
        "## DeepRAG Field Verdicts",
        "",
        f"- match: `{deeprag_counter.get('match', 0)}`",
        f"- missing: `{deeprag_counter.get('missing', 0)}`",
        f"- mismatch: `{deeprag_counter.get('mismatch', 0)}`",
        f"- not_comparable: `{sum(1 for row in field_rows if row['deeprag_verdict'] == 'not_comparable')}`",
        "",
        "## DeepRAG Strategies",
        "",
    ]
    for strategy, count in sorted(strategy_counter.items()):
        lines.append(f"- {strategy}: `{count}`")
    return "\n".join(lines) + "\n"


def percentage(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0%"
    return f"{(numerator / denominator) * 100:.0f}%"


def field_hotspots(field_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_path: dict[str, Counter[str]] = {}
    for row in field_rows:
        path = row["path"]
        counter = by_path.setdefault(path, Counter())
        counter[f"ixp_{row['ixp_verdict']}"] += 1
        counter[f"deeprag_{row['deeprag_verdict']}"] += 1
    items: list[dict[str, Any]] = []
    for path, counter in by_path.items():
        items.append(
            {
                "path": path,
                "ixp_match": counter.get("ixp_match", 0),
                "ixp_missing": counter.get("ixp_missing", 0),
                "ixp_mismatch": counter.get("ixp_mismatch", 0),
                "deeprag_match": counter.get("deeprag_match", 0),
                "deeprag_missing": counter.get("deeprag_missing", 0),
                "deeprag_mismatch": counter.get("deeprag_mismatch", 0),
                "deeprag_not_comparable": counter.get("deeprag_not_comparable", 0),
            }
        )
    items.sort(
        key=lambda item: (
            item["ixp_missing"] + item["ixp_mismatch"],
            item["deeprag_match"],
            item["path"],
        ),
        reverse=True,
    )
    return items


def document_bar(match_count: int, missing_count: int, mismatch_count: int) -> str:
    total = max(match_count + missing_count + mismatch_count, 1)
    match_width = (match_count / total) * 100
    missing_width = (missing_count / total) * 100
    mismatch_width = (mismatch_count / total) * 100
    return (
        '<div class="stacked-bar">'
        f'<span class="bar-match" style="width:{match_width:.2f}%"></span>'
        f'<span class="bar-missing" style="width:{missing_width:.2f}%"></span>'
        f'<span class="bar-mismatch" style="width:{mismatch_width:.2f}%"></span>'
        "</div>"
    )


def comparison_dashboard_html(
    output_dir: Path,
    packets: list[SyntheticPacket],
    document_rows: list[dict[str, Any]],
    field_rows: list[dict[str, Any]],
) -> str:
    prompt_review = load_current_ixp_prompt_review()
    ixp_counter = Counter(row["ixp_verdict"] for row in field_rows if row["expected_value"] is not None)
    deeprag_counter = Counter(
        row["deeprag_verdict"]
        for row in field_rows
        if row["expected_value"] is not None and row["deeprag_verdict"] != "not_comparable"
    )
    strategy_counter = Counter(row["deeprag_strategy_used"] for row in document_rows)
    grounded_docs = sum(1 for row in document_rows if row["deeprag_strategy_used"] in GROUNDED_DEEPRAG_STRATEGIES)
    ixp_total = ixp_counter.get("match", 0) + ixp_counter.get("missing", 0) + ixp_counter.get("mismatch", 0)
    deeprag_total = deeprag_counter.get("match", 0) + deeprag_counter.get("missing", 0) + deeprag_counter.get("mismatch", 0)
    hotspot_rows = field_hotspots(field_rows)[:10]

    metric_cards = [
        ("Synthetic Packets", len(packets), "Synthetic source PDFs pulled only from the sibling generator repo."),
        ("Grounded DeepRAG", grounded_docs, "Grounded second-pass runs that produced comparable extraction output."),
        ("Fallback Cases", len(document_rows) - grounded_docs, "Included intentionally so the walkthrough shows non-comparable behavior too."),
        ("IXP Match Rate", percentage(ixp_counter.get("match", 0), ixp_total), "Field-level agreement against the fabricated ground truth."),
        ("DeepRAG Match Rate", percentage(deeprag_counter.get("match", 0), deeprag_total), "Comparable grounded field-level agreement against the same truth set."),
        ("Synthetic Guardrail", "0 customer PDFs", "No customer packets or production extraction outputs were copied into this bundle."),
    ]

    metric_cards_html = "".join(
        (
            '<article class="metric-card">'
            f'<div class="metric-label">{html_text(label)}</div>'
            f'<div class="metric-value">{html_text(value)}</div>'
            f'<p>{html_text(description)}</p>'
            "</article>"
        )
        for label, value, description in metric_cards
    )

    document_cards_html = []
    for packet, row in zip(packets, document_rows):
        badge_class = "badge-grounded" if row["deeprag_strategy_used"] in GROUNDED_DEEPRAG_STRATEGIES else "badge-fallback"
        pdf_href = packet.source_pdf_path.relative_to(output_dir).as_posix()
        json_href = packet.source_json_path.relative_to(output_dir).as_posix()
        document_cards_html.append(
            "".join(
                [
                    '<article class="document-card">',
                    '<div class="document-head">',
                    f'<div><h3>{html_text(row["file_name"])}</h3><p>{html_text(packet.source_family)} · {html_text(row["doc_type_id_vs"])}</p></div>',
                    f'<span class="badge {badge_class}">{html_text(row["deeprag_strategy_used"])}</span>',
                    "</div>",
                    '<div class="doc-metrics">',
                    f'<div><span class="micro-label">IXP</span><strong>{html_text(row["ixp_match_count"])} match / {html_text(row["ixp_missing_count"])} missing / {html_text(row["ixp_mismatch_count"])} mismatch</strong></div>',
                    f'<div><span class="micro-label">DeepRAG</span><strong>{html_text(row["deeprag_match_count"])} match / {html_text(row["deeprag_missing_count"])} missing / {html_text(row["deeprag_mismatch_count"])} mismatch</strong></div>',
                    "</div>",
                    document_bar(row["ixp_match_count"], row["ixp_missing_count"], row["ixp_mismatch_count"]),
                    document_bar(row["deeprag_match_count"], row["deeprag_missing_count"], row["deeprag_mismatch_count"]),
                    '<div class="doc-links">',
                    f'<a href="{html_text(pdf_href)}" class="ghost-link">Open Synthetic PDF</a>',
                    f'<a href="{html_text(json_href)}" class="ghost-link">Open Synthetic JSON</a>',
                    f'<a href="{html_text(IXP_WORKBOOK_NAME)}" class="ghost-link">Open IXP workbook</a>',
                    f'<a href="{html_text(DEEPRAG_WORKBOOK_NAME)}" class="ghost-link">Open DeepRAG workbook</a>',
                    "</div>",
                    "</article>",
                ]
            )
        )

    hotspot_rows_html = "".join(
        (
            "<tr>"
            f"<td>{html_text(item['path'])}</td>"
            f"<td>{html_text(item['ixp_match'])}</td>"
            f"<td>{html_text(item['ixp_missing'])}</td>"
            f"<td>{html_text(item['ixp_mismatch'])}</td>"
            f"<td>{html_text(item['deeprag_match'])}</td>"
            f"<td>{html_text(item['deeprag_missing'])}</td>"
            f"<td>{html_text(item['deeprag_mismatch'])}</td>"
            f"<td>{html_text(item['deeprag_not_comparable'])}</td>"
            "</tr>"
        )
        for item in hotspot_rows
    )

    strategy_rows_html = "".join(
        (
            "<tr>"
            f"<td>{html_text(strategy)}</td>"
            f"<td>{html_text(count)}</td>"
            "</tr>"
        )
        for strategy, count in sorted(strategy_counter.items())
    )

    source_rows_html = "".join(
        (
            "<tr>"
            f"<td>{html_text(packet.file_stem)}</td>"
            f"<td>{html_text(packet.source_family)}</td>"
            f'<td><a href="{html_text(packet.source_pdf_path.relative_to(output_dir).as_posix())}">{html_text(packet.source_pdf_path.name)}</a></td>'
            f'<td><a href="{html_text(packet.source_json_path.relative_to(output_dir).as_posix())}">{html_text(packet.source_json_path.name)}</a></td>'
            "</tr>"
        )
        for packet in packets
    )

    prompt_cards_html = "".join(
        (
            '<article class="prompt-card">'
            f'<div class="prompt-meta"><span class="priority-chip priority-{html_text(item["priority"])}">{html_text(item["priority"])}</span><span>{html_text(item["target"])}</span></div>'
            '<div class="prompt-columns">'
            '<div>'
            '<h3>Current v5 Prompt</h3>'
            f'<pre>{html_text(item["current_prompt"])}</pre>'
            "</div>"
            '<div>'
            '<h3>Suggested Prompt Change</h3>'
            f'<pre>{html_text(item["proposed_prompt"])}</pre>'
            f'<p class="prompt-why">{html_text(item["why"])}</p>'
            "</div>"
            "</div>"
            "</article>"
        )
        for item in prompt_review["prompt_changes"]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Synthetic IXP Comparison Dashboard</title>
  <style>
    :root {{
      --bg: #f5efe4;
      --panel: rgba(255, 252, 247, 0.82);
      --panel-strong: rgba(255, 252, 247, 0.95);
      --ink: #182126;
      --muted: #5d675f;
      --line: rgba(24, 33, 38, 0.12);
      --match: #1f8f6a;
      --missing: #d98e04;
      --mismatch: #b24a2f;
      --accent: #0f6d7a;
      --accent-soft: rgba(15, 109, 122, 0.12);
      --fallback: #6c4a97;
      --shadow: 0 18px 50px rgba(43, 34, 19, 0.12);
      --radius-xl: 28px;
      --radius-lg: 18px;
      --radius-sm: 12px;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(15, 109, 122, 0.22), transparent 30%),
        radial-gradient(circle at top right, rgba(217, 142, 4, 0.18), transparent 24%),
        linear-gradient(180deg, #f8f2e8 0%, #f2ebdf 45%, #ece4d7 100%);
      min-height: 100vh;
    }}

    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(24, 33, 38, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(24, 33, 38, 0.03) 1px, transparent 1px);
      background-size: 32px 32px;
      mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.45), transparent 90%);
    }}

    .page {{
      width: min(1180px, calc(100vw - 32px));
      margin: 28px auto 56px;
      position: relative;
      z-index: 1;
    }}

    .hero {{
      background: linear-gradient(135deg, rgba(255, 252, 247, 0.96), rgba(240, 247, 246, 0.9));
      border: 1px solid rgba(24, 33, 38, 0.08);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow);
      padding: 28px;
      overflow: hidden;
      position: relative;
    }}

    .hero::after {{
      content: "";
      position: absolute;
      width: 280px;
      height: 280px;
      top: -120px;
      right: -80px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(15, 109, 122, 0.18), transparent 68%);
    }}

    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(24, 33, 38, 0.05);
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}

    h1, h2, h3 {{
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
      margin: 0;
      line-height: 1.05;
    }}

    h1 {{
      margin-top: 18px;
      font-size: clamp(2.4rem, 4vw, 4.4rem);
      max-width: 10ch;
    }}

    .hero-grid {{
      display: grid;
      grid-template-columns: 1.3fr 0.9fr;
      gap: 24px;
      margin-top: 20px;
      align-items: end;
    }}

    .hero-copy p,
    .hero-callout p,
    .metric-card p,
    .section-copy {{
      color: var(--muted);
      line-height: 1.55;
      margin: 0;
    }}

    .hero-callout {{
      background: rgba(255, 252, 247, 0.8);
      border: 1px solid rgba(24, 33, 38, 0.08);
      border-radius: var(--radius-lg);
      padding: 18px;
      backdrop-filter: blur(12px);
    }}

    .hero-callout strong {{
      display: block;
      font-size: 1.65rem;
      margin-bottom: 8px;
    }}

    .action-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
    }}

    .pill-link,
    .ghost-link {{
      text-decoration: none;
      color: inherit;
      border-radius: 999px;
      padding: 10px 14px;
      border: 1px solid var(--line);
      background: rgba(255, 252, 247, 0.76);
    }}

    .pill-link {{
      background: linear-gradient(135deg, #123f48, #0f6d7a);
      color: white;
      border-color: transparent;
      box-shadow: 0 12px 24px rgba(15, 109, 122, 0.18);
    }}

    .disabled-link {{
      opacity: 0.58;
    }}

    section {{
      margin-top: 22px;
      background: var(--panel);
      border: 1px solid rgba(24, 33, 38, 0.08);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow);
      padding: 24px;
      backdrop-filter: blur(8px);
    }}

    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
      margin-bottom: 18px;
    }}

    .section-head p {{
      margin: 10px 0 0;
      color: var(--muted);
      max-width: 68ch;
    }}

    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}

    .metric-card {{
      background: var(--panel-strong);
      border: 1px solid rgba(24, 33, 38, 0.08);
      border-radius: var(--radius-lg);
      padding: 16px;
      min-height: 160px;
    }}

    .metric-label {{
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 16px;
    }}

    .metric-value {{
      font-size: clamp(1.8rem, 2.8vw, 2.6rem);
      font-weight: 700;
      margin-bottom: 12px;
    }}

    .split-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}

    .compare-panel {{
      background: var(--panel-strong);
      border: 1px solid rgba(24, 33, 38, 0.08);
      border-radius: var(--radius-lg);
      padding: 18px;
    }}

    .compare-panel h3 {{
      font-size: 1.6rem;
      margin-bottom: 12px;
    }}

    .stat-list {{
      display: grid;
      gap: 12px;
    }}

    .stat-row {{
      display: grid;
      grid-template-columns: 110px 1fr 48px;
      gap: 10px;
      align-items: center;
      font-size: 0.96rem;
    }}

    .stat-row strong {{
      font-size: 1rem;
    }}

    .track {{
      height: 12px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(24, 33, 38, 0.08);
    }}

    .fill {{
      height: 100%;
      border-radius: inherit;
    }}

    .fill.match {{
      background: var(--match);
    }}

    .fill.missing {{
      background: var(--missing);
    }}

    .fill.mismatch {{
      background: var(--mismatch);
    }}

    .documents-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}

    .document-card {{
      background: var(--panel-strong);
      border: 1px solid rgba(24, 33, 38, 0.08);
      border-radius: var(--radius-lg);
      padding: 18px;
      display: grid;
      gap: 14px;
    }}

    .document-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }}

    .document-head p {{
      color: var(--muted);
      margin: 6px 0 0;
    }}

    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      white-space: nowrap;
    }}

    .badge-grounded {{
      background: rgba(31, 143, 106, 0.14);
      color: var(--match);
    }}

    .badge-fallback {{
      background: rgba(108, 74, 151, 0.14);
      color: var(--fallback);
    }}

    .doc-metrics {{
      display: grid;
      gap: 10px;
    }}

    .micro-label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 4px;
    }}

    .stacked-bar {{
      display: flex;
      overflow: hidden;
      height: 12px;
      border-radius: 999px;
      background: rgba(24, 33, 38, 0.08);
    }}

    .bar-match {{
      background: var(--match);
    }}

    .bar-missing {{
      background: var(--missing);
    }}

    .bar-mismatch {{
      background: var(--mismatch);
    }}

    .doc-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
    }}

    th, td {{
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}

    th {{
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-weight: 700;
    }}

    tbody tr:hover {{
      background: rgba(15, 109, 122, 0.05);
    }}

    .table-wrap {{
      overflow-x: auto;
      border-radius: var(--radius-lg);
      background: var(--panel-strong);
      border: 1px solid rgba(24, 33, 38, 0.08);
    }}

    .footer-note {{
      color: var(--muted);
      font-size: 0.94rem;
      margin-top: 12px;
    }}

    .prompt-intro {{
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 16px;
      margin-bottom: 16px;
    }}

    .prompt-summary-box,
    .prompt-card {{
      background: var(--panel-strong);
      border: 1px solid rgba(24, 33, 38, 0.08);
      border-radius: var(--radius-lg);
      padding: 18px;
    }}

    .prompt-summary-box pre,
    .prompt-card pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: "SFMono-Regular", "Menlo", "Monaco", monospace;
      font-size: 0.9rem;
      line-height: 1.55;
      background: rgba(24, 33, 38, 0.04);
      padding: 14px;
      border-radius: var(--radius-sm);
      border: 1px solid rgba(24, 33, 38, 0.06);
    }}

    .prompt-stack {{
      display: grid;
      gap: 14px;
    }}

    .prompt-meta {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      margin-bottom: 14px;
      font-size: 0.95rem;
      font-weight: 700;
    }}

    .priority-chip {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-weight: 700;
    }}

    .priority-highest {{
      background: rgba(178, 74, 47, 0.12);
      color: var(--mismatch);
    }}

    .priority-medium {{
      background: rgba(217, 142, 4, 0.14);
      color: #996200;
    }}

    .priority-cross-cutting {{
      background: rgba(15, 109, 122, 0.12);
      color: var(--accent);
    }}

    .prompt-columns {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}

    .prompt-columns h3,
    .prompt-summary-box h3 {{
      font-size: 1.15rem;
      margin-bottom: 12px;
    }}

    .prompt-why {{
      margin: 12px 0 0;
      color: var(--muted);
      line-height: 1.5;
    }}

    @media (max-width: 980px) {{
      .hero-grid,
      .metrics-grid,
      .split-grid,
      .documents-grid,
      .prompt-intro,
      .prompt-columns {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <span class="eyebrow">Synthetic Visual Comparison</span>
      <div class="hero-grid">
        <div class="hero-copy">
          <h1>IXP vs DeepRAG against fake ground truth.</h1>
          <p class="section-copy">This dashboard is a visual walkthrough of the same extraction pipeline used in this repo, but populated only with synthetic PDFs and fabricated reviewer spreadsheets. It is meant for a fast demo, not production scoring.</p>
          <div class="action-row">
            <a class="pill-link" href="{html_text(COMPARISON_WORKBOOK_NAME)}">Open Comparison Workbook</a>
            <a class="ghost-link" href="{html_text(IXP_WORKBOOK_NAME)}">Open IXP Workbook</a>
            <a class="ghost-link" href="{html_text(DEEPRAG_WORKBOOK_NAME)}">Open DeepRAG Workbook</a>
            <a class="ghost-link" href="{html_text(GROUND_TRUTH_WORKBOOK_NAME)}">Open Ground Truth Workbook</a>
          </div>
        </div>
        <aside class="hero-callout">
          <strong>0 real packet data</strong>
          <p>Everything shown here was derived from synthetic PDFs located in the sibling generator repo and written into fresh fake spreadsheets under <code>{html_text(output_dir.name)}</code>.</p>
        </aside>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>Scorecards</h2>
          <p>Top-line metrics for the synthetic packet set. Two packets simulate grounded DeepRAG success and one packet simulates an IXP-only fallback.</p>
        </div>
      </div>
      <div class="metrics-grid">{metric_cards_html}</div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>Field-Level Outcome</h2>
          <p>These bars compare each system against the fabricated ground truth spreadsheet, using the same canonical field-path comparison style as the repo's evaluation helpers.</p>
        </div>
      </div>
      <div class="split-grid">
        <article class="compare-panel">
          <h3>IXP</h3>
          <div class="stat-list">
            <div class="stat-row"><strong>Match</strong><div class="track"><div class="fill match" style="width:{percentage(ixp_counter.get('match', 0), ixp_total)}"></div></div><span>{html_text(ixp_counter.get('match', 0))}</span></div>
            <div class="stat-row"><strong>Missing</strong><div class="track"><div class="fill missing" style="width:{percentage(ixp_counter.get('missing', 0), ixp_total)}"></div></div><span>{html_text(ixp_counter.get('missing', 0))}</span></div>
            <div class="stat-row"><strong>Mismatch</strong><div class="track"><div class="fill mismatch" style="width:{percentage(ixp_counter.get('mismatch', 0), ixp_total)}"></div></div><span>{html_text(ixp_counter.get('mismatch', 0))}</span></div>
          </div>
        </article>
        <article class="compare-panel">
          <h3>DeepRAG</h3>
          <div class="stat-list">
            <div class="stat-row"><strong>Match</strong><div class="track"><div class="fill match" style="width:{percentage(deeprag_counter.get('match', 0), deeprag_total)}"></div></div><span>{html_text(deeprag_counter.get('match', 0))}</span></div>
            <div class="stat-row"><strong>Missing</strong><div class="track"><div class="fill missing" style="width:{percentage(deeprag_counter.get('missing', 0), deeprag_total)}"></div></div><span>{html_text(deeprag_counter.get('missing', 0))}</span></div>
            <div class="stat-row"><strong>Mismatch</strong><div class="track"><div class="fill mismatch" style="width:{percentage(deeprag_counter.get('mismatch', 0), deeprag_total)}"></div></div><span>{html_text(deeprag_counter.get('mismatch', 0))}</span></div>
          </div>
          <p class="footer-note">`not_comparable` rows are excluded from the comparable DeepRAG denominator because the fallback packet intentionally does not produce grounded extraction output.</p>
        </article>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>Per-Packet Readout</h2>
          <p>Each card shows how the baseline IXP extraction compared with the grounded second pass for the same synthetic packet.</p>
        </div>
      </div>
      <div class="documents-grid">{''.join(document_cards_html)}</div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>Field Hotspots</h2>
          <p>Fields at the top are where IXP struggled most often in the synthetic walkthrough. In this demo set, DeepRAG mostly closes those gaps except for the deliberate fallback packet.</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Field Path</th>
              <th>IXP Match</th>
              <th>IXP Missing</th>
              <th>IXP Mismatch</th>
              <th>DeepRAG Match</th>
              <th>DeepRAG Missing</th>
              <th>DeepRAG Mismatch</th>
              <th>DeepRAG N/C</th>
            </tr>
          </thead>
          <tbody>{hotspot_rows_html}</tbody>
        </table>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>Current IXP Prompt And Suggested Prompt-Level Changes</h2>
          <p>This section uses a sanitized prompt snapshot plus the repo's local prompt recommendation notes. It shows the current prompt surface the dashboard is assuming and the prompt edits already being suggested locally.</p>
        </div>
      </div>
      <div class="prompt-intro">
        <article class="prompt-summary-box">
          <h3>Current Global Prompt</h3>
          <pre>{html_text(prompt_review["general_prompt"])}</pre>
        </article>
        <article class="prompt-summary-box">
          <h3>Prompt Sources</h3>
          <p class="section-copy">Current taxonomy source:</p>
          <pre>{html_text(prompt_review["taxonomy_path"])}</pre>
          <p class="section-copy" style="margin-top:12px;">Prompt change recommendations source:</p>
          <pre>{html_text(prompt_review["prompt_recommendations_path"])}</pre>
        </article>
      </div>
      <div class="prompt-stack">{prompt_cards_html}</div>
    </section>

    <section>
      <div class="split-grid">
        <div>
          <div class="section-head">
            <div>
              <h2>Strategy Mix</h2>
              <p>Intentional spread of grounded and fallback modes.</p>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Strategy</th><th>Packets</th></tr></thead>
              <tbody>{strategy_rows_html}</tbody>
            </table>
          </div>
        </div>
        <div>
          <div class="section-head">
            <div>
              <h2>Source Inventory</h2>
              <p>Every source file below lives in the sibling synthetic generator repo.</p>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Packet</th><th>Family</th><th>PDF</th><th>JSON</th></tr></thead>
              <tbody>{source_rows_html}</tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  </main>
</body>
</html>
"""


def walkthrough_markdown(output_dir: Path, packets: list[SyntheticPacket], document_rows: list[dict[str, Any]]) -> str:
    grounded_docs = sum(1 for row in document_rows if row["deeprag_strategy_used"] in GROUNDED_DEEPRAG_STRATEGIES)
    ixp_json_ref = output_relative_path(output_dir / "synthetic_ixp_results.json", output_dir)
    ixp_workbook_ref = output_relative_path(output_dir / IXP_WORKBOOK_NAME, output_dir)
    deeprag_json_ref = output_relative_path(output_dir / "synthetic_deeprag_results.json", output_dir)
    deeprag_workbook_ref = output_relative_path(output_dir / DEEPRAG_WORKBOOK_NAME, output_dir)
    ground_truth_ref = output_relative_path(output_dir / GROUND_TRUTH_WORKBOOK_NAME, output_dir)
    comparison_ref = output_relative_path(output_dir / COMPARISON_WORKBOOK_NAME, output_dir)
    html_dashboard_ref = output_relative_path(output_dir / HTML_DASHBOARD_NAME, output_dir)
    document_summary_ref = output_relative_path(output_dir / "document_summary.csv", output_dir)
    field_results_ref = output_relative_path(output_dir / "field_results.csv", output_dir)
    lines = [
        "# Synthetic IXP Walkthrough",
        "",
        "This folder is a synthetic-only walkthrough for the repo's current UM Intake flow:",
        "",
        "`PDF -> IXP normalization -> DeepRAG second pass -> spreadsheet comparison`",
        "",
        "## Guardrails",
        "",
        "- Every source PDF in this package was freshly generated from the sibling `synthetic-record-generator` repo.",
        "- The generated PDFs and their paired JSON files were copied into this walkthrough folder so the HTML demo can link to them directly.",
        "- Every spreadsheet row in this package is synthetic and fabricated from those generated packets.",
        "- No customer PDFs or production extraction outputs were copied into these artifacts.",
        "",
        "## Source Packets",
        "",
        "| Packet | Source Family | PDF | JSON |",
        "| --- | --- | --- | --- |",
    ]
    for packet in packets:
        lines.append(
            f"| `{packet.file_stem}` | `{packet.source_family}` | `{output_relative_path(packet.source_pdf_path, output_dir)}` | `{output_relative_path(packet.source_json_path, output_dir)}` |"
        )

    lines.extend(
        [
            "",
            "## How The Real Repo Flow Maps To These Synthetic Files",
            "",
            "1. The first stage mirrors a baseline IXP extraction run that reads PDFs and writes `normalized_fields` plus `normalized_tables`.",
            f"   For this offline walkthrough, that output shape is mirrored in `{ixp_json_ref}` and `{ixp_workbook_ref}`.",
            "2. The second stage mirrors a coded second pass that re-reads the document, uses IXP fields as hints, and returns `extraction`, `field_guesses`, and `strategy_used`.",
            f"   For this walkthrough, that shape is mirrored in `{deeprag_json_ref}` and `{deeprag_workbook_ref}`.",
            "3. The third stage mirrors the comparison pattern that aligns spreadsheet truth against both the baseline IXP output and the second-pass output using canonical field paths.",
            f"   For this walkthrough, the synthetic truth sheet is `{ground_truth_ref}` and the final comparison workbook is `{comparison_ref}`.",
            "",
            "## Synthetic Output Files",
            "",
            f"- Ground truth workbook: `{ground_truth_ref}`",
            f"- IXP output workbook: `{ixp_workbook_ref}`",
            f"- DeepRAG output workbook: `{deeprag_workbook_ref}`",
            f"- Comparison workbook: `{comparison_ref}`",
            f"- HTML dashboard: `{html_dashboard_ref}`",
            f"- Document summary CSV: `{document_summary_ref}`",
            f"- Field results CSV: `{field_results_ref}`",
            "",
            "## What To Look At First",
            "",
            f"- `synthetic_ground_truth.xlsx`: reviewer-entered expected values using the same `Sample_Tracking` sheet shape as the real eval flow.",
            f"- `synthetic_ixp_results.xlsx`: normalized IXP output in the same `Summary / Documents / Fields / Tables` structure the bucket runner writes.",
            f"- `synthetic_deeprag_results.xlsx`: second-pass extracted field paths plus field-level reasoning/evidence metadata.",
            f"- `synthetic_ixp_deeprag_ground_truth_comparison.xlsx`: side-by-side reviewer workbook showing match / missing / mismatch outcomes.",
            "",
            "## Rerun",
            "",
            "```bash",
            "python3 scripts/build_synthetic_ixp_walkthrough.py",
            "```",
            "",
            "That command regenerates the synthetic PDFs first, then rebuilds the synthetic spreadsheets, comparison outputs, and HTML dashboard.",
            "It requires the sibling `synthetic-record-generator` repo next to this repo.",
            "",
            "## Notes",
            "",
            f"- This package intentionally includes `{grounded_docs}` grounded DeepRAG cases and `{len(document_rows) - grounded_docs}` fallback case so the comparison workbook shows both normal and non-comparable behavior.",
            "- Several IXP values are intentionally left blank or slightly wrong so the comparison sheets make the IXP-vs-DeepRAG delta obvious during a walkthrough.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_ground_truth_csv_rows(ground_truth_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return ground_truth_rows


def main() -> None:
    args = parse_args()
    synthetic_root = Path(args.synthetic_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_sources = generate_demo_packet_files(output_dir)
    packets = build_packets(generated_sources)
    ground_truth_rows = build_ground_truth_rows(packets)
    source_manifest = build_source_manifest(packets, output_dir)
    ixp_run = build_ixp_run_payload(packets, output_dir)
    deeprag_results = build_deeprag_payload(packets)
    ixp_results_by_name = {item["source_file_name"].removesuffix(".pdf"): item for item in ixp_run["results"]}

    field_rows = build_field_rows(packets, ixp_results_by_name, deeprag_results)
    document_rows = build_document_rows(packets, field_rows, deeprag_results, output_dir)

    write_json(output_dir / "source_manifest.json", source_manifest)
    write_json(output_dir / "synthetic_ixp_results.json", ixp_run)
    write_json(output_dir / "synthetic_deeprag_results.json", deeprag_results)
    write_csv(output_dir / "synthetic_ground_truth_sample_tracking.csv", build_ground_truth_csv_rows(ground_truth_rows))
    write_csv(output_dir / "document_summary.csv", document_rows)
    write_csv(output_dir / "field_results.csv", field_rows)
    (output_dir / "comparison_summary.md").write_text(
        comparison_summary_markdown(packets, document_rows, field_rows),
        encoding="utf-8",
    )
    (output_dir / HTML_DASHBOARD_NAME).write_text(
        comparison_dashboard_html(output_dir, packets, document_rows, field_rows),
        encoding="utf-8",
    )
    (output_dir / "walkthrough.md").write_text(
        walkthrough_markdown(output_dir, packets, document_rows),
        encoding="utf-8",
    )

    ground_truth_workbook = output_dir / GROUND_TRUTH_WORKBOOK_NAME
    ixp_workbook = output_dir / IXP_WORKBOOK_NAME
    deeprag_workbook = output_dir / DEEPRAG_WORKBOOK_NAME
    comparison_workbook = output_dir / COMPARISON_WORKBOOK_NAME

    write_xlsx(ground_truth_workbook, ground_truth_workbook_sheets(ground_truth_rows))
    write_xlsx(ixp_workbook, ixp_workbook_sheets(ixp_run))
    write_xlsx(deeprag_workbook, deeprag_workbook_sheets(deeprag_results))
    write_xlsx(comparison_workbook, comparison_workbook_sheets(ground_truth_rows, document_rows, field_rows))

    workbook_validation = {
        ground_truth_workbook.name: validate_xlsx(ground_truth_workbook),
        ixp_workbook.name: validate_xlsx(ixp_workbook),
        deeprag_workbook.name: validate_xlsx(deeprag_workbook),
        comparison_workbook.name: validate_xlsx(comparison_workbook),
    }

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "packet_count": len(packets),
                "grounded_deeprag_packets": sum(
                    1 for row in document_rows if row["deeprag_strategy_used"] in GROUNDED_DEEPRAG_STRATEGIES
                ),
                "workbooks": workbook_validation,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
