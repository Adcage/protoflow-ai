# Landing page layout rhythm

Landing pages must make one promise, prove it, and ask once.

## Page skeleton

```
┌─────────────────────────────────────────────┐
│  topnav (logo + links + sign-in)            │
├─────────────────────────────────────────────┤
│  hero                                       │
│  h1 + lead + primary/secondary CTAs         │
├─────────────────────────────────────────────┤
│  features (3-column grid)                   │
├─────────────────────────────────────────────┤
│  social proof (logo row or testimonial)     │
├─────────────────────────────────────────────┤
│  optional: pricing / detail / stats         │
├─────────────────────────────────────────────┤
│  closing CTA strip                          │
├─────────────────────────────────────────────┤
│  footer                                     │
└─────────────────────────────────────────────┘
```

## Rhythm rules

1. **One hero, one promise.** The H1 should be ≤14 words. The lead sentence is ≤2 sentences / 56 characters wide.
2. **Two CTAs max in hero.** Primary + secondary or primary + text link. No third option.
3. **Features are exactly three.** One row, equal weight. Each feature has a number, a specific heading, and a concrete description.
4. **Social proof is logos or a quote, not both.** If logos, 4–6 names. If quote, one decisive sentence with attribution.
5. **Closing CTA is a single ask.** Contrasting background, generous padding, one button.
6. **Footer is minimal.** Copyright, privacy, terms. No sitemap.

## Token discipline

- Six root tokens: `--bg`, `--surface`, `--fg`, `--muted`, `--border`, `--accent`.
- No raw hex outside `:root`.
- Accent is the action color: primary button, link text, feature numbers.
- White or surface background for the features band to create separation.

## Typography

- H1: `clamp(44px, 6vw, 76px)`, line-height 1.05, tight tracking.
- Lead: 19px, muted, max-width 56ch.
- Feature number: 12px mono, accent, uppercase.
- Feature heading: 18px, medium.
- Feature body: 14.5px, muted.
- Section label ("Used by teams at"): 14px uppercase, muted, wide tracking.

## Spacing

- Header padding: 20px 0.
- Hero padding: 100px 0.
- Standard section padding: 80px 0.
- Container max-width: 1080px, horizontal padding 32px.
- Feature grid gap: 32px.
- Logo row gap: 56px.

## Responsive

- At 800px, feature grid becomes a single column.
- Hero text remains left-aligned; CTA buttons stack if needed.
- Logo row wraps.

## Section rhythm — when in doubt

For a minimal SaaS landing:
1. Hero
2. Features (3)
3. Social proof
4. Closing CTA
5. Footer

For a richer landing, insert **one** of the following between features and social proof:
- Stats row (3 numbers max)
- Split detail (text + product visual)
- Testimonial quote

Never stack two optional sections back-to-back.
