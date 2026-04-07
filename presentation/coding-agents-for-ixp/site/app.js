document.body.classList.add("js-enhanced");

const repoBlobBase = "https://github.com/UiPath-HLS-SE/ixp-agents-demo/blob/main";

const framingPills = [
  "Start from Studio Desktop and IXP as the familiar baseline",
  "Explain the pain in edge cases, iteration speed, and support artifacts",
  "Position coding agents as a developer persona, not just a runtime model",
  "Land on better business-fit solutions delivered faster",
];

const valueAreas = [
  {
    tag: "Value Area One",
    title: "Build solution logic, artifacts, and code faster",
    copy:
      "Coding agents reduce the blank-page problem for developers. They help teams move faster on the assets and coded components that hold a document solution together.",
    points: [
      "RPA and API workflow logic ideas",
      "File pickup and handoff flows from Storage Buckets or Data Fabric",
      "Python helpers and coded-agent scaffolding",
      "Normalization, validation, and review utilities",
      "Mapping specs, test packets, and handoff contracts",
    ],
  },
  {
    tag: "Value Area Two",
    title: "Troubleshoot and improve IXP faster",
    copy:
      "Coding agents help teams turn bad extraction examples into a developer loop: analyze patterns, propose likely fixes, and build the artifacts needed to verify whether the change helped.",
    points: [
      "Cluster repeated extraction failures",
      "Suggest prompt and taxonomy improvements",
      "Decide what belongs in IXP versus code",
      "Build evaluation and comparison artifacts",
      "Support faster regression review before promotion",
    ],
  },
];

const unlocks = [
  {
    tag: "Python Helpers",
    title: "Validation and normalization logic",
    copy:
      "Package logic that checks extracted data, reshapes payloads, and applies business-specific rules that would be awkward to maintain only in prompts or workflows.",
  },
  {
    tag: "Coded Agents",
    title: "Advanced reasoning where prompts alone fall short",
    copy:
      "Prototype coded agents for packet review, enrichment, evidence collection, or classification when the task needs more than a single extraction prompt.",
  },
  {
    tag: "Automation Utilities",
    title: "Comparison, scoring, and review support",
    copy:
      "Generate the utilities that make solution iteration disciplined: run summaries, diff reports, scorecards, and business-review artifacts.",
  },
  {
    tag: "Integration Logic",
    title: "Storage Bucket, Data Fabric, and API handoffs",
    copy:
      "Create the code around file retrieval, metadata shaping, and downstream contracts so the whole process fits the business workflow more tightly.",
  },
  {
    tag: "Team Capability",
    title: "Studio-first developers can reach further",
    copy:
      "The force multiplier is not only speed. Teams can now implement useful Python-based solution logic that they might previously have deferred to a separate coding specialist.",
  },
  {
    tag: "Reusable Assets",
    title: "Versioned, testable logic instead of tribal knowledge",
    copy:
      "Promote the hard-won rules into code and artifacts that can be reviewed, rerun, and maintained instead of being trapped in ad hoc notes and manual rework.",
  },
];

const stack = [
  {
    tag: "Studio Desktop",
    title: "Own orchestration and deterministic process flow",
    points: [
      "Queues, handoffs, exceptions, approvals",
      "Activity-based integrations",
      "RPA flow and downstream system choreography",
    ],
  },
  {
    tag: "IXP",
    title: "Own the primary extraction surface",
    points: [
      "Taxonomy and prompt configuration",
      "Base field and table extraction",
      "Structured output that downstream components can consume",
    ],
  },
  {
    tag: "Coding Agents",
    title: "Accelerate how developers build and improve the solution",
    points: [
      "Artifact generation and scaffolding",
      "Failure analysis and prompt troubleshooting",
      "Planning coded extensions and evaluation strategy",
    ],
  },
  {
    tag: "Python and Coded Logic",
    title: "Own the advanced reusable logic",
    points: [
      "Cross-page reasoning and validation",
      "No-form gating, scorecards, comparison helpers",
      "Packaged code that belongs under version control and tests",
    ],
  },
];

const lessonFlow = [
  {
    step: "1",
    title: "Start from what the audience already does today",
    copy:
      "Open with Studio Desktop orchestration and IXP extraction as the familiar baseline. This keeps the lesson grounded in the audience's current workflow.",
    note:
      "Say that the challenge is not getting any extraction at all. The challenge is building and maintaining a full business-fit solution around document extraction.",
  },
  {
    step: "2",
    title: "Describe where teams lose time",
    copy:
      "Explain the friction in edge cases, prompt troubleshooting, repeated review work, and the gap between extraction and the surrounding process logic.",
    note:
      "This is where the audience should recognize their own experience instead of hearing a generic AI story.",
  },
  {
    step: "3",
    title: "Introduce the two major value areas",
    copy:
      "Show that coding agents help both with building solution logic faster and with improving extraction behavior faster.",
    note:
      "Keep the framing practical. Use phrases like artifact generation, coded helpers, regression review, and prompt troubleshooting.",
  },
  {
    step: "4",
    title: "Land the Python unlock explicitly",
    copy:
      "Call out that Studio-first developers can now produce useful complex Python logic with support from coding agents, including coded agents and automation helpers.",
    note:
      "This is the real force multiplier. It expands what the team can realistically implement, not just how fast they type.",
  },
  {
    step: "5",
    title: "Show the stack boundaries",
    copy:
      "Make the architecture clear: Studio still orchestrates, IXP still extracts, coding agents accelerate developer work, and Python owns the advanced reusable logic.",
    note:
      "This protects the audience from hearing the message as 'replace everything with agents.'",
  },
  {
    step: "6",
    title: "Close with adoption and platform direction",
    copy:
      "Finish with the idea that coding agents are becoming a first-class persona in the UiPath platform and give teams a practical path to better, faster document solutions.",
    note:
      "Emphasize better fit to the business process, faster delivery, and more fine-grained logic captured in reusable code and artifacts.",
  },
];

const demoFlow = [
  {
    time: "2 min",
    tag: "Frame",
    title: "Start with the developer problem",
    copy:
      "Explain that the hardest part of an IXP solution is often everything around the extraction: exceptions, comparisons, prompt tuning, and supporting artifacts.",
  },
  {
    time: "3 min",
    tag: "Value",
    title: "Show the two major value areas",
    copy:
      "Use the site and deck to show how coding agents help with both solution-building work and extraction-improvement work.",
  },
  {
    time: "4 min",
    tag: "Proof",
    title: "Point to concrete repo examples",
    copy:
      "Use the coded-agent demo and evaluation docs as proof that these are real solution patterns, not theoretical ideas.",
  },
  {
    time: "3 min",
    tag: "Troubleshooting Loop",
    title: "Walk an IXP issue into a developer loop",
    copy:
      "Show how a repeated failure leads to failure analysis, prompt or taxonomy changes, coded extensions where needed, and comparison artifacts before promotion.",
  },
  {
    time: "3 min",
    tag: "Unlock",
    title: "Close on the Python capability expansion",
    copy:
      "Make it explicit that coding agents give Studio-first developers a realistic path to building coded agents and other Python-based automation logic.",
  },
];

const artifacts = [
  {
    tag: "Web",
    title: "This microsite",
    copy: "Use this as the polished browser entry point for the lesson and the presentation flow.",
    href: "./index.html",
    hrefLabel: "Open site",
    meta: ["Presentation-ready", "Static HTML/CSS/JS", "No build step"],
  },
  {
    tag: "Deck",
    title: "Slide deck source",
    copy: "Keep the talk track in editable markdown for future revisions or export into another presentation format.",
    href: `${repoBlobBase}/presentation/coding-agents-for-ixp/slide-deck.md`,
    hrefLabel: "Open slide deck",
    meta: ["Marp-style markdown", "Speaker framing", "Easy to revise"],
  },
  {
    tag: "Demo",
    title: "Live demo runbook",
    copy: "Use the live sequence and talk track to keep the demo centered on developer leverage rather than raw model output.",
    href: `${repoBlobBase}/presentation/coding-agents-for-ixp/demo-script.md`,
    hrefLabel: "Open demo script",
    meta: ["15-minute flow", "Fallback guidance", "Terminal references"],
  },
  {
    tag: "Pattern",
    title: "Recommended architecture handout",
    copy: "Share the responsibility split across Studio, IXP, coding agents, and Python logic in a concise format.",
    href: `${repoBlobBase}/presentation/coding-agents-for-ixp/recommended-pattern.md`,
    hrefLabel: "Open handout",
    meta: ["Studio-first framing", "Guardrails", "Best first use cases"],
  },
  {
    tag: "Prompts",
    title: "Prompt pack",
    copy: "Use this to demonstrate how coding agents can help with artifact generation, prompt troubleshooting, helper design, and evaluation planning.",
    href: `${repoBlobBase}/presentation/coding-agents-for-ixp/prompt-pack.md`,
    hrefLabel: "Open prompt pack",
    meta: ["Developer-oriented", "IXP troubleshooting", "Python planning"],
  },
  {
    tag: "Repo",
    title: "Sanitized repo overview",
    copy: "Anchor the story in the repo’s generic coded-agent and evaluation structure.",
    href: `${repoBlobBase}/README.md`,
    hrefLabel: "Open repo README",
    meta: ["Operational context", "Architecture", "Evidence trail"],
  },
  {
    tag: "Agent Demo",
    title: "Offline coded-agent example",
    copy: "Use this to show the kind of Python logic teams can now prototype and package more easily.",
    href: `${repoBlobBase}/document_review_agent_demo/README.md`,
    hrefLabel: "Open agent demo",
    meta: ["Offline", "Python-based", "Demo-safe"],
  },
  {
    tag: "Evaluator",
    title: "Generic IXP evaluation helper",
    copy: "Use this to show how teams can build and keep reusable scorecards around extraction changes.",
    href: `${repoBlobBase}/document_ixp_sanity/README.md`,
    hrefLabel: "Open evaluator",
    meta: ["Sample data", "Tests", "Smoke run"],
  },
];

function renderPills() {
  const container = document.querySelector("#framing-pills");
  container.innerHTML = framingPills.map((item) => `<span class="pill">${item}</span>`).join("");
}

function renderValueAreas() {
  const container = document.querySelector("#value-area-grid");
  container.innerHTML = valueAreas
    .map(
      (item) => `
        <article class="value-card">
          <span class="eyebrow">${item.tag}</span>
          <strong>${item.title}</strong>
          <p>${item.copy}</p>
          <ul class="value-list">
            ${item.points.map((point) => `<li>${point}</li>`).join("")}
          </ul>
        </article>
      `,
    )
    .join("");
}

function renderUnlocks() {
  const container = document.querySelector("#unlock-grid");
  container.innerHTML = unlocks
    .map(
      (item) => `
        <article class="unlock-card">
          <span class="unlock-chip">${item.tag}</span>
          <strong>${item.title}</strong>
          <p>${item.copy}</p>
        </article>
      `,
    )
    .join("");
}

function renderStack() {
  const container = document.querySelector("#stack-grid");
  container.innerHTML = stack
    .map(
      (item) => `
        <article class="stack-card">
          <span class="eyebrow">${item.tag}</span>
          <strong>${item.title}</strong>
          <ul class="stack-list">
            ${item.points.map((point) => `<li>${point}</li>`).join("")}
          </ul>
        </article>
      `,
    )
    .join("");
}

function renderLessonFlow() {
  const container = document.querySelector("#lesson-timeline");
  container.innerHTML = lessonFlow
    .map(
      (item) => `
        <article class="timeline-step">
          <div class="timeline-marker">
            <div class="timeline-number">${item.step}</div>
            <span class="eyebrow">Lesson Step</span>
          </div>
          <div>
            <h3>${item.title}</h3>
            <p class="timeline-copy">${item.copy}</p>
          </div>
          <div class="timeline-note">
            <strong>Speaker angle</strong>
            <p class="timeline-copy">${item.note}</p>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderDemoFlow() {
  const container = document.querySelector("#demo-grid");
  container.innerHTML = demoFlow
    .map(
      (item) => `
        <article class="demo-card">
          <span class="demo-chip">${item.tag}</span>
          <div class="demo-time">${item.time}</div>
          <strong>${item.title}</strong>
          <p>${item.copy}</p>
        </article>
      `,
    )
    .join("");
}

function renderArtifacts() {
  const container = document.querySelector("#artifact-grid");
  container.innerHTML = artifacts
    .map(
      (item) => `
        <article class="artifact-card">
          <span class="artifact-tag">${item.tag}</span>
          <strong>${item.title}</strong>
          <p>${item.copy}</p>
          <ul class="artifact-meta">
            ${item.meta.map((entry) => `<li>${entry}</li>`).join("")}
          </ul>
          <div class="artifact-footer">
            <a class="artifact-link" href="${item.href}">${item.hrefLabel}</a>
          </div>
        </article>
      `,
    )
    .join("");
}

function setupReveal() {
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
        }
      }
    },
    { threshold: 0.14 },
  );

  document.querySelectorAll(".reveal").forEach((element) => observer.observe(element));
}

function setupNavTracking() {
  const links = Array.from(document.querySelectorAll(".top-nav a"));
  const map = new Map(links.map((link) => [link.getAttribute("href").slice(1), link]));
  const sections = document.querySelectorAll("[data-section]");

  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

      if (!visible) {
        return;
      }

      const target = visible.target.id || visible.target.dataset.section;
      links.forEach((link) => link.classList.remove("is-active"));
      if (map.has(target)) {
        map.get(target).classList.add("is-active");
      }
    },
    { rootMargin: "-30% 0px -55% 0px", threshold: [0.1, 0.25, 0.5] },
  );

  sections.forEach((section) => observer.observe(section));
}

renderPills();
renderValueAreas();
renderUnlocks();
renderStack();
renderLessonFlow();
renderDemoFlow();
renderArtifacts();
setupReveal();
setupNavTracking();
