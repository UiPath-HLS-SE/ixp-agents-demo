# Shared KSWIC Correspondence Smoke Agent

Deterministic coded-agent package for Shared-folder smoke testing in the HLS tenant.

This package simulates the post-IXP routing layer for KSWIC payer correspondence:

- classify the correspondence into a high-level route bucket
- decide whether it is a denial of service
- flag payer-auth problems
- choose the dummy downstream action for payer portal, Cerner, and rev cycle

Expected Shared-folder release name:

- `Shared KSWIC Correspondence Smoke Agent`

Local package commands from the repo root:

```bash
./.venv/bin/uipath pack cloud-api-smoke/shared-kswic-correspondence-smoke-agent
./.venv/bin/uipath deploy --tenant cloud-api-smoke/shared-kswic-correspondence-smoke-agent
./.venv/bin/python scripts/setup_shared_kswic_cloud_tests.py --folder-path Shared
```

For end-to-end cloud setup and invocation, prefer the repo wrappers:

```bash
./scripts/deploy_shared_kswic_cloud_tests.sh
./.venv/bin/python scripts/run_shared_kswic_cloud_smoke.py --target smoke --wait
```

To invoke the published smoke agent from a live `UM Intake` result record:

```bash
./.venv/bin/python scripts/run_shared_kswic_cloud_smoke.py \
  --target smoke \
  --live-ixp-packet scn_005_request_for_additional_information \
  --wait
```
