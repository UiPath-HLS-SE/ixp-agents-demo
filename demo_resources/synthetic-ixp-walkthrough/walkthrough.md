# Synthetic IXP Walkthrough

This folder is a synthetic-only walkthrough for the repo's current UM Intake flow:

`PDF -> IXP normalization -> DeepRAG second pass -> spreadsheet comparison`

## Guardrails

- Every source PDF in this package was freshly generated from the sibling `synthetic-record-generator` repo.
- The generated PDFs and their paired JSON files were copied into this walkthrough folder so the HTML demo can link to them directly.
- Every spreadsheet row in this package is synthetic and fabricated from those generated packets.
- No customer PDFs or production extraction outputs were copied into these artifacts.

## Source Packets

| Packet | Source Family | PDF | JSON |
| --- | --- | --- | --- |
| `record_a_moderate_acuity` | `provider_records` | `demo_packet_files/provider_records/record_a_moderate_acuity.pdf` | `demo_packet_files/provider_records/record_a_moderate_acuity.json` |
| `synthetic_patient_chart_case_001` | `base_patient_chart` | `demo_packet_files/base_patient_chart/synthetic_patient_chart_case_001.pdf` | `demo_packet_files/base_patient_chart/synthetic_patient_chart_case_001.json` |
| `record_a_high_risk_member` | `payer_records` | `demo_packet_files/payer_records/record_a_high_risk_member.pdf` | `demo_packet_files/payer_records/record_a_high_risk_member.json` |

## How The Real Repo Flow Maps To These Synthetic Files

1. The first stage mirrors a baseline IXP extraction run that reads PDFs and writes `normalized_fields` plus `normalized_tables`.
   For this offline walkthrough, that output shape is mirrored in `synthetic_ixp_results.json` and `synthetic_ixp_results.xlsx`.
2. The second stage mirrors a coded second pass that re-reads the document, uses IXP fields as hints, and returns `extraction`, `field_guesses`, and `strategy_used`.
   For this walkthrough, that shape is mirrored in `synthetic_deeprag_results.json` and `synthetic_deeprag_results.xlsx`.
3. The third stage mirrors the comparison pattern that aligns spreadsheet truth against both the baseline IXP output and the second-pass output using canonical field paths.
   For this walkthrough, the synthetic truth sheet is `synthetic_ground_truth.xlsx` and the final comparison workbook is `synthetic_ixp_deeprag_ground_truth_comparison.xlsx`.

## Synthetic Output Files

- Ground truth workbook: `synthetic_ground_truth.xlsx`
- IXP output workbook: `synthetic_ixp_results.xlsx`
- DeepRAG output workbook: `synthetic_deeprag_results.xlsx`
- Comparison workbook: `synthetic_ixp_deeprag_ground_truth_comparison.xlsx`
- HTML dashboard: `comparison_dashboard.html`
- Document summary CSV: `document_summary.csv`
- Field results CSV: `field_results.csv`

## What To Look At First

- `synthetic_ground_truth.xlsx`: reviewer-entered expected values using the same `Sample_Tracking` sheet shape as the real eval flow.
- `synthetic_ixp_results.xlsx`: normalized IXP output in the same `Summary / Documents / Fields / Tables` structure the bucket runner writes.
- `synthetic_deeprag_results.xlsx`: second-pass extracted field paths plus field-level reasoning/evidence metadata.
- `synthetic_ixp_deeprag_ground_truth_comparison.xlsx`: side-by-side reviewer workbook showing match / missing / mismatch outcomes.

## Rerun

```bash
python3 scripts/build_synthetic_ixp_walkthrough.py
```

That command regenerates the synthetic PDFs first, then rebuilds the synthetic spreadsheets, comparison outputs, and HTML dashboard.
It requires the sibling `synthetic-record-generator` repo next to this repo.

## Notes

- This package intentionally includes `2` grounded DeepRAG cases and `1` fallback case so the comparison workbook shows both normal and non-comparable behavior.
- Several IXP values are intentionally left blank or slightly wrong so the comparison sheets make the IXP-vs-DeepRAG delta obvious during a walkthrough.
