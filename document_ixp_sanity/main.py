from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from uipath.platform import UiPath
except Exception:
    class UiPath:  # type: ignore[override]
        """Local fallback so unit tests can run without the UiPath SDK installed."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass


try:
    # TODO: Prefer the shared repo helpers when this package is moved into the evaluator repo.
    from ground_truth_evaluator.storage import BucketArtifactStore
    from ground_truth_evaluator.utils import _run_phase
except Exception:
    BucketArtifactStore = None

    class _PhaseContext:
        def __init__(self, name: str) -> None:
            self.name = name

        def __enter__(self) -> None:
            print(f"PHASE: {self.name}", flush=True)
            return None

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def _run_phase(name: str) -> _PhaseContext:
        return _PhaseContext(name)


try:
    import yaml
except Exception:
    yaml = None

from document_ixp_sanity.evaluator import IXPEvaluator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAPPING_PATH = PROJECT_ROOT / "document_ixp_sanity" / "mapping_config.example.json"
DEFAULT_GT_SAMPLE_PATH = PROJECT_ROOT / "document_ixp_sanity" / "sample_gt" / "sample1.jsonl"


class GraphInput(BaseModel):
    doc_id: str
    ixp_output_json: dict[str, Any] | list[Any] | str | None = Field(default=None)
    ixp_output_bucket_path: str | None = Field(default=None)
    ground_truth_json: dict[str, Any] | list[Any] | str | None = Field(default=None)
    ground_truth_bucket_path: str | None = Field(default=None)
    mapping_config_path: str | None = Field(default=None)

    model_config = {"extra": "ignore"}


class GraphOutput(BaseModel):
    evaluation_report: dict[str, Any]
    summary_markdown: str
    metrics: dict[str, Any]


def _parse_jsonish_text(text: str, *, source_hint: str = "") -> Any:
    stripped = text.strip()
    if not stripped:
        return {}

    suffix = Path(source_hint).suffix.lower()
    if suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(stripped)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and all(line.startswith("{") for line in lines):
        return [json.loads(line) for line in lines]

    raise ValueError(f"Unsupported JSON payload format for {source_hint or 'inline payload'}.")


def _read_local_payload(path: Path) -> Any:
    return _parse_jsonish_text(path.read_text(encoding="utf-8"), source_hint=str(path))


def load_json_from_bucket(store: Any, path: str) -> Any:
    local_path = Path(path)
    if local_path.exists():
        return _read_local_payload(local_path)

    if store and hasattr(store, "download_json"):
        payload = store.download_json(path)
        if isinstance(payload, str):
            return _parse_jsonish_text(payload, source_hint=path)
        return payload

    if store and hasattr(store, "download_text"):
        return _parse_jsonish_text(store.download_text(path), source_hint=path)

    raise FileNotFoundError(f"Bucket store unavailable and local file not found: {path}")


def _coerce_inline_payload(payload: Any) -> Any:
    if payload is None:
        return {}
    if isinstance(payload, str):
        maybe_path = Path(payload)
        if maybe_path.exists():
            return _read_local_payload(maybe_path)
        return _parse_jsonish_text(payload, source_hint="inline")
    return payload


def _load_payload(*, inline_payload: Any, bucket_path: str | None, store: Any) -> Any:
    if bucket_path:
        return load_json_from_bucket(store, bucket_path)
    return _coerce_inline_payload(inline_payload)


def load_mapping_config(path: str | None) -> dict[str, Any]:
    mapping_path = Path(path) if path else DEFAULT_MAPPING_PATH
    if not mapping_path.exists():
        return {}

    text = mapping_path.read_text(encoding="utf-8")
    if mapping_path.suffix.lower() == ".json":
        return json.loads(text)

    if yaml is None:
        raise RuntimeError(
            f"YAML support is unavailable, but a YAML mapping config was requested: {mapping_path}"
        )
    return yaml.safe_load(text) or {}


def main(input: GraphInput | dict[str, Any]) -> GraphOutput:
    graph_input = GraphInput.model_validate(input)
    try:
        client = UiPath()
    except Exception:
        client = None
    store = None
    if BucketArtifactStore:
        try:
            # TODO: In the evaluator repo, prefer the shared bucket helper directly.
            store = BucketArtifactStore.from_env(client)
        except Exception:
            store = None

    with _run_phase("load_inputs"):
        ixp_payload = _load_payload(
            inline_payload=graph_input.ixp_output_json,
            bucket_path=graph_input.ixp_output_bucket_path,
            store=store,
        )
        gt_payload = _load_payload(
            inline_payload=graph_input.ground_truth_json,
            bucket_path=graph_input.ground_truth_bucket_path,
            store=store,
        )
        mapping = load_mapping_config(graph_input.mapping_config_path)

    evaluator = IXPEvaluator(mapping=mapping)

    with _run_phase("evaluate"):
        evaluation_report = evaluator.evaluate(
            doc_id=graph_input.doc_id,
            ixp_payload=ixp_payload,
            ground_truth=gt_payload,
        )

    with _run_phase("summarize"):
        summary_md = evaluator.build_markdown_summary(evaluation_report)
        metrics = evaluator.build_metrics(evaluation_report)

    return GraphOutput(
        evaluation_report=evaluation_report,
        summary_markdown=summary_md,
        metrics=metrics,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-smoke",
        help="Path to a local sample IXP JSON to run a smoke test",
        default=None,
    )
    args = parser.parse_args()

    if args.run_smoke:
        sample_gt = (
            _read_local_payload(DEFAULT_GT_SAMPLE_PATH) if DEFAULT_GT_SAMPLE_PATH.exists() else None
        )
        graph_input = {
            "doc_id": "DOC-SAMPLE-1",
            "ixp_output_json": _read_local_payload(Path(args.run_smoke)),
            "ground_truth_json": sample_gt,
            "mapping_config_path": str(DEFAULT_MAPPING_PATH),
        }
        output = main(graph_input)
        print(json.dumps(output.model_dump(), indent=2, ensure_ascii=False))
