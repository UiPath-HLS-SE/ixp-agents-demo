# Extraction Review Queue

These payloads are reviewer-oriented summaries derived from the live `UM Intake` run.
They are not yet UiPath `ContentValidationData` artifacts.

| Packet | Type | Member ID | Auth/Claim | Suggested Route | Review Mode |
| --- | --- | --- | --- | --- | --- |
| `scn_001_prior_authorization_approval_letter` | `Prior Authorization Approval Letter` | `PHH-484920-01` | `PA-884201` | `prior_authorization/approved` | `interim_json_review` |
| `scn_003_prior_authorization_denial_letter` | `Prior Authorization Denial Letter` | `FHC-228174-02` | `PA-118943` | `prior_authorization/denied` | `interim_json_review` |
| `scn_005_request_for_additional_information` | `Request for Additional Information` | `SPM-775114-05` | `N/A` | `claim_denial/pended` | `interim_json_review` |

To turn this into a true Maestro review step, follow the UiPath-supported path:
1. Create DU validation artifacts in an RPA workflow.
2. Create an Action App task with `validationData: ContentValidationData`.
3. Bind a Maestro User task to that Action App and pause for reviewer approval.

