# KSWIC Payer Correspondence Demo

Starter demo package for Kansas Sunflower Women's Imaging Center intake and revenue-cycle routing around payer correspondence.

This bundle is intentionally demo-safe:

- all names, IDs, addresses, NPIs, claim numbers, and auth numbers are fictional
- the packet set is built locally from the repo's synthetic record tooling
- Maestro, Cerner, rev cycle, and payer portal actions are represented as static contracts and simulated outputs
- the repo now also includes publishable Shared-folder cloud smoke packages that exercise the orchestration shape with real UiPath packages

## Why this demo exists

The KSWIC workflow needs three layers kept separate:

- IXP for correspondence classification and field extraction
- Maestro for confidence gating and multi-step orchestration
- downstream automations for Cerner updates, payer-portal actions, and rev-cycle work items

That matches the current UiPath platform guidance:

- IXP handles multi-modal classification and extraction across structured, semi-structured, and unstructured document capabilities: [UiPath IXP introduction](https://docs.uipath.com/ixp/automation-cloud/latest/user-guide/introduction)
- when a fax packet may contain multiple document types, classification validation is the recommended safety net before downstream extraction and routing: [Document classification validation overview](https://docs.uipath.com/document-understanding/automation-cloud/latest/classic-user-guide/document-classification-validation-overview)
- Maestro models the orchestration layer on a BPMN 2.0 canvas: [Maestro BPMN-supported elements](https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/bpmn-support)

## Included assets

- `generated_packets/`
  - ten synthetic payer-correspondence packet folders
  - each folder contains a PDF, the source scenario JSON, and a text rendering
- `scenario_catalog.json`
  - compact structured catalog for the starter batch
- `ixp_extraction_contract.json`
  - field contract for the IXP layer
- `simulated_ixp_output.json`
  - IXP-style structured payloads that Maestro would consume
- `live_ixp/`
  - outputs from the live `UM Intake` IXP extractor run against a small fake-doc batch
  - includes `results.json`, `manifest.json`, `summary.md`, `review_payloads.json`, `review_summary.md`, and raw per-document payloads
- `simulated_maestro_run.json`
  - routing results showing which dummy automations fire for each notice
- `ground_truth.jsonl`
  - evaluator-friendly truth rows for core fields and route flags
- `maestro/`
  - BPMN-style process file, flow JSON, and a readable markdown flow handout
  - includes `kswic_extraction_validation_task.md` describing the supported UiPath user-task pattern for reviewer validation
- `automation_stubs/`
  - dummy contracts for payer portal, Cerner auth, Cerner patient account, and rev-cycle actions
- `../../cloud-api-smoke/shared-kswic-correspondence-smoke-agent/`
  - publishable Shared-folder smoke agent for the KSWIC routing logic
- `../../maestro-process-tests/shared-kswic-correspondence-maestro-test/`
  - publishable Maestro wrapper that starts the Shared smoke-agent release

## Shared-folder cloud test path

The repo now carries a real cloud smoke-test lane for the HLS tenant's `Shared`
folder, modeled after the sibling orchestrator demo repo:

1. deploy `cloud-api-smoke/shared-kswic-correspondence-smoke-agent`
2. deploy `maestro-process-tests/shared-kswic-correspondence-maestro-test`
3. run `scripts/setup_shared_kswic_cloud_tests.py` to create or update the
   explicit Shared-folder releases
4. invoke the smoke release directly or invoke the Maestro release, which then
   starts the smoke agent via `Orchestrator.StartAgentJob`

## Starter scenarios

The batch currently includes:

1. Prior auth approval
2. Prior auth denial
3. Claim denial
4. Request for additional information
5. Appeal acknowledgment
6. Appeal overturn
7. Paid EOB
8. COB questionnaire
9. Overpayment recovery notice
10. Pharmacy exception denial

## Regenerate

Run:

```bash
python3 scripts/build_kswic_payer_correspondence_demo.py
```

The script re-renders the packet PDFs and refreshes the scenario catalog, simulated IXP payloads, Maestro run output, and automation contracts.

## Run the live UM Intake extractor

After repo auth is set up, run the live extractor against the default fake-doc
batch:

```bash
./scripts/uipath_auth.sh
./.venv/bin/python scripts/run_live_um_intake_kswic_demo.py
```

Notes:

- the runner targets the `UM Intake` DU/IXP project
- it selects the project version tagged `live` by default via `--tag-name live`
- the default packets are:
  - `scn_001_prior_authorization_approval_letter`
  - `scn_003_prior_authorization_denial_letter`
  - `scn_005_request_for_additional_information`
- override the batch with repeated `--doc <packet_folder_name>` flags
- output artifacts land in `live_ixp/`

## Start the published Shared demo from live IXP output

After `live_ixp/results.json` exists, invoke the published Shared smoke or
Maestro release directly from one of those live records:

```bash
./.venv/bin/python scripts/run_shared_kswic_cloud_smoke.py \
  --target maestro \
  --live-ixp-packet scn_003_prior_authorization_denial_letter \
  --wait
```

Supported selectors on the run script:

- `--live-ixp-packet`
- `--live-ixp-scenario`
- `--live-ixp-document-id`

## Can Maestro stop for reviewer validation?

Yes, but the true UiPath-supported implementation requires more than the raw
live IXP JSON:

- Maestro review is modeled as a `User task`
- the task uses `Create Action App task`
- the Action App expects `validationData` of type `ContentValidationData`

This repo now includes interim reviewer payloads in `live_ixp/review_payloads.json`
and a design note in `maestro/kswic_extraction_validation_task.md`, but the
published Shared demo does not yet include the live Action App because the DU
validation-artifact workflow and deployed Action App are not in this repo.

## Suggested walkthrough

1. Open `packet_manifest.json` to pick a document.
2. Open the matching synthetic PDF under `generated_packets/`.
3. Show the extracted fields in `simulated_ixp_output.json`.
4. Show the route decision in `simulated_maestro_run.json`.
5. Close on the orchestration design in `maestro/kswic_payer_correspondence_flow.md`.
