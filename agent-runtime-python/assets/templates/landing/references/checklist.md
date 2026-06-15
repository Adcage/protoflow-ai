# Landing page quality checklist

P0 = must pass; P1 = should pass; P2 = nice to have.

## P0 — must pass

- [ ] **All colors tokenized.** No raw hex outside `:root`. Use `var(--bg)`, `var(--surface)`, `var(--fg)`, `var(--muted)`, `var(--border)`, `var(--accent)` only.
- [ ] **No filler copy.** Zero "Feature One / Feature Two", lorem ipsum, "Lorem ipsum dolor", "Your tagline here".
- [ ] **No invented metrics.** Stats must come from the brief or be clearly labelled `[REPLACE]`.
- [ ] **H1 ≤14 words.** If longer, rewrite.
- [ ] **Lead ≤2 sentences.** Must fit within `max-width: 56ch`.
- [ ] **Hero has exactly one primary CTA.** One secondary or text link is allowed. No third button.
- [ ] **Feature descriptions name user value, not technology.** "Sync the files you changed" beats "Block-level delta sync".
- [ ] **CTA buttons say what happens.** "Start free" beats "Get Started". "Read the story" beats "Learn More".
- [ ] **Accent appears at most 3× per screen.** Primary button, feature numbers, one other flourish.
- [ ] **No emoji icons.** Use inline SVG marks or tasteful mono glyphs.
- [ ] **No purple/violet gradients** or generic AI-startup palettes.
- [ ] **`data-od-id` on every top-level section.** Hero, features, proof, closing, footer.
- [ ] **Mobile reflow at 800px.** Feature grid collapses to one column; text stays readable.

## P1 — should pass

- [ ] **One decisive flourish.** A strong stat, a real quote, or a product screenshot. Just one.
- [ ] **Social proof is specific.** Named companies, real quotes, or concrete outcomes. "Trusted by 10,000 teams" is acceptable only if sourced.
- [ ] **Hover states on buttons and links.** Provide clear affordance.
- [ ] **Consistent vertical rhythm.** 80px section padding, no arbitrary gaps.
- [ ] **Feature headings are concrete.** "Block-level diffs" beats "Fast sync".
- [ ] **Footer is minimal.** Copyright + 2–3 links. No sitemap.

## P2 — nice to have

- [ ] **Sticky topnav.** Optional; keep it subtle.
- [ ] **Smooth scroll to anchored sections.** Use `scroll-behavior: smooth` on html.
- [ ] **Focus-visible styles for keyboard users.**
- [ ] **Open Graph / meta description.** If the head is customized.

## Anti-slop spot-check

- Does the headline sound like it could be any startup?
- Are the features three variations of "easy, fast, secure"?
- Is there a generic gradient, emoji, or purple accent?
- Would a visitor know what the product does in 5 seconds?

If yes to any, rewrite the weakest section and remove one decorative element.
