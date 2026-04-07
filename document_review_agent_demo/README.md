# Document Review Agent Demo

This is a small offline example of the kind of Python-based logic a team can package once coding agents help them move beyond Studio-only patterns.

It is not tied to a live model or a live UiPath tenant. It demonstrates a coded-agent-style contract:

- input:
  - packet text
  - current extracted fields
  - requested fields to review
- output:
  - field guesses
  - confidence
  - support status
  - evidence snippets

## Run

```bash
python3 document_review_agent_demo/main.py --input document_review_agent_demo/input.sample.json
```

## Why this exists

One of the important force-multiplier effects of coding agents is that Studio-first developers can now create useful Python-based helpers and coded agents much faster than before.

This demo is intentionally simple and offline, but it shows the shape of that work.
