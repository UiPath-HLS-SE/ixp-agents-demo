# KSWIC Extraction Validation Task

This repo can support a true reviewer step in Maestro, but the supported UiPath
implementation has one hard requirement:

- the review step must be a Maestro `User task`
- the user task must use `Create Action App task`
- the Action App input must include `validationData` of type `ContentValidationData`

That implementation pattern is documented in UiPath Maestro:

- `Extracting and validating documents`:
  https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/how-to-document-extraction-and-validation
- `User task`:
  https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/user-task

## What exists in this repo now

- live IXP extraction output:
  - `../live_ixp/results.json`
  - `../live_ixp/review_payloads.json`
  - `../live_ixp/review_summary.md`
- a conceptual Maestro flow with an explicit review step:
  - `kswic_payer_correspondence.bpmn`
  - `kswic_payer_correspondence_flow.md`

## What is still missing for a true in-product review task

1. An RPA workflow that creates DU validation artifacts.
   UiPath's documented path uses `Create Document Validation Artifacts`.
2. A deployed Action App task.
   The Action App should expose `validationData` as `ContentValidationData`.
3. A published Maestro process that binds the `User task` to that deployed
   Action App.

## Practical recommendation for this demo

Use the current `live_ixp/review_payloads.json` as the interim reviewer queue
while keeping the published Shared smoke flow unchanged.

When you want the real reviewer experience in UiPath:

1. Move the extraction step into a Studio Web RPA workflow.
2. Generate DU validation artifacts there.
3. Publish the Action App task.
4. Insert the `User task` before the downstream smoke or production automations.

## Minimal reviewer fields for KSWIC

For the payer-correspondence scenarios in this repo, the reviewer should verify:

- document type
- member ID
- authorization number or claim number
- service description
- note text or reason summary
- suggested routing flags:
  - `is_denial_of_service`
  - `payer_auth_problem`
  - `missing_information`
  - `target_record_type`
