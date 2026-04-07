---
marp: true
title: Coding Agents for IXP Automations and AI Solutions
paginate: true
---

# Coding Agents for IXP Automations and AI Solutions

## Accelerating how developers build better document solutions

- Audience: Studio Desktop developers with some familiarity editing IXP in the web
- Focus: how coding agents help build, debug, and extend IXP-based automations
- Outcome: better solutions, better fit to the business process, faster delivery

Speaker note:
This lesson is about coding agents as a developer persona in the UiPath platform. The point is not just "LLMs can read documents." The point is that coding agents help developers build stronger document solutions faster.

---

# The key message

Coding agents help accelerate work on IXP automations and AI solutions in two major ways:

1. They help developers build solution artifacts, logic, and code faster.
2. They help developers troubleshoot and improve extraction behavior faster.

Speaker note:
Keep repeating this. The lesson is not narrowly about runtime extraction. It is about speed and solution quality across the full developer workflow.

---

# Why this matters now

- Traditional RPA is strong at deterministic orchestration
- IXP is strong at structured extraction
- Many Studio-first developers were not previously writing complex Python for document solutions
- Real document processes still have:
  - nuanced rules
  - edge cases
  - low-signal packets
  - process-specific exceptions
- Coding agents let developers address those gaps faster than manual trial-and-error

Speaker note:
The comparison is not "RPA versus AI." The better framing is that coding agents let teams handle finer-grained logic and iteration faster than traditional RPA alone, including logic that many Studio-first developers would not have written by hand in Python before.

---

# The first big value area

## Coding agents help build solution logic faster

- RPA and API workflow logic
- file pickup and handoff flows from Storage Buckets or Data Fabric
- helper code in Python
- coded-agent packages
- normalization, validation, and review utilities

Speaker note:
This is where coding agents feel immediately useful to Studio teams. They help create the assets and logic around the process, not just the final extraction prompt, and they lower the barrier to using Python for more advanced solution logic.

---

# A major unlock for Studio-first teams

- Developers who were comfortable in Studio and IXP did not always have a path to writing complex Python logic quickly
- Coding agents change that
- They can help produce:
  - coded-agent scaffolding
  - Python helpers
  - validation logic
  - comparison utilities
  - advanced document-processing code
- That means teams can solve more nuanced business problems without waiting on a separate specialized coding team

Speaker note:
This slide is important. It says the force multiplier is not only speed. It is expanded capability for developers who previously were not working this way.

---

# What developers can build with help from coding agents

- workflow-adjacent specs and artifacts
- mapping documents between IXP output and downstream payloads
- sample inputs and test packets
- eval scripts and comparison utilities
- Python helpers packaged with coded agents
- review reports for business and QA partners

Speaker note:
A good phrase here is: coding agents reduce the blank-page problem for developers.

---

# The second big value area

## Coding agents help troubleshoot and improve IXP faster

- analyze repeated extraction failures
- cluster failure modes
- suggest prompt and taxonomy changes
- identify which issues belong in IXP and which belong in code
- create eval-ready examples to confirm whether a change helped

Speaker note:
This is the bridge between "bad output" and "a concrete next action." Coding agents help convert frustrating review work into an engineering loop.

---

# Recommended developer workflow

1. Run a representative packet set through IXP.
2. Review where extraction quality breaks down.
3. Use a coding agent to analyze patterns and propose next changes.
4. Use a coding agent to help build any needed code, utilities, or artifacts.
5. Re-run and compare results before promoting changes.

Speaker note:
The lesson should feel like a developer loop, not a magical AI leap.

---

# Where the agent helps in the solution stack

- In Studio Desktop:
  - process structure
  - exception handling ideas
  - integration scaffolding
- In IXP:
  - prompt troubleshooting
  - taxonomy iteration
  - extraction gap analysis
- In code:
  - Python helpers
  - coded agents
  - advanced validation and enrichment logic

Speaker note:
This is the key boundary slide. Coding agents help across the stack, but each layer still has a job.

---

# A practical example

## Prior-auth extraction

Base system:

- IXP performs the main extraction
- Studio orchestrates downstream handling

Developer acceleration:

- coding agent reviews failed packets
- coding agent suggests prompt and taxonomy changes
- coding agent helps build utilities for comparison and scoring
- coding agent helps implement advanced logic where prompt-only extraction is not enough

Speaker note:
This ties the message back to the repo. You have concrete examples here already.

---

# What belongs in code instead of only in IXP

- no-complete-form gating
- cross-page classification logic
- confidence-based routing
- field validation against multiple extracted signals
- baseline-versus-candidate comparison
- evidence packaging for reviewers

Speaker note:
When the logic gets semantic, conditional, or cross-document, coded helpers or coded agents often become the better place to implement it.

---

# Why this is better than pure manual iteration

- more fine-grained rules
- faster iteration on hard problems
- more reusable artifacts
- clearer separation between extraction, orchestration, and advanced logic
- easier path from prototype to maintained solution

Speaker note:
The audience should come away thinking: "This makes my current process more capable," not "This replaces how I work."

---

# UiPath platform direction

- coding agents are becoming a first-class persona in the platform
- platform primitives are increasingly exposed to code and agent workflows
- developers can combine:
  - RPA
  - APIs
  - Storage Buckets
  - Data Fabric
  - coded agents
  - Python packaging

Speaker note:
This is the strategic slide. You are telling the audience this is aligned with platform direction, not a sidecar hack. The platform is making it more realistic for Studio-first developers to work with coded logic as part of the same solution.

---

# Demo flow

1. Show an IXP extraction issue
2. Show how a coding agent analyzes the issue
3. Show an artifact the agent helps produce
4. Show code or coded-agent logic for a hard case
5. Show how the updated solution is easier to maintain and explain

Speaker note:
Keep the demo focused on developer leverage.

---

# The pitch in one sentence

Coding agents help developers build better IXP automations and AI solutions faster by accelerating both the creation of solution logic and the improvement of extraction quality.
