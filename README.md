# UiPath Document Agents Demo

This repository is a sanitized, demo-safe starter repo for showing how coding agents can accelerate document automation work around UiPath Studio Desktop and IXP.

It intentionally excludes customer-specific materials, production bucket references, restricted artifacts, and business-domain notes from the source repo it was derived from.

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

Open the presentation microsite directly in a browser:

- `presentation/coding-agents-for-ixp/site/index.html`

Run the generic evaluator smoke test:

```bash
python3 document_ixp_sanity/main.py --run-smoke document_ixp_sanity/sample_ixp/sample1_ixp.json
```

Run the offline coded-agent demo:

```bash
python3 document_review_agent_demo/main.py --input document_review_agent_demo/input.sample.json
```

## Demo-safe boundaries

This repo is intended to be shareable. It does not include:

- customer names or project names
- live bucket coordinates
- production auth references
- business-specific ground truth spreadsheets
- restricted extraction artifacts
- internal handoff notes tied to a real deployment
