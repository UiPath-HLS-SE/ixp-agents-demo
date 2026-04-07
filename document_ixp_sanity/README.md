# document_ixp_sanity

Generic local evaluator for comparing IXP-style structured output against ground truth.

Quick run:

- Unit tests: `python3 -m pytest document_ixp_sanity/tests`
- Smoke test: `python3 document_ixp_sanity/main.py --run-smoke document_ixp_sanity/sample_ixp/sample1_ixp.json`

This package is demo-safe and intentionally generic. It does not depend on customer data, live bucket sources, or a specific business domain.

It falls back cleanly when shared UiPath helpers are unavailable so local runs and unit tests still work without credentials.
