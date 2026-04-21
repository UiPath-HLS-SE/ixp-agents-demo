---
name: visual-lint
description: Audit HTML/CSS/TSX files for text density issues and visual consistency. Use when the user asks to "lint visuals", "check text density", "audit UI text", "visual lint", "scaffold from referrals template", or mentions checking banners, buttons, badges, or cards for too much text. Also use when the user asks to create a new project from the referrals/EMIR template.
version: 1.0.0
---

# Visual Lint — Text Density & Consistency Auditor

**Purpose:** Enforce the design principles from the EMIR (Medical Imaging Requisitions) app across all projects: brevity over prose, spatial hierarchy over text volume, functional labels over explanatory copy.

---

## Two Modes

This skill operates in two modes based on user intent:

### Mode 1: `audit` (default)

Scan HTML, CSS, and TSX files in the target directory for text-density violations and visual inconsistencies.

### Mode 2: `scaffold`

Generate a starter template with the EMIR/Fluent-inspired design system tokens and layout shell.

---

## Mode 1: Audit

### What to Scan

Scan all `.html`, `.tsx`, `.jsx`, and `.css` files in the target project directory, excluding `node_modules/`, `.venv/`, `dist/`, `.next/`, `.git/`, and `__MACOSX/`.

### Text Density Rules

Apply these rules to all visible text content in the scanned files. For HTML, parse the text content of elements directly. For TSX/JSX, parse string literals inside JSX elements and component props like `label=`, `title=`, `placeholder=`, `aria-label=`.

#### Rule 1: Hero / Lede Text
- **Selector:** Elements with class `lede`, `hero-subtitle`, `hero-description`, or `<p>` elements that are direct children of elements with class `hero`, `masthead`, `banner`, or similar.
- **Threshold:** Flag if **> 20 words**
- **Severity:** Warning
- **Message:** `"Hero lede has {N} words (limit: 20). Trim to a single scannable sentence."`
- **Suggested fix:** Rewrite to max 20 words. Move detail to a tooltip, expandable section, or separate doc.

#### Rule 2: Badges, Pills, Chips
- **Selector:** Elements with class `badge`, `pill`, `chip`, `tag`, or elements using `border-radius: 999px` / `rounded-full` / `rounded-pill`.
- **Threshold:** Flag if **> 3 words**
- **Severity:** Error
- **Message:** `"Badge/pill text '{text}' has {N} words (limit: 3). Badges should be scannable labels."`
- **Suggested fix:** Shorten to max 3 words (e.g., "Maestro for intake and recommendation orchestration" -> "Maestro Intake").

#### Rule 3: Card Headers
- **Selector:** `h2`, `h3`, `h4` inside elements with class `card`, `sim-card`, `panel`, `section`, or inside `<article>` tags. Also any element with class `card-title`, `card-header`.
- **Threshold:** Flag if **> 5 words**
- **Severity:** Warning
- **Message:** `"Card header '{text}' has {N} words (limit: 5). Headers should be scannable, not sentences."`
- **Suggested fix:** Move explanatory text to a subtitle or body paragraph.

#### Rule 4: Button Labels
- **Selector:** `<button>`, `<a>` with class `btn`/`button`, elements with `role="button"`, Tailwind classes containing `btn`.
- **Threshold:** Flag if **> 3 words**
- **Severity:** Error
- **Message:** `"Button label '{text}' has {N} words (limit: 3). Buttons should be terse action verbs."`
- **Suggested fix:** Shorten to verb + optional noun (e.g., "Explore requested capabilities" -> "Explore").

#### Rule 5: Navigation Items
- **Selector:** Elements inside `nav`, elements with class `nav-item`, `nav-pill`, `nav-link`, or `<a>` inside headers/navigation regions.
- **Threshold:** Flag if **> 3 words**
- **Severity:** Warning
- **Message:** `"Nav label '{text}' has {N} words (limit: 3)."`

#### Rule 6: Banner / Alert Text
- **Selector:** Elements with class `banner`, `alert`, `callout`, `notice`, `announcement`, or full-width elements with colored backgrounds containing paragraph text.
- **Threshold:** Flag if **> 15 words**
- **Severity:** Warning
- **Message:** `"Banner text has {N} words (limit: 15). Banners should be glanceable."`

#### Rule 7: Compact Container Text Blocks
- **Selector:** `<p>` or text nodes inside elements that are constrained (class `rail-card`, `sidebar-card`, `compact`, or elements with explicit `max-width` < 300px).
- **Threshold:** Flag if **> 15 words**
- **Severity:** Warning
- **Message:** `"Text block in compact container has {N} words (limit: 15). Dense text in small containers hurts readability."`

### Output Format

```
=== Visual Lint Report ===
Target: {directory}
Files scanned: {count}

ERRORS ({count})
  {file}:{line} — {rule}: {message}

WARNINGS ({count})
  {file}:{line} — {rule}: {message}

PASSED ({count} files clean)

Summary: {errors} errors, {warnings} warnings across {files_with_issues} files
```

Group results by file. Within each file, sort by line number. Always show the exact offending text quoted.

### How to Implement the Audit

Do NOT write a standalone script. Instead, perform the audit directly using Claude's tools:

1. Use `Glob` to find all `.html`, `.tsx`, `.jsx` files in the target directory (excluding node_modules, .venv, dist, .next, .git).
2. Use `Grep` to find elements matching each rule's selectors.
3. Use `Read` to examine flagged regions in context and count words in the visible text.
4. Compile findings into the report format above.
5. Present the report to the user with suggested fixes for each violation.

For TSX/JSX files, also check string props: `label="..."`, `title="..."`, `description="..."`, `placeholder="..."`.

---

## Mode 2: Scaffold

When the user asks to scaffold a new project or create a template, generate these files in the target directory:

### File 1: `tokens.css`

The canonical design token file extracted from the EMIR app's Fluent-inspired palette:

```css
:root {
  /* === EMIR Fluent-Inspired Design Tokens === */

  /* Neutral palette */
  --background: oklch(0.995 0 0);
  --foreground: oklch(0.15 0 0);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.15 0 0);
  --popover: oklch(1 0 0);
  --popover-foreground: oklch(0.15 0 0);

  /* Brand: Fluent blue */
  --primary: oklch(0.55 0.18 250);
  --primary-foreground: oklch(0.99 0 0);

  /* Secondary / muted */
  --secondary: oklch(0.96 0 0);
  --secondary-foreground: oklch(0.2 0 0);
  --muted: oklch(0.96 0 0);
  --muted-foreground: oklch(0.45 0 0);
  --accent: oklch(0.94 0.01 250);
  --accent-foreground: oklch(0.15 0 0);

  /* Semantic */
  --destructive: oklch(0.55 0.22 25);
  --destructive-foreground: oklch(0.99 0 0);
  --success: oklch(0.55 0.17 155);
  --success-foreground: oklch(0.99 0 0);
  --warning: oklch(0.75 0.15 75);
  --warning-foreground: oklch(0.15 0 0);

  /* Borders and inputs */
  --border: oklch(0.91 0 0);
  --input: oklch(0.91 0 0);
  --ring: oklch(0.55 0.18 250);

  /* Compact radius (Fluent density) */
  --radius: 0.375rem;

  /* Sidebar */
  --sidebar: oklch(0.98 0 0);
  --sidebar-foreground: oklch(0.15 0 0);
  --sidebar-primary: oklch(0.55 0.18 250);
  --sidebar-primary-foreground: oklch(0.99 0 0);
  --sidebar-accent: oklch(0.94 0.005 250);
  --sidebar-accent-foreground: oklch(0.15 0 0);
  --sidebar-border: oklch(0.91 0 0);

  /* Typography */
  --font-sans: 'Segoe UI', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  --font-mono: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;

  /* Spacing scale (base-4) */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
  --space-8: 2rem;

  /* Text density constraints */
  --max-button-words: 3;
  --max-badge-words: 3;
  --max-card-header-words: 5;
  --max-banner-words: 15;
  --max-hero-lede-words: 20;
}

.dark {
  --background: oklch(0.12 0.01 260);
  --foreground: oklch(0.95 0 0);
  --card: oklch(0.16 0.01 260);
  --card-foreground: oklch(0.95 0 0);
  --popover: oklch(0.18 0.01 260);
  --popover-foreground: oklch(0.95 0 0);
  --primary: oklch(0.65 0.18 250);
  --primary-foreground: oklch(0.99 0 0);
  --secondary: oklch(0.25 0.01 260);
  --secondary-foreground: oklch(0.92 0 0);
  --muted: oklch(0.22 0.01 260);
  --muted-foreground: oklch(0.65 0 0);
  --accent: oklch(0.28 0.02 250);
  --accent-foreground: oklch(0.95 0 0);
  --destructive: oklch(0.55 0.2 25);
  --destructive-foreground: oklch(0.99 0 0);
  --border: oklch(0.28 0.01 260);
  --input: oklch(0.22 0.01 260);
  --ring: oklch(0.65 0.18 250);
  --sidebar: oklch(0.14 0.01 260);
  --sidebar-foreground: oklch(0.95 0 0);
  --sidebar-primary: oklch(0.65 0.18 250);
  --sidebar-primary-foreground: oklch(0.99 0 0);
  --sidebar-accent: oklch(0.25 0.02 250);
  --sidebar-accent-foreground: oklch(0.95 0 0);
  --sidebar-border: oklch(0.28 0.01 260);
}
```

### File 2: `template.html`

A minimal starter HTML file that demonstrates the design system with zero explanatory prose:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{{PROJECT_NAME}}</title>
  <link rel="stylesheet" href="./tokens.css" />
  <style>
    * { box-sizing: border-box; margin: 0; }

    body {
      font-family: var(--font-sans);
      background: var(--background);
      color: var(--foreground);
      line-height: 1.5;
    }

    /* === Shell === */
    .shell { max-width: 1400px; margin: 0 auto; padding: var(--space-4); }

    /* === Command Bar (header) === */
    .command-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 48px;
      padding: 0 var(--space-4);
      border-bottom: 1px solid var(--border);
      background: var(--card);
    }
    .command-bar h1 { font-size: 0.875rem; font-weight: 600; }

    /* === 3-Pane Layout === */
    .pane-group {
      display: grid;
      grid-template-columns: 180px 240px 1fr;
      height: calc(100vh - 48px);
    }
    .pane {
      overflow-y: auto;
      border-right: 1px solid var(--border);
      padding: var(--space-2);
    }
    .pane:last-child { border-right: none; }

    /* === Badge === */
    .badge {
      display: inline-flex;
      align-items: center;
      gap: var(--space-1);
      padding: 2px 8px;
      border-radius: var(--radius);
      font-size: 0.75rem;
      font-weight: 500;
      background: var(--secondary);
      color: var(--secondary-foreground);
    }
    .badge--primary { background: var(--primary); color: var(--primary-foreground); }
    .badge--success { background: var(--success); color: var(--success-foreground); }
    .badge--warning { background: var(--warning); color: var(--warning-foreground); }
    .badge--destructive { background: var(--destructive); color: var(--destructive-foreground); }

    /* === Button === */
    .btn {
      display: inline-flex;
      align-items: center;
      gap: var(--space-1);
      padding: 6px 12px;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--card);
      color: var(--foreground);
      font-size: 0.8125rem;
      font-weight: 500;
      cursor: pointer;
    }
    .btn--primary {
      background: var(--primary);
      color: var(--primary-foreground);
      border-color: var(--primary);
    }
    .btn--ghost { border-color: transparent; background: transparent; }

    /* === Card === */
    .card {
      padding: var(--space-3);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--card);
    }
    .card-title { font-size: 0.875rem; font-weight: 600; margin-bottom: var(--space-2); }

    /* === List row === */
    .list-row {
      display: flex;
      align-items: center;
      gap: var(--space-2);
      padding: 6px var(--space-2);
      border-radius: var(--radius);
      font-size: 0.8125rem;
      cursor: pointer;
    }
    .list-row:hover { background: var(--accent); }
    .list-row--selected { background: var(--accent); font-weight: 600; }

    /* === Count indicator === */
    .count {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 20px;
      height: 20px;
      padding: 0 6px;
      border-radius: var(--radius);
      background: var(--muted);
      color: var(--muted-foreground);
      font-size: 0.6875rem;
      font-weight: 600;
    }

    /* === Utility === */
    .text-muted { color: var(--muted-foreground); }
    .text-xs { font-size: 0.75rem; }
    .text-sm { font-size: 0.8125rem; }
    .gap-2 { gap: var(--space-2); }
    .flex { display: flex; }
    .items-center { align-items: center; }
    .justify-between { justify-content: space-between; }
  </style>
</head>
<body>
  <!-- Command Bar: app title only, no explanatory text -->
  <div class="command-bar">
    <h1>{{PROJECT_NAME}}</h1>
    <div class="flex items-center gap-2">
      <button class="btn btn--ghost text-sm">Filters</button>
      <button class="btn btn--primary text-sm">Save</button>
    </div>
  </div>

  <!-- 3-Pane Layout -->
  <div class="pane-group">
    <!-- Left: Stage Inbox -->
    <div class="pane">
      <div class="list-row list-row--selected">
        <span>Draft</span>
        <span class="count">12</span>
      </div>
      <div class="list-row">
        <span>Pending</span>
        <span class="count">8</span>
      </div>
      <div class="list-row">
        <span>Approved</span>
        <span class="count">3</span>
      </div>
      <div class="list-row">
        <span>Completed</span>
        <span class="count">41</span>
      </div>
    </div>

    <!-- Middle: Item List -->
    <div class="pane">
      <div class="list-row list-row--selected">
        <span class="badge badge--warning">P2</span>
        <div>
          <div class="text-sm" style="font-weight:600">Item Name</div>
          <div class="text-xs text-muted">2026-04-09</div>
        </div>
      </div>
      <div class="list-row">
        <span class="badge badge--success">P4</span>
        <div>
          <div class="text-sm">Another Item</div>
          <div class="text-xs text-muted">2026-04-08</div>
        </div>
      </div>
    </div>

    <!-- Right: Detail View -->
    <div class="pane" style="padding: var(--space-4);">
      <div class="flex items-center justify-between" style="margin-bottom: var(--space-4);">
        <h2 style="font-size: 1.125rem; font-weight: 600;">Item Name</h2>
        <span class="badge badge--warning">Pending</span>
      </div>
      <div class="card">
        <div class="card-title">Details</div>
        <p class="text-sm text-muted">Content goes here.</p>
      </div>
    </div>
  </div>
</body>
</html>
```

### Scaffold Instructions

When scaffolding:
1. Ask the user for the project name (used in `<title>` and `<h1>`).
2. Write `tokens.css` and `template.html` (renamed to `index.html`) into the target directory.
3. Replace `{{PROJECT_NAME}}` with the user's project name.
4. Remind the user of the text density constraints:
   - Buttons: max 3 words
   - Badges/pills: max 3 words
   - Card headers: max 5 words
   - Banners: max 15 words
   - Hero ledes: max 20 words
   - No explanatory prose in the UI — every piece of text should be a label, value, or status

---

## Design Principles (from EMIR)

These principles should be cited when explaining violations:

1. **Constraint as design.** The layout should structurally discourage prose. A 3-pane workbench has no room for paragraphs — and that's the point.

2. **Labels, not explanations.** Every visible text element should be a label, a value, or a status. If you need to explain something, use a tooltip or a separate docs page.

3. **Spatial hierarchy over text volume.** Achieve information density through layout structure (panes, rows, badges) not through more words.

4. **Functional typography.** Use font-size and weight to create hierarchy — `text-xs` (10px) for metadata, `text-sm` (13px) for primary content, `text-base` (16px) for headings. Don't use large display type with paragraph-length text.

5. **Compact density.** Padding `py-1.5` (6px) between list items, `gap-2` (8px) between elements, `p-2`/`p-3` for sections. Compact without cramped.

6. **Borders over shadows.** Use 1px solid borders for separation. Reserve shadows for elevation (popovers, modals).

7. **Fluent blue as the single brand color.** `oklch(0.55 0.18 250)` for actions and focus. Semantic colors (success green, warning amber, destructive red) only for status indication.
