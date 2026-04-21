# Shared KSWIC Correspondence Maestro Test

Minimal publishable Maestro wrapper for the Shared-folder KSWIC smoke demo.

Expected Shared-folder release name:

- `Shared KSWIC Correspondence Maestro Test`

The BPMN process starts the published smoke-agent release:

- target release: `Shared KSWIC Correspondence Smoke Agent`
- target folder: `Shared`

Preferred repo-level commands:

```bash
./scripts/deploy_shared_kswic_cloud_tests.sh
./.venv/bin/python scripts/run_shared_kswic_cloud_smoke.py --target maestro --wait
```

To start the published Maestro wrapper from a live `UM Intake` result record:

```bash
./.venv/bin/python scripts/run_shared_kswic_cloud_smoke.py \
  --target maestro \
  --live-ixp-packet scn_003_prior_authorization_denial_letter \
  --wait
```
