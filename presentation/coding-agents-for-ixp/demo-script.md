# Live Demo Script

## Goal

Show that coding agents help developers build better IXP automations and AI solutions faster, not only by reasoning about documents at runtime, but by accelerating the work of building, debugging, and extending the solution.

## Core story

Start from the audience's current reality:

- they already use Studio Desktop for process logic
- they already understand IXP as the extraction surface
- they already spend time debugging prompts, inspecting failures, and building support artifacts

Then show that coding agents help in two major ways:

1. they help build solution logic and artifacts faster
2. they help troubleshoot and improve IXP behavior faster

Also make one point explicit:

3. they help Studio-first developers produce complex Python logic that many of them would not previously have written comfortably by hand

## Recommended 15-minute flow

### 1. Frame the developer problem - 2 minutes

Say:

"The hardest part of an IXP solution is usually not only getting a first extraction. It is building the surrounding process logic, handling exceptions, and iterating quickly on extraction failures."

Emphasize:

- traditional RPA handles deterministic steps well
- document processes often need finer-grained logic
- coding agents help developers move faster on that work
- coding agents also expand what the team can realistically build in Python

### 2. Show the two value areas - 3 minutes

Use the deck to explain:

- build logic faster
- troubleshoot IXP faster

Example developer outputs to mention:

- mapping specs
- test packets
- comparison scripts
- review reports
- Python helpers
- coded-agent scaffolding

Key line to say:

"One of the biggest changes here is that developers who were mostly living in Studio can now produce useful Python-based solution logic much faster, including coded agents and other automated logic."

### 3. Show current repo examples - 4 minutes

Use:

```bash
sed -n '1,220p' README.md
sed -n '1,220p' document_review_agent_demo/README.md
sed -n '1,220p' document_ixp_sanity/README.md
```

Talk track:

- the repo already contains evaluation and coded-agent examples
- this shows the kind of artifacts and code that developers can produce with coding-agent help
- the lesson is not about replacing IXP, but about extending what the solution can do
- it also shows the kind of Python logic that becomes accessible when coding agents help generate and refine it

### 4. Walk through an IXP troubleshooting loop - 3 minutes

Say:

"Suppose we see a repeated failure: over-extraction on no-form packets or weak classification fields."

Then explain the loop:

1. run a representative packet set
2. inspect the failure pattern
3. ask the coding agent to cluster likely causes
4. decide what belongs in prompt changes versus coded logic
5. rebuild comparison artifacts and review the result

### 5. Walk through a coded-logic extension - 2 minutes

Use:

- the repo examples of offline coded-agent logic and evaluation helpers

Talk track:

- some tasks are too conditional or cross-page for prompt-only extraction
- that is where Python helpers or coded agents become useful
- Studio still orchestrates the process, but code can own the more advanced logic
- this matters because many teams previously did not have a fast path to writing and maintaining that code

### 6. Close on the platform direction - 1 minute

Say:

"UiPath is making coding agents a first-class developer persona. The opportunity is to combine Studio, IXP, APIs, Storage Buckets, Data Fabric, and packaged Python logic into solutions that are more capable and easier to evolve."

## Suggested terminal walkthrough

```bash
sed -n '1,200p' README.md
sed -n '1,220p' document_review_agent_demo/README.md
sed -n '1,220p' document_ixp_sanity/README.md
sed -n '1,220p' presentation/coding-agents-for-ixp/recommended-pattern.md
```

## Demo artifacts to emphasize

- the architecture handout in `recommended-pattern.md`
- the prompt ideas in `prompt-pack.md`
- the repo's generic evaluator and coded-agent structure as proof points

## Fallback if you cannot do anything live

If services are unavailable, keep the demo focused on developer workflow:

1. show the repo structure
2. show the problem-to-solution loop
3. show the kinds of artifacts coding agents help generate
4. show where coded logic becomes the right tool
5. reinforce the platform message

## Strong closing line

"Coding agents are useful here because they help developers ship better document solutions faster, with more of the fine-grained logic captured in reusable artifacts and code instead of tribal knowledge and manual rework."
