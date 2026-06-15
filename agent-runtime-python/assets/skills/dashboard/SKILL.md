---
name: dashboard
description: |
  Admin / analytics dashboard for monitoring operational data. Use when the brief
  asks for a "dashboard", "admin", "analytics", "control panel", or "后台/看板" screen.
  Produces real project files through file tools for single_file, multi_file, or
  Vue project output modes.
triggers:
  - "dashboard"
  - "admin panel"
  - "analytics"
  - "control panel"
  - "后台"
  - "管理后台"
  - "看板"
  - "数据看板"
od:
  mode: prototype
  platform: desktop
  scenario: operations
  preview:
    type: html
    entry: index.html
  design_system:
    requires: true
    sections: [color, typography, layout, components]
  craft:
    requires: [state-coverage, accessibility-baseline, laws-of-ux]
ac:
  when_to_use: "Use when generating an admin panel, analytics dashboard, operations screen, or data monitoring interface."
  target_code_gen_types: ["single_file", "multi_file", "vue_project"]
  related_templates: ["dashboard"]
  recommended_seeds: ["vue-dashboard"]
  output_contract: "single_html_file"
---

# Dashboard Skill

Produce a single-screen admin / analytics dashboard with real data and complete functionality.

## Workflow

1. **Read the active DESIGN.md** (injected above). Colors, typography, spacing,
   component styling all come from it. Do not invent new tokens.
2. **Classify** what the dashboard monitors (sales, traffic, usage, incidents,
   ops, etc.) from the brief. Generate specific, plausible metric names and
   values — no "Metric A / Metric B" placeholders.
3. **Lay out** the required regions:
   - **Left sidebar** (220–260px): brand mark at top, 6–8 nav links with
     icons, active state uses the DS accent.
   - **Top bar**: page title on the left, search input + user avatar / status
     on the right.
   - **Main**:
     - Row 1: 3–4 KPI cards (label + big number + delta vs. prior period).
     - Row 2: one primary chart (full width or 2/3) — render as an inline SVG
       line / bar / area chart drawn from real-looking numbers.
     - Row 3: one secondary chart or table (recent events, top items, etc.).
4. **Write** real project files using file tools:
   - For `single_file` mode: one complete `index.html` with inline `<style>` and `<script>`.
   - For `multi_file` mode: `index.html`, `style.css`, and `script.js`.
   - For `vue_project` mode: Vue SFC files under `src/`, preserving the seed structure.
   - Use CSS Grid for the overall layout; Flexbox inside cards.
   - Semantic HTML: `<aside>`, `<header>`, `<main>`, `<section>`.
   - Tag each logical region with `data-od-id="slug"` for comment mode.
5. **Charts**: inline SVG only, no JS libraries. A line chart is ~10 lines of
   `<polyline>` with a subtle area fill. A bar chart is N `<rect>`s with
   DS-accent fill. Label axes lightly (muted text, smaller scale).
6. **Self-check**:
   - Every color comes from DESIGN.md tokens.
   - Accent used at most twice (sidebar active + one chart highlight).
   - Sidebar + top bar are sticky; main scrolls independently.
   - Density matches the DS mood — airy DSes get more padding, dense DSes
     (trading, crypto) tighten rows.
   - Include loading, empty, error, and normal states for all data-dependent views.

## Hard rules

- Use real Chinese business text, not placeholder content like "Metric A" or "Card 1".
- Use tools to write actual files to the workspace; do not emit content wrapped in `<artifact>` tags.
- Include real chart data and table data.
- Ensure all interactive elements are functional.
- For Vue project mode, preserve `package.json`, `src/main.ts`, and `src/App.vue` consistency with the seed.

## Output contract

Use file tools (`write_file`) to write real project files under the workspace.

- For `single_file` output mode: write one complete `index.html` with inline `<style>` and `<script>`.
- For `multi_file` output mode: write `index.html`, `style.css`, and `script.js`.
- For `vue_project` output mode: write Vue SFC files under `src/`, preserving the seed project structure.
- Do not wrap output in `<artifact>` tags.
- Do not leave placeholder content like "Metric A", "Card 1", "Lorem ipsum", or "Feature One".
