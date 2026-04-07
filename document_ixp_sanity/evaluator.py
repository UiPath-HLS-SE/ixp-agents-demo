from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Optional

try:
    from rapidfuzz import fuzz
except Exception:
    from difflib import SequenceMatcher

    class _FallbackFuzz:
        @staticmethod
        def ratio(left: str, right: str) -> float:
            return SequenceMatcher(None, left, right).ratio() * 100.0

        @staticmethod
        def token_set_ratio(left: str, right: str) -> float:
            left_tokens = set(left.split())
            right_tokens = set(right.split())
            if not left_tokens and not right_tokens:
                return 100.0
            if not left_tokens or not right_tokens:
                return 0.0
            overlap = " ".join(sorted(left_tokens & right_tokens))
            left_only = " ".join(sorted(left_tokens - right_tokens))
            right_only = " ".join(sorted(right_tokens - left_tokens))
            lhs = " ".join(part for part in [overlap, left_only] if part)
            rhs = " ".join(part for part in [overlap, right_only] if part)
            return SequenceMatcher(None, lhs, rhs).ratio() * 100.0

    fuzz = _FallbackFuzz()

from document_ixp_sanity import validators


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        if "value" in value:
            return _safe_text(value.get("value"))
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    if isinstance(value, list):
        return ", ".join(_safe_text(item) for item in value)
    return str(value)


def normalize_text(value: Any, mode: Optional[str] = None) -> str:
    text = unicodedata.normalize("NFKC", _safe_text(value))
    text = re.sub(r"\s+", " ", text).strip()
    if mode == "lower":
        text = text.lower()
    elif mode == "uppercase":
        text = text.upper()
    return text


def remove_punctuation(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text)


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize_text(value, mode="lower"))


def _clamp_confidence(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric > 1.0:
        numeric = numeric / 100.0
    return max(0.0, min(1.0, numeric))


def _candidate_payload(value: Any, *, source_path: str) -> Any:
    if isinstance(value, dict):
        if any(key in value for key in ("value", "text", "content")):
            payload = dict(value)
            payload.setdefault("path", source_path)
            return payload
        return {"value": value, "path": source_path}
    return value


def _escape_markdown_cell(value: Any) -> str:
    text = _safe_text(value) or "-"
    return text.replace("|", "\\|").replace("\n", " ")


class IXPEvaluator:
    def __init__(self, mapping: dict[str, Any]):
        self.mapping = mapping or {}
        self.global_cfg = self.mapping.get("global", {})
        self.default_threshold = float(self.global_cfg.get("default_acceptance_threshold", 0.8))
        self.key_match_threshold = float(self.global_cfg.get("candidate_key_threshold", 75.0))
        self.fallback_key_threshold = float(self.global_cfg.get("fallback_candidate_key_threshold", 55.0))
        self.ignored_index_keys = {
            _normalized_key(key)
            for key in self.global_cfg.get(
                "ignored_ixp_keys",
                ["confidence", "score", "page", "pages", "document_id", "documentid"],
            )
        }

    def evaluate(self, doc_id: str, ixp_payload: dict[str, Any], ground_truth: Any) -> dict[str, Any]:
        canonical = self.mapping.get("canonical_fields", {})
        report: dict[str, Any] = {"doc_id": doc_id, "fields": []}
        ixp_index = self._index_ixp(ixp_payload)

        for field_name, cfg in canonical.items():
            gt_entry = self._ground_truth_entry(doc_id, ground_truth, field_name)
            gt_value = gt_entry.get("value") if gt_entry else None

            candidates = self.candidate_ixp_keys(ixp_index, cfg, field_name=field_name)
            scored_candidates = []
            for key, ixp_value in candidates:
                signals = self.score_candidate(gt_value, ixp_value, cfg)
                confidence, verdict = self.aggregate_confidence(signals, cfg)
                scored_candidates.append(
                    {
                        "ixp_key": key,
                        "ixp_value": self._candidate_value(ixp_value),
                        "source_path": self._candidate_path(ixp_value),
                        "signals": signals,
                        "confidence": round(confidence, 4),
                        "verdict": verdict,
                    }
                )

            best = max(scored_candidates, key=lambda item: item["confidence"]) if scored_candidates else None

            entry: dict[str, Any] = {
                "canonical_field": field_name,
                "gt_value": gt_value,
                "ground_truth_present": gt_value not in (None, ""),
                "candidates": scored_candidates,
                "best": best,
            }

            if gt_value in (None, ""):
                entry["verdict"] = "MISSING"
                entry["confidence"] = round(best["confidence"], 4) if best else 0.0
                entry["ixp_value"] = best["ixp_value"] if best else None
                entry["error_class"] = "GroundTruthMissing"
            elif not best:
                entry["verdict"] = "MISSING"
                entry["confidence"] = 0.0
                entry["ixp_value"] = None
                entry["error_class"] = "Missing"
            else:
                entry["verdict"] = best["verdict"]
                entry["confidence"] = round(best["confidence"], 4)
                entry["ixp_value"] = best["ixp_value"]
                entry["error_class"] = self.classify_error(
                    gt_value,
                    best["ixp_value"],
                    best["signals"],
                    verdict=best["verdict"],
                )

            report["fields"].append(entry)

        report["summary"] = self._build_summary(report["fields"])
        return report

    def _ground_truth_entry(self, doc_id: str, ground_truth: Any, field_name: str) -> dict[str, Any] | None:
        if isinstance(ground_truth, dict):
            if field_name not in ground_truth:
                return None
            value = ground_truth.get(field_name)
            return {"doc_id": doc_id, "canonical_field": field_name, "value": value}

        if isinstance(ground_truth, list):
            for record in ground_truth:
                if not isinstance(record, dict):
                    continue
                record_doc_id = record.get("doc_id")
                if record.get("canonical_field") != field_name:
                    continue
                if record_doc_id in (None, "", doc_id):
                    return record
        return None

    def _build_summary(self, fields: list[dict[str, Any]]) -> dict[str, Any]:
        counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "MISSING": 0}
        for field in fields:
            verdict = str(field.get("verdict") or "MISSING")
            counts[verdict] = counts.get(verdict, 0) + 1

        fields_with_gt = [field for field in fields if field.get("ground_truth_present")]
        covered_fields = [field for field in fields_with_gt if field.get("ixp_value") not in (None, "", [])]

        return {
            "fields_evaluated": len(fields),
            "fields_with_gt": len(fields_with_gt),
            "fields_passed": counts.get("PASS", 0),
            "verdict_counts": counts,
            "coverage": round(len(covered_fields) / len(fields_with_gt), 4) if fields_with_gt else 0.0,
        }

    def _index_ixp(self, ixp_payload: dict[str, Any]) -> dict[str, list[Any]]:
        index: dict[str, list[Any]] = {}
        seen: set[tuple[str, str]] = set()

        def add_candidate(key: str, value: Any, source_path: str) -> None:
            candidate = _candidate_payload(value, source_path=source_path)
            fingerprint = json.dumps(candidate, sort_keys=True, default=str, ensure_ascii=False)
            if (key, fingerprint) in seen:
                return
            seen.add((key, fingerprint))
            index.setdefault(key, []).append(candidate)

        def walk(node: Any, path: str = "") -> None:
            if isinstance(node, dict):
                if self._looks_like_field_record(node):
                    key = str(node.get("field_name") or node.get("name") or node.get("key"))
                    add_candidate(key, dict(node), path or key)

                for key, value in node.items():
                    child_path = f"{path}.{key}" if path else key
                    if self._is_leaf_value(value) and _normalized_key(str(key)) not in self.ignored_index_keys:
                        add_candidate(str(key), value, child_path)
                    walk(value, child_path)
            elif isinstance(node, list):
                if node and all(not isinstance(item, (dict, list)) for item in node):
                    add_candidate(path.rsplit(".", 1)[-1] or "list_value", node, path or "list_value")
                for index_value, item in enumerate(node):
                    walk(item, f"{path}[{index_value}]")

        walk(ixp_payload)
        return index

    def _looks_like_field_record(self, node: dict[str, Any]) -> bool:
        return (
            isinstance(node, dict)
            and any(key in node for key in ("field_name", "name", "key"))
            and any(key in node for key in ("value", "text", "content"))
        )

    def _is_leaf_value(self, value: Any) -> bool:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return True
        if isinstance(value, list):
            return not value or all(not isinstance(item, (dict, list)) for item in value)
        if isinstance(value, dict):
            return any(key in value for key in ("value", "text", "content"))
        return False

    def candidate_ixp_keys(
        self,
        ixp_index: dict[str, list[Any]],
        field_cfg: dict[str, Any],
        *,
        field_name: str = "",
    ) -> list[tuple[str, Any]]:
        search_terms = self._candidate_search_terms(field_name, field_cfg)
        normalized_terms = {_normalized_key(term) for term in search_terms if term}

        matched_keys: dict[str, tuple[int, float]] = {}
        for key in ixp_index:
            key_norm = _normalized_key(key)
            exact_match = 1 if key_norm in normalized_terms else 0
            fuzzy_match = max(
                (fuzz.ratio(key_norm, term_norm) for term_norm in normalized_terms if term_norm),
                default=0.0,
            )
            if exact_match or fuzzy_match >= self.key_match_threshold:
                matched_keys[key] = (exact_match, float(fuzzy_match))

        if not matched_keys:
            ranked_keys = sorted(
                (
                    (
                        key,
                        max(
                            (fuzz.ratio(_normalized_key(key), term_norm) for term_norm in normalized_terms if term_norm),
                            default=0.0,
                        ),
                    )
                    for key in ixp_index
                ),
                key=lambda item: (-item[1], item[0]),
            )
            matched_keys = {
                key: (0, float(score))
                for key, score in ranked_keys[: max(1, min(3, len(ranked_keys)))]
                if score >= self.fallback_key_threshold
            }

        ordered_keys = sorted(matched_keys, key=lambda key: (-matched_keys[key][0], -matched_keys[key][1], key))
        candidates: list[tuple[str, Any]] = []
        for key in ordered_keys:
            for candidate in ixp_index.get(key, []):
                candidates.append((key, candidate))
        return candidates

    def _candidate_search_terms(self, field_name: str, field_cfg: dict[str, Any]) -> list[str]:
        terms = [field_name]
        explicit = field_cfg.get("ixp_candidates", []) or []
        terms.extend(str(item) for item in explicit if item)

        synonyms = self.global_cfg.get("synonyms", {}) or {}
        known_terms = {_normalized_key(term) for term in terms if term}
        for root_term, aliases in synonyms.items():
            cluster = [str(root_term), *(str(alias) for alias in aliases or [])]
            cluster_norm = {_normalized_key(term) for term in cluster}
            if known_terms & cluster_norm:
                terms.extend(cluster)

        return terms

    def score_candidate(self, gt_value: Any, ixp_value: Any, field_cfg: dict[str, Any]) -> dict[str, Any]:
        raw_ixp_value = self._candidate_value(ixp_value)
        model_confidence = self._candidate_confidence(ixp_value)
        gt_base = normalize_text(gt_value, mode="lower")
        ixp_base = normalize_text(raw_ixp_value, mode="lower")
        gt_normalized = self._normalize_for_field(gt_value, field_cfg)
        ixp_normalized = self._normalize_for_field(raw_ixp_value, field_cfg)

        signals: dict[str, Any] = {
            "gt_present": gt_value not in (None, ""),
            "ixp_present": raw_ixp_value not in (None, "", []),
            "exact": gt_value == raw_ixp_value and gt_value not in (None, ""),
            "field_normalized_match": bool(gt_normalized and ixp_normalized and gt_normalized == ixp_normalized),
            "norm_exact": bool(
                remove_punctuation(gt_base) and remove_punctuation(gt_base) == remove_punctuation(ixp_base)
            ),
            "partial_overlap": bool(
                gt_normalized
                and ixp_normalized
                and (gt_normalized in ixp_normalized or ixp_normalized in gt_normalized)
                and gt_normalized != ixp_normalized
            ),
            "token_set_ratio": fuzz.token_set_ratio(gt_normalized or gt_base, ixp_normalized or ixp_base)
            if gt_value not in (None, "") and raw_ixp_value not in (None, "", [])
            else 0.0,
            "ratio": fuzz.ratio(gt_normalized or gt_base, ixp_normalized or ixp_base)
            if gt_value not in (None, "") and raw_ixp_value not in (None, "", [])
            else 0.0,
            "model_confidence": model_confidence,
            "gt_normalized": gt_normalized,
            "ixp_normalized": ixp_normalized,
            "validators": {},
        }

        validator_names = field_cfg.get("validators", []) or []
        for validator_name in validator_names:
            signals["validators"][validator_name] = self._run_validator(
                validator_name,
                gt_value=gt_value,
                ixp_value=raw_ixp_value,
            )

        tolerance = field_cfg.get("numeric_tolerance")
        if tolerance is not None:
            signals["numeric_tolerance_match"] = validators.within_numeric_tolerance(
                gt_value,
                raw_ixp_value,
                tolerance=float(tolerance),
            )
        else:
            signals["numeric_tolerance_match"] = None

        return signals

    def _run_validator(self, validator_name: str, *, gt_value: Any, ixp_value: Any) -> dict[str, Any]:
        gt_text = _safe_text(gt_value)
        ixp_text = _safe_text(ixp_value)

        if validator_name == "npi":
            gt_norm = validators.digits_only(gt_text)
            ixp_norm = validators.digits_only(ixp_text)
            return {
                "gt_valid": validators.validate_npi(gt_text) if gt_text else None,
                "ixp_valid": validators.validate_npi(ixp_text),
                "match": bool(gt_norm and ixp_norm and gt_norm == ixp_norm),
            }

        if validator_name == "date":
            gt_norm = validators.date_normalize(gt_text)
            ixp_norm = validators.date_normalize(ixp_text)
            return {
                "gt_valid": validators.validate_date(gt_text) if gt_text else None,
                "ixp_valid": validators.validate_date(ixp_text),
                "match": bool(gt_norm and ixp_norm and gt_norm == ixp_norm),
            }

        if validator_name == "icd":
            gt_norm = normalize_text(gt_text, mode="uppercase")
            ixp_norm = normalize_text(ixp_text, mode="uppercase")
            return {
                "gt_valid": validators.validate_icd(gt_text) if gt_text else None,
                "ixp_valid": validators.validate_icd(ixp_text),
                "match": bool(gt_norm and ixp_norm and gt_norm == ixp_norm),
            }

        return {"gt_valid": None, "ixp_valid": None, "match": None}

    def _normalize_for_field(self, value: Any, field_cfg: dict[str, Any]) -> str:
        text = normalize_text(value)
        normalize_modes = field_cfg.get("normalize")
        if normalize_modes is None:
            modes: list[str] = []
        elif isinstance(normalize_modes, str):
            modes = [normalize_modes]
        else:
            modes = [str(mode) for mode in normalize_modes]

        for mode in modes:
            if mode == "lower":
                text = normalize_text(text, mode="lower")
            elif mode == "uppercase":
                text = normalize_text(text, mode="uppercase")
            elif mode == "digits":
                text = validators.digits_only(text)
            elif mode == "date":
                text = validators.date_normalize(text) or normalize_text(text, mode="lower")
            elif mode in {"punct", "punctuation"}:
                text = remove_punctuation(text)

        if field_cfg.get("strip_punctuation"):
            text = remove_punctuation(text)
        return re.sub(r"\s+", " ", text).strip()

    def _candidate_value(self, candidate: Any) -> Any:
        if isinstance(candidate, dict):
            for key in ("value", "text", "content"):
                if key in candidate:
                    return candidate.get(key)
        return candidate

    def _candidate_confidence(self, candidate: Any) -> float | None:
        if isinstance(candidate, dict):
            for key in ("confidence", "score"):
                value = _clamp_confidence(candidate.get(key))
                if value is not None:
                    return value
        return None

    def _candidate_path(self, candidate: Any) -> str | None:
        if isinstance(candidate, dict):
            path = candidate.get("path")
            return str(path) if path else None
        return None

    def aggregate_confidence(self, signals: dict[str, Any], field_cfg: dict[str, Any]) -> tuple[float, str]:
        if not signals.get("ixp_present"):
            return 0.0, "MISSING"

        if not signals.get("gt_present"):
            validator_score = self._validator_validity_score(signals)
            base_score = (signals.get("model_confidence") or 0.5) * 0.7
            if validator_score is not None:
                base_score += validator_score * 0.3
            return max(0.0, min(1.0, base_score)), "WARN"

        if signals.get("exact"):
            return 1.0, "PASS"
        if signals.get("field_normalized_match"):
            return 0.98, "PASS"
        if any(entry.get("match") for entry in signals.get("validators", {}).values()):
            return 0.97, "PASS"
        if signals.get("norm_exact"):
            return 0.95, "PASS"

        token_ratio = float(signals.get("token_set_ratio", 0.0)) / 100.0
        plain_ratio = float(signals.get("ratio", 0.0)) / 100.0
        model_confidence = signals.get("model_confidence")
        validator_validity = self._validator_validity_score(signals)
        validator_match = self._validator_match_score(signals)

        score = token_ratio * 0.45 + plain_ratio * 0.2
        score += (model_confidence if model_confidence is not None else 0.5) * 0.2
        if validator_validity is not None:
            score += validator_validity * 0.1
        if validator_match is not None:
            score += validator_match * 0.05
        if signals.get("numeric_tolerance_match") is True:
            score = max(score, 0.96)
        elif signals.get("partial_overlap"):
            score += 0.05

        score = max(0.0, min(1.0, score))
        threshold = float(field_cfg.get("acceptance_threshold", self.default_threshold))
        warn_threshold = max(0.0, threshold - 0.15)
        if score >= threshold:
            verdict = "PASS"
        elif score >= warn_threshold:
            verdict = "WARN"
        else:
            verdict = "FAIL"
        return score, verdict

    def _validator_validity_score(self, signals: dict[str, Any]) -> float | None:
        values = [
            1.0 if entry.get("ixp_valid") else 0.0
            for entry in signals.get("validators", {}).values()
            if entry.get("ixp_valid") is not None
        ]
        return sum(values) / len(values) if values else None

    def _validator_match_score(self, signals: dict[str, Any]) -> float | None:
        values = [
            1.0 if entry.get("match") else 0.0
            for entry in signals.get("validators", {}).values()
            if entry.get("match") is not None
        ]
        return sum(values) / len(values) if values else None

    def classify_error(
        self,
        gt_value: Any,
        ixp_value: Any,
        signals: dict[str, Any],
        *,
        verdict: str,
    ) -> Optional[str]:
        if gt_value in (None, ""):
            return "GroundTruthMissing"
        if ixp_value in (None, "", []):
            return "Missing"
        if verdict == "PASS":
            return "Match"
        if signals.get("partial_overlap"):
            return "Partial"
        if any(entry.get("ixp_valid") is False for entry in signals.get("validators", {}).values()):
            return "FormatMismatch"
        model_confidence = signals.get("model_confidence")
        if model_confidence is not None and model_confidence < 0.5:
            return "LowConfidence"
        if max(signals.get("token_set_ratio", 0.0), signals.get("ratio", 0.0)) >= 70.0:
            return "NearMatch"
        return "WrongValue"

    def build_markdown_summary(self, report: dict[str, Any]) -> str:
        summary = report.get("summary", {})
        lines = [f"# Evaluation summary for {report.get('doc_id', 'unknown')}"]
        lines.append("")
        lines.append(f"- fields evaluated: {summary.get('fields_evaluated', 0)}")
        lines.append(f"- fields with GT: {summary.get('fields_with_gt', 0)}")
        lines.append(f"- fields passed: {summary.get('fields_passed', 0)}")
        lines.append(f"- coverage: {summary.get('coverage', 0.0):.2%}")
        lines.append("")
        lines.append("## Per-field verdicts")
        lines.append("")
        lines.append("| Field | Verdict | Confidence | Error | GT | IXP |")
        lines.append("| --- | --- | ---: | --- | --- | --- |")
        for field in report.get("fields", []):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_markdown_cell(field.get("canonical_field")),
                        _escape_markdown_cell(field.get("verdict")),
                        f"{float(field.get('confidence', 0.0)):.3f}",
                        _escape_markdown_cell(field.get("error_class")),
                        _escape_markdown_cell(field.get("gt_value")),
                        _escape_markdown_cell(field.get("ixp_value")),
                    ]
                )
                + " |"
            )
        return "\n".join(lines)

    def build_metrics(self, report: dict[str, Any]) -> dict[str, Any]:
        fields = report.get("fields", [])
        confidences = [
            float(field.get("confidence", 0.0))
            for field in fields
            if field.get("ixp_value") not in (None, "", [])
        ]
        fields_with_gt = [field for field in fields if field.get("ground_truth_present")]
        covered_fields = [field for field in fields_with_gt if field.get("ixp_value") not in (None, "", [])]

        per_field_stats: dict[str, Any] = {}
        for field in fields:
            stats = per_field_stats.setdefault(
                str(field.get("canonical_field")),
                {
                    "count": 0,
                    "avg_confidence": 0.0,
                    "pass": 0,
                    "warn": 0,
                    "fail": 0,
                    "missing": 0,
                },
            )
            stats["count"] += 1
            stats["avg_confidence"] += float(field.get("confidence", 0.0))
            verdict = str(field.get("verdict", "MISSING")).lower()
            stats[verdict] = stats.get(verdict, 0) + 1

        for stats in per_field_stats.values():
            stats["avg_confidence"] = round(stats["avg_confidence"] / max(stats["count"], 1), 4)

        return {
            "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
            "coverage": round(len(covered_fields) / len(fields_with_gt), 4) if fields_with_gt else 0.0,
            "field_count": len(fields),
            "verdict_counts": report.get("summary", {}).get("verdict_counts", {}),
            "per_field_stats": per_field_stats,
        }
