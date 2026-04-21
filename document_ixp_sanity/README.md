# document_ixp_sanity

Generic local evaluator for comparing IXP-style structured output against ground truth.

Smoke run on stock Python:

- Smoke test: `python3 document_ixp_sanity/main.py --run-smoke document_ixp_sanity/sample_ixp/sample1_ixp.json`

Optional full setup for tests and extra local tooling:

- Install deps: `python3 -m pip install -r requirements.txt`
- Unit tests: `python3 -m pytest document_ixp_sanity/tests`

This package is demo-safe and intentionally generic. It does not depend on customer data, live bucket sources, or a specific business domain.

It falls back cleanly when pydantic, rapidfuzz, the UiPath SDK, or shared UiPath helpers are unavailable, so the smoke run still works without credentials or a prebuilt environment.
