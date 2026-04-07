# Prompt Pack

These prompts are meant to support the developer workflow around IXP automations and AI solutions.

They focus on two major uses:

1. helping developers build artifacts, logic, and code faster
2. helping developers troubleshoot and improve extraction behavior faster

They are also intended to help Studio-first developers design and produce Python-based logic that extends beyond what they would traditionally build only in Studio.

## 1. IXP failure analysis

Use when:

- you have a sample set with repeated extraction issues and want the coding agent to identify patterns

Prompt:

```text
You are helping troubleshoot an IXP extraction workflow.

Inputs:
- sample extracted outputs
- expected outputs or reviewer notes when available
- any notes about the current taxonomy or prompt behavior

Your job:
1. Identify repeated failure patterns.
2. Cluster the failures by likely root cause.
3. Separate issues that likely belong in IXP from issues that likely belong in code or downstream workflow logic.
4. Recommend the smallest changes worth testing first.
5. Suggest the best eval samples to confirm whether the fix worked.

Keep the recommendations practical and developer-oriented.
```

## 2. Prompt and taxonomy troubleshooting

Use when:

- you want help turning bad extraction examples into targeted IXP improvements

Prompt:

```text
You are helping improve an IXP taxonomy or prompt configuration.

Inputs:
- examples of weak or incorrect extraction
- current field names and taxonomy behavior
- reviewer notes about the intended output

Your job:
1. Explain the likely reason for each failure.
2. Suggest targeted prompt or taxonomy improvements.
3. Call out where the issue is unlikely to be solved by prompt tuning alone.
4. Recommend a small regression set to test after the change.

Do not suggest broad rewrites unless the failures clearly require them.
```

## 3. Studio-side artifact generation

Use when:

- you want help creating the supporting artifacts around an IXP solution

Prompt:

```text
Help me create developer artifacts for a UiPath Studio Desktop solution that uses IXP.

I need one or more of the following:
- mapping documentation
- test packet inventory
- expected-output templates
- review workbook structure
- exception categories
- handoff contract for downstream systems

Return concise, implementation-ready artifacts that a Studio team can use directly.
Prefer tables, contracts, and checklists over high-level prose.
```

## 4. Coded helper design

Use when:

- a task feels too complex, conditional, or cross-page for IXP alone
- the team needs Python-based logic but wants help designing it cleanly

Prompt:

```text
Design a coded helper or coded agent for a UiPath document workflow.

Context:
- Studio Desktop remains the orchestration layer.
- IXP remains the primary extractor.
- The coded component should handle logic that is too complex for prompt-only extraction.

Task:
[describe the task]

Return:
1. what should stay in Studio
2. what should stay in IXP
3. what the coded helper or coded agent should own
4. the recommended input and output contract
5. any evaluation artifacts needed to validate the design
```

## 5. Python packaging and reuse planning

Use when:

- you want to build reusable Python logic that can be packaged with coded agents
- the solution team is stronger in Studio than in handwritten Python and wants help structuring the code well

Prompt:

```text
Help me design reusable Python logic for a UiPath coded-agent solution.

The logic may need to work with:
- IXP outputs
- API workflow inputs
- Storage Bucket file pickups
- Data Fabric records
- evaluation artifacts

Return:
1. suggested module boundaries
2. input and output contracts
3. reusable helper functions
4. where tests should focus
5. what should remain outside the Python package
```

## 6. Comparison and scorecard planning

Use when:

- you want a measurable way to evaluate whether a prompt, taxonomy, or code change helped

Prompt:

```text
Design an evaluation approach for an IXP automation change.

The change may involve:
- prompt or taxonomy edits
- new coded-agent logic
- new Python helper functions
- workflow changes around extraction review

Return:
1. the minimum useful scorecard
2. the sample set needed
3. the artifacts to save from each run
4. how to separate extraction quality from downstream business validation
5. the decision rule for promoting the change
```
