# Dashboard layout rhythm

Dashboard pages should feel dense but scannable. Every element must justify its pixel count.

## Page skeleton

```
┌─────────────────────────────────────────────────────────┐
│  sidebar │  topbar (title + date range + primary CTA)   │
│          ├─────────────────────────────────────────────┤
│          │  KPI row (3–4 cards)                         │
│          ├─────────────────────────────────────────────┤
│          │  main chart  │  side list / alert panel      │
│          ├─────────────────────────────────────────────┤
│          │  recent events / detail table                │
└──────────┴─────────────────────────────────────────────┘
```

## Rhythm rules

1. **Sidebar first.** A fixed 220–240px sidebar anchors navigation. Keep it flat: one active state, one hover state, group labels in muted uppercase.
2. **Topbar is a single row.** Page title on the left, contextual filters and primary action on the right. No wrapping.
3. **KPI row = 3 or 4 cards.** Never 5+. Each card has a label, a big value, and a delta. Use color only for deltas (green up / red down). The value itself stays neutral.
4. **Main chart area is 2fr, side panel is 1fr.** The chart gets the visual weight. The side panel holds ranked lists, alerts, or quick filters.
5. **Recent events table below.** Time, subject, event, status. Status uses a subtle pill, not a colored background on the whole row.
6. **Collapse at 900px.** Sidebar becomes a top hamburger or remains a rail; KPIs go 2×2; main/side stack vertically.

## Token discipline

- All colors come from `:root` variables: `--bg`, `--surface`, `--fg`, `--muted`, `--border`, `--accent`, `--good`, `--bad`.
- No raw hex outside `:root`.
- No gradient backgrounds on panels. The chart area may use a faint gradient only for the data visualization background.
- Use system fonts. Dashboards are tools, not editorial experiences.

## Typography

- Page title: 20px, medium weight, tight letter-spacing.
- KPI value: 28px, tabular numerics.
- KPI label: 12px uppercase, muted.
- Table headers: 11px uppercase, muted.
- Body: 14px/1.5.

## Spacing

- Sidebar padding: 16px.
- Main padding: 0 28px 56px.
- Gap between KPIs: 16px.
- Gap between main chart and side panel: 16px.
- Panel internal padding: 20px.

## Data tables

- Headers aligned with content (left for text, right for numbers).
- Row hover: faint `var(--bg)` tint.
- Never use colored row backgrounds for status; use pills.
- Empty states: show a centered message inside the panel, not a blank panel.
