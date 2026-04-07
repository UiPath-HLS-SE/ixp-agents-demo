from __future__ import annotations

import json
from pathlib import Path

from document_ixp_sanity.evaluator import IXPEvaluator
from document_ixp_sanity.main import load_mapping_config


def _load_sample_gt() -> list[dict[str, str]]:
    sample_path = Path(__file__).resolve().parents[1] / "sample_gt" / "sample1.jsonl"
    return [json.loads(line) for line in sample_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_sample_ixp() -> dict:
    sample_path = Path(__file__).resolve().parents[1] / "sample_ixp" / "sample1_ixp.json"
    return json.loads(sample_path.read_text(encoding="utf-8"))


def test_scoring_exact() -> None:
    mapping = {
        "canonical_fields": {
            "patient_name": {
                "ixp_candidates": ["patientName"],
                "acceptance_threshold": 0.8,
            }
        }
    }
    evaluator = IXPEvaluator(mapping)
    gt = [{"doc_id": "DOC-SAMPLE-1", "canonical_field": "patient_name", "value": "John Doe"}]
    ixp = {"extracted_fields": [{"field_name": "patientName", "value": "John Doe", "confidence": 0.9}]}
    report = evaluator.evaluate("DOC-SAMPLE-1", ixp, gt)
    field = report["fields"][0]
    assert field["verdict"] == "PASS"
    assert field["confidence"] > 0.8


def test_scoring_partial() -> None:
    mapping = {
        "canonical_fields": {
            "patient_name": {
                "ixp_candidates": ["patientName"],
                "normalize": "lower",
                "acceptance_threshold": 0.95,
            }
        }
    }
    evaluator = IXPEvaluator(mapping)
    gt = [{"doc_id": "DOC-SAMPLE-1", "canonical_field": "patient_name", "value": "John A. Doe"}]
    ixp = {"extracted_fields": [{"field_name": "patientName", "value": "John Doe", "confidence": 0.9}]}
    report = evaluator.evaluate("DOC-SAMPLE-1", ixp, gt)
    field = report["fields"][0]
    assert field["error_class"] in ("Partial", "NearMatch", "WrongValue", "LowConfidence", "FormatMismatch")


def test_date_normalization_passes_and_metrics_include_coverage() -> None:
    mapping_path = Path(__file__).resolve().parents[1] / "mapping_config.example.json"
    mapping = load_mapping_config(str(mapping_path))
    evaluator = IXPEvaluator(mapping)
    report = evaluator.evaluate("DOC-SAMPLE-1", _load_sample_ixp(), _load_sample_gt())

    dob_field = next(field for field in report["fields"] if field["canonical_field"] == "patient_dob")
    metrics = evaluator.build_metrics(report)

    assert dob_field["verdict"] == "PASS"
    assert dob_field["error_class"] == "Match"
    assert metrics["coverage"] == 1.0
    assert metrics["avg_confidence"] > 0.0
