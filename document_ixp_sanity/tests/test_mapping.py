from __future__ import annotations

import json
from pathlib import Path

from document_ixp_sanity.evaluator import IXPEvaluator, normalize_text, remove_punctuation
from document_ixp_sanity.main import load_mapping_config


def test_normalize_text() -> None:
    assert normalize_text("John A. Doe", mode="lower") == "john a. doe"
    assert remove_punctuation("John A. Doe!") == "John A Doe"


def test_candidate_keys_from_mapping() -> None:
    mapping = {
        "canonical_fields": {
            "patient_name": {
                "ixp_candidates": ["patientName", "name"],
                "acceptance_threshold": 0.8,
            }
        }
    }
    evaluator = IXPEvaluator(mapping)
    ixp_payload = {"patientName": "John Doe", "other": "x"}
    idx = evaluator._index_ixp(ixp_payload)
    candidates = evaluator.candidate_ixp_keys(
        idx,
        mapping["canonical_fields"]["patient_name"],
        field_name="patient_name",
    )
    assert any(key == "patientName" for key, _ in candidates)


def test_mapping_example_loads() -> None:
    mapping_path = Path(__file__).resolve().parents[1] / "mapping_config.example.json"
    mapping = load_mapping_config(str(mapping_path))
    assert "patient_dob" in mapping["canonical_fields"]
    sample_path = Path(__file__).resolve().parents[1] / "sample_ixp" / "sample1_ixp.json"
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    evaluator = IXPEvaluator(mapping)
    idx = evaluator._index_ixp(payload)
    candidates = evaluator.candidate_ixp_keys(
        idx,
        mapping["canonical_fields"]["patient_dob"],
        field_name="patient_dob",
    )
    assert any(key == "dob" for key, _ in candidates)
