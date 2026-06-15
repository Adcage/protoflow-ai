# Dashboard quality checklist

P0 = must pass; P1 = should pass; P2 = nice to have.

## P0 — must pass

- [ ] **All colors are tokenized.** No raw hex outside `:root`. Use `var(--bg)`, `var(--surface)`, `var(--fg)`, `var(--muted)`, `var(--border)`, `var(--accent)`, `var(--good)`, `var(--bad)` only.
- [ ] **No invented metrics.** Every KPI value must come from the user brief or be clearly labelled `[REPLACE]`.
- [ ] **No filler labels.** No "Metric A", "KPI 1", "Label here". Either use real business labels or mark with `[REPLACE]`.
- [ ] **Delta direction is correct.** Green for positive/up, red for negative/down. If a metric's direction is inverted (e.g. latency down = good), annotate the delta text instead of flipping colors silently.
- [ ] **Sidebar has one active item.** Only the current page is highlighted.
- [ ] **Primary CTA in topbar is the single strongest action.** Usually "Export", "Create report", or "Add widget".
- [ ] **Empty states are handled.** Every panel that may lack data shows a clear empty message, not a blank box.
- [ ] **Mobile reflow at 900px.** Sidebar collapses or becomes a rail; KPIs go 2×2; chart and side panel stack.
- [ ] **No horizontal scroll on desktop.** The layout must fit a 1280px viewport.
- [ ] **Table status uses pills, not colored rows.** Keep rows neutral; status is a small pill.

## P1 — should pass

- [ ] **KPI row has 3–4 cards.** More cards dilute focus; fewer looks empty.
- [ ] **Chart has a clear title and axis/hint.** Even a placeholder chart should say what it measures.
- [ ] **Date range or filter is visible.** Dashboards are time-bound; show the current scope.
- [ ] **Numerics use tabular figures.** Prevent jitter when numbers update.
- [ ] **Hover states on rows and nav items.** Provide clear affordance.
- [ ] **Consistent 8px grid.** Padding, margins, and gaps should align to multiples of 4 or 8.
- [ ] **No "Learn more" or generic CTAs.** Buttons say exactly what happens: "Export CSV", "Add alert", "Invite member".

## P2 — nice to have

- [ ] **Chart line uses `var(--accent)` or a color-mix.** Keep the palette minimal.
- [ ] **Loading skeleton for data panels.** If real data were async, show a neutral skeleton instead of spinners.
- [ ] **Keyboard-navigable table.** Focusable rows or actionable cells.
- [ ] **Tooltips on KPI deltas.** Brief explanation of the comparison period.

## Anti-slop spot-check

- Does the dashboard look like it belongs to a real product?
- Are the KPIs things an actual user would check daily?
- Is the density appropriate, or is there excessive whitespace?
- Would a screenshot of this dashboard be useful in a status meeting?
