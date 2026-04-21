# UiPath Document Agents Demo

This repository is a sanitized, demo-safe starter repo for showing how coding agents can accelerate document automation work around UiPath Studio Desktop and IXP.

It intentionally excludes customer-specific materials, production bucket references, restricted artifacts, and business-domain notes from the source repo it was derived from.

## Start here

- Landing page: `index.html`
- Full presentation microsite: `presentation/coding-agents-for-ixp/site/index.html`
- Walkthrough scorecard dashboard: `demo_resources/synthetic-ixp-walkthrough/comparison_dashboard.html`
- KSWIC payer-correspondence starter demo: `demo_resources/kswic-payer-correspondence-demo/README.md`
- GitHub repo: `https://github.com/UiPath-HLS-SE/ixp-agents-demo`

## What is included

- `presentation/coding-agents-for-ixp/`
  - a browser-ready microsite and markdown presentation kit
  - focused on how coding agents help developers build better IXP automations and AI solutions faster
- `document_ixp_sanity/`
  - a generic local evaluation helper for comparing IXP-style output against ground truth
  - includes synthetic sample data and basic tests
- `document_review_agent_demo/`
  - a small offline coded-agent-style demo that reviews extracted fields against packet text
  - demonstrates the kind of Python logic teams can package once coding agents lower the implementation barrier
- `demo_resources/`
  - synthetic sample packet text, extracted output, and ground-truth records
  - includes a KSWIC payer-correspondence starter batch with synthetic PDFs, simulated IXP output, Maestro flow assets, and dummy downstream automations

## Why this repo exists

The core lesson is:

1. Coding agents help developers build solution artifacts, logic, and code faster.
2. Coding agents help developers troubleshoot and improve extraction behavior faster.
3. They also unlock complex Python-based logic for Studio-first developers, including coded agents and other automation helpers.

The goal is not to replace Studio or IXP. The goal is to combine:

- Studio orchestration
- IXP extraction
- coding-agent-assisted development
- reusable Python logic for the hard cases

## Quick start

Preferred full local setup for repo development and UiPath CLI work:

```bash
./scripts/bootstrap_uipath.sh
source .venv/bin/activate
```

Authenticate with the repo wrapper:

```bash
./scripts/uipath_auth.sh
```

Auth behavior defaults to attended desktop/browser login. Use
`./scripts/uipath_auth.sh --unattended` only when you explicitly want client
credentials from `.env`. The new Shared-folder cloud smoke scripts prefer the
desktop auth cache first and only fall back to unattended credentials when
those env vars are configured for operations.

Optional minimal setup for offline smoke tests only:

```bash
python3 -m pip install -r requirements.txt
```

Open the presentation microsite directly in a browser:

- `presentation/coding-agents-for-ixp/site/index.html`

Open the root landing page for a cleaner repo entry point:

- `index.html`

Open the static walkthrough dashboard for a demo-safe IXP vs. second-pass scorecard:

- `demo_resources/synthetic-ixp-walkthrough/comparison_dashboard.html`

Run the generic evaluator smoke test:

```bash
./.venv/bin/python document_ixp_sanity/main.py --run-smoke document_ixp_sanity/sample_ixp/sample1_ixp.json
```

Run the offline coded-agent demo:

```bash
./.venv/bin/python document_review_agent_demo/main.py --input document_review_agent_demo/input.sample.json
```

Check the installed UiPath CLI:

```bash
./.venv/bin/uipath --version
./scripts/uipath_auth.sh --help
```

## UiPath CLI and auth

This repo now follows the same repo-local pattern used in sibling UiPath repos:

- dependencies are declared in `pyproject.toml`
- the working environment is `.venv/`
- dependency sync is done with `uv`
- the UiPath CLI lives in the repo-local environment as `./.venv/bin/uipath`

Bootstrap details:

- `scripts/bootstrap_uipath.sh` prefers Python 3.12, then 3.11, and rejects
  older interpreters
- if `uv` is not already available on your machine, the bootstrap script
  installs it into `.venv` first and then runs `./.venv/bin/uv sync`
- this avoids relying on a global Python or a global UiPath CLI install

Auth details:

- `scripts/uipath_auth.sh` loads `.env` when present
- by default it opens interactive desktop/browser auth
- pass `--unattended` only when you want client-credentials auth explicitly
- the Shared-folder cloud scripts prefer cached desktop auth first, then use
  unattended credentials as an operational fallback
- the intended default for local developer work is desktop auth, not unattended

Copy `.env.example` to `.env` only if you need unattended or scripted cloud
operations:

```bash
cp .env.example .env
```

## Shared cloud smoke tests

This repo now includes actual publishable Shared-folder cloud test assets,
mirroring the pattern used in the sibling orchestrator demo repo:

- `cloud-api-smoke/shared-kswic-correspondence-smoke-agent/`
  - deterministic coded agent for KSWIC correspondence routing smoke tests
- `maestro-process-tests/shared-kswic-correspondence-maestro-test/`
  - minimal Maestro wrapper that starts the published smoke-agent release
- `scripts/deploy_shared_kswic_cloud_tests.sh`
  - publishes both packages to the tenant feed, then binds explicit releases in the `Shared` folder
- `scripts/setup_shared_kswic_cloud_tests.py`
  - creates or updates explicit releases in `Shared`
- `scripts/run_shared_kswic_cloud_smoke.py`
  - invokes either the smoke release or the Maestro release and can poll job state

End-to-end flow:

```bash
./scripts/uipath_auth.sh
./scripts/deploy_shared_kswic_cloud_tests.sh
./.venv/bin/python scripts/run_shared_kswic_cloud_smoke.py --target maestro --wait
```

The default target folder is `Shared` via `.env.example`, and the default tenant
settings point at `HLS_SE_Team`.

To feed the published smoke or Maestro release from the live `UM Intake` fake-doc
run instead of the built-in synthetic profiles:

```bash
./.venv/bin/python scripts/run_shared_kswic_cloud_smoke.py \
  --target maestro \
  --live-ixp-packet scn_003_prior_authorization_denial_letter \
  --wait
```

## Live UM Intake IXP run

The KSWIC demo also includes a direct live-IXP runner that sends a small batch
of synthetic payer correspondence PDFs through the tenant's `UM Intake`
extractor tagged `live` by default:

```bash
./scripts/uipath_auth.sh
./.venv/bin/python scripts/run_live_um_intake_kswic_demo.py
```

Default batch:

- `scn_001_prior_authorization_approval_letter`
- `scn_003_prior_authorization_denial_letter`
- `scn_005_request_for_additional_information`

Artifacts are written to
`demo_resources/kswic-payer-correspondence-demo/live_ixp/`, including
`results.json`, `manifest.json`, per-document raw payloads under `raw/`, a
compact `summary.md`, and reviewer-oriented `review_payloads.json` /
`review_summary.md`.

## How to demo this in 10 minutes

1. Open `index.html`, `presentation/coding-agents-for-ixp/site/index.html`, or `demo_resources/synthetic-ixp-walkthrough/comparison_dashboard.html`.
2. Walk through the core message:
   coding agents help teams build solution logic faster and troubleshoot extraction faster.
3. Make the Python unlock explicit:
   Studio-first developers can now package useful coded logic much more easily.
4. Show the synthetic walkthrough dashboard:
   `demo_resources/synthetic-ixp-walkthrough/comparison_dashboard.html`
5. Show the KSWIC payer-correspondence starter:
   `demo_resources/kswic-payer-correspondence-demo/README.md`
6. Run the offline coded-agent demo:
   `python3 document_review_agent_demo/main.py --input document_review_agent_demo/input.sample.json`
7. Run the evaluator smoke test:
   `python3 document_ixp_sanity/main.py --run-smoke document_ixp_sanity/sample_ixp/sample1_ixp.json`
8. Close on the architecture:
   Studio orchestration + IXP extraction + coding-agent-assisted development + reusable Python logic.

## GitHub Pages

This repo now includes:

- a root `index.html` landing page
- a static presentation microsite under `presentation/coding-agents-for-ixp/site/`

To publish it with the simplest setup:

1. Open the repository Pages settings.
2. Set `Source` to `Deploy from a branch`.
3. Select branch `main`.
4. Select folder `/(root)`.

With that configuration, the root landing page is ready to act as the public entry point.

## Demo-safe boundaries

This repo is intended to be shareable. It does not include:

- customer names or project names
- live bucket coordinates
- production auth references
- business-specific ground truth spreadsheets
- restricted extraction artifacts
- internal handoff notes tied to a real deployment
