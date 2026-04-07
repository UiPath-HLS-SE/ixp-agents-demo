# Annotation schema for document_ixp_sanity

- Format: JSONL (one JSON object per line) or CSV with `doc_id,canonical_field,value,annotator_id,page,bbox`.
- Required fields:
  - `doc_id` - document identifier
  - `canonical_field` - canonical name (see `mapping_config.example.yaml`)
  - `value` - annotated value (string or list)
  - `annotator_id` - who annotated
  - optional `page`, `bbox` for provenance

Example JSONL entry:
`{"doc_id":"DOC-0001","canonical_field":"patient_name","value":"John Doe","annotator_id":"demo-user","page":1,"bbox":[100,200,450,260]}`
