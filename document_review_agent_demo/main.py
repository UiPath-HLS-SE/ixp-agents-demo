from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class FieldGuess:
    path: str
    value: str | None
    confidence: float
    status: str
    reasoning: str
    evidence: list[dict[str, Any]]


def _read_input(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    packet_text_path = payload.get("packet_text_path")
    if packet_text_path:
        resolved = (path.parent / packet_text_path).resolve()
        payload["packet_text"] = resolved.read_text(encoding="utf-8")
    return payload


def _extract_value(packet_text: str, patterns: list[str]) -> tuple[str | None, str | None]:
    for pattern in patterns:
        match = re.search(pattern, packet_text, flags=re.IGNORECASE)
        if match:
            value = (match.group(1) or "").strip()
            snippet = match.group(0).strip()
            return value, snippet
    return None, None


def review_fields(input_payload: dict[str, Any]) -> dict[str, Any]:
    packet_text = str(input_payload.get("packet_text") or "")
    current_ixp_fields = dict(input_payload.get("current_ixp_fields") or {})
    requested_fields = list(input_payload.get("requested_fields") or [])

    guesses: list[FieldGuess] = []
    for field in requested_fields:
        path = str(field.get("path") or "")
        label = str(field.get("label") or path)
        patterns = [str(pattern) for pattern in field.get("patterns") or []]
        ixp_hint = current_ixp_fields.get(path)

        matched_value, snippet = _extract_value(packet_text, patterns)
        if matched_value:
            confidence = 0.95 if ixp_hint in (None, "", matched_value) else 0.82
            status = "confirmed" if ixp_hint in (None, "", matched_value) else "revised"
            reasoning = f"{label} was found directly in the packet text."
            evidence = [{"snippet": snippet, "source": input_payload.get("document_name")}]
            value = matched_value
        elif ixp_hint not in (None, ""):
            confidence = 0.45
            status = "hint_only"
            reasoning = f"{label} was not found in the packet text. Returning the current extracted hint for review."
            evidence = []
            value = str(ixp_hint)
        else:
            confidence = 0.12
            status = "missing"
            reasoning = f"{label} was not supported by the packet text."
            evidence = []
            value = None

        guesses.append(
            FieldGuess(
                path=path,
                value=value,
                confidence=confidence,
                status=status,
                reasoning=reasoning,
                evidence=evidence,
            )
        )

    return {
        "document_name": input_payload.get("document_name"),
        "summary": "Offline review over synthetic packet text.",
        "field_guesses": [asdict(guess) for guess in guesses],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to the input JSON payload.")
    args = parser.parse_args()

    payload = _read_input(Path(args.input))
    output = review_fields(payload)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
