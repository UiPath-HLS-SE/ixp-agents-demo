# Recommended Pattern for Studio Desktop Teams

## Summary

Coding agents help accelerate IXP automations and AI solutions in two major ways:

1. they help developers build solution logic, artifacts, and code faster
2. they help developers troubleshoot and improve extraction behavior faster

An important practical effect is that Studio-first developers can now use coding agents to create complex Python-based logic that they often would not previously have built comfortably by hand.

For a Studio Desktop team, the recommended pattern is not to replace Studio or IXP. It is to use coding agents across the solution lifecycle:

`Studio orchestration + IXP extraction + coding-agent-assisted development + coded logic for hard cases`

## What this means in practice

### Studio Desktop remains the orchestration surface

Use Studio for:

- process flow
- approvals and exceptions
- integration handoffs
- queue operations
- deterministic automation steps

### IXP remains the primary extraction surface

Use IXP for:

- taxonomy and prompt configuration
- form-aware field and table extraction
- baseline structured output for downstream use

### Coding agents accelerate the developer workflow

Use coding agents to help with:

- workflow-adjacent artifact creation
- test and sample data generation
- mapping specifications
- failure analysis
- prompt and taxonomy troubleshooting
- helper code and coded-agent scaffolding
- Python logic that extends what the team can implement beyond traditional Studio-only patterns

### Code owns the tasks that are too complex for prompt-only extraction

Use Python helpers or coded agents for:

- advanced validation
- no-form or low-signal gating
- cross-page reasoning
- evidence-backed classification
- comparison and evaluation utilities
- reusable logic that should be versioned and tested

This is especially useful when the team understands the business process well but has historically had less experience writing complex Python directly.

## Recommended developer loop

1. Build or update the baseline IXP extraction.
2. Run a representative sample set.
3. Review failures and weak spots.
4. Use a coding agent to analyze the failure modes.
5. Use a coding agent to help create prompt fixes, artifacts, or code.
6. Re-run and compare before promoting any change.

## Best first use cases

- generating test artifacts around extraction changes
- troubleshooting repeated IXP failures
- building comparison tools and scorecards
- implementing validation or enrichment logic in Python
- creating coded-agent helpers for business-specific document logic

## Guardrails

- Do not treat coding agents as a replacement for Studio orchestration.
- Do not force all logic into IXP when code is the better fit.
- Do not promote changes without review artifacts or scoring.
- Do not leave important logic only in prompts when it should be versioned in code.

## What success looks like

- faster iteration on extraction quality issues
- more reusable technical artifacts
- more fine-grained business logic captured in code
- clearer separation of concerns across Studio, IXP, and coded components
- better business-fit solutions delivered faster
- expanded developer capability, not just faster execution of the same tasks
