# STYLE GUIDE — USyd Assessment Calendar

Companion to `usyd-assessment-calendar-BUILD-SPEC.md`. The build spec defines *what* the site
does; this defines *how it looks*. Where the two disagree on visual matters, this document wins.

The target is restrained and editorial — the feel of a well-set printed timetable, not a SaaS
landing page. Every decision below is already made. Implement the tokens as written. Do not
substitute "equivalent" values.

---

## 0. Things that must not appear

Treat this as a hard checklist. Any of these present means the work isn't done.

- Default framework favicon, or an unedited `<title>`
- Emoji in headings or UI labels (✨ 🚀 📅 ⚡ etc.), sparkle/AI iconography of any kind
- Gradient text, especially on the `h1`. No gradients anywhere except the one specified in §7.
- Tailwind default palette values, `indigo`/`violet`/`purple` in any form
- Inter, or the system-UI stack, as the primary typeface
- Lorem ipsum, invented statistics, testimonials, fake logos, "trusted by" anything
- Marketing-voice copy. Banned words and phrases: *seamlessly, effortlessly, transform,
  supercharge, elevate, unlock, streamline, empower, journey, game-changing, built for modern
  students, powerful yet simple, at a glance* (this last one especially — it will be tempting).
- The template skeleton: centred hero → 3-column feature grid → pricing → FAQ → footer. This
  product has **no marketing page at all**. The app *is* the homepage.
- Card-in-card nesting. Border + shadow + rounded corners stacked on nested containers.
- Scroll-triggered fade-in animations. Zero of them. Not one.
- Rounded-full avatar circles, "person" placeholder icons, stock photography, 3D blobs, mesh
  gradients, glassmorphism, dark-mode-only neon.

---

## 1. Design principles

1. **The data is the design.** A student opens this to find out when things are due. Ornament
   that delays that answer is a bug.
2. **Hairlines, not shadows.** Separation comes from 1px rules and whitespace. Elevation is
   reserved for exactly two elements (§5).
3. **One accent, used four times.** If the accent appears on every button and badge, it means
   nothing.
4. **Spacing carries meaning.** Related rows nearly touch; unrelated sections are far apart.
   Uniform gaps are the strongest generated-looking tell.
5. **Dense where it counts.** This is closer to a spreadsheet than a brochure. Generous margins
   around a *compact* core, not airy everything.

---

## 2. Typography

Two families. No third.

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
```

- **Instrument Sans** — all UI, body, data, labels. Neutral without being Inter.
- **Instrument Serif** — used in exactly three places: the app wordmark, the empty state's
  headline, and the 404. Nowhere else. It is a seasoning, not a system.

### Scale

Wide by design. Do not collapse these toward each other.

| Token | Size | Line-height | Tracking | Weight | Use |
|---|---|---|---|---|---|
| `--t-display` | `clamp(2.75rem, 6vw, 3.5rem)` / 44–56px | 1.05 | -0.028em | 400 (Serif) | Empty state, 404 |
| `--t-h1` | 28px | 1.15 | -0.022em | 600 | Session heading |
| `--t-h2` | 20px | 1.25 | -0.016em | 600 | Month dividers, panel titles |
| `--t-body` | 16px | 1.6 | 0 | 400 | Prose, descriptions |
| `--t-row` | 15px | 1.35 | -0.004em | 500 | Assessment rows |
| `--t-small` | 13.5px | 1.45 | 0 | 400 | Metadata, secondary |
| `--t-label` | 11.5px | 1.2 | +0.09em | 600, uppercase | Column labels, unit codes, badges |

Rules:

- Line-height is set **per size**, never globally. A single global `line-height` is a tell.
- Negative tracking on everything ≥ 20px; positive tracking only on `--t-label`.
- Prose and description text caps at **68 characters** (`max-width: 34em`). Data rows may run
  full width.
- All dates, times, weights, percentages and countdowns use
  `font-variant-numeric: tabular-nums;` so columns align vertically.
- Unit codes render as `--t-label` (uppercase, tracked out), never in a monospace font.
- Italic Instrument Serif appears exactly once: the word *"Unofficial"* in the disclaimer strip.

---

## 3. Colour

Near-monochrome, warm-tinted neutrals, one accent.

```css
:root {
  /* Neutrals — hue-shifted warm (30°), never pure grey */
  --paper:      #FBFAF8;   /* page background */
  --surface:    #FFFFFF;   /* raised surfaces only */
  --ink-900:    #1A1714;   /* primary text */
  --ink-700:    #4A433C;   /* secondary text */
  --ink-500:    #7D746A;   /* tertiary, metadata */
  --ink-300:    #B5ABA0;   /* disabled, past items */
  --rule:       #E5DFD7;   /* hairline borders */
  --rule-soft:  #F0ECE6;   /* internal dividers */

  /* Accent — ochre. Used FOUR places only (see below) */
  --accent:     #C2571A;   /* fills, today marker, ruler ticks */
  --accent-ink: #9A410F;   /* accent text on light bg — AA at 5.4:1 */
  --accent-wash:#FBEFE6;   /* 8% tint, selection + hover wash */

  /* Semantic — desaturated, not stoplight */
  --warn:       #8A6D1F;   /* approximate dates */
  --error:      #9B3A2E;   /* failed loads */

  --radius:     3px;       /* THE radius. One value. */
  --radius-pill:999px;     /* chips only */
}
```

### Where the accent is allowed

Only these four. Nowhere else.

1. The "today" marker (the rule in the list view, the dot on the term ruler)
2. The primary action — the **Download .ics** button
3. `:focus-visible` rings
4. `::selection` background

Buttons that are not the primary action are text-coloured with a hairline border. Links are
`--ink-900` with a 1px underline offset 3px, becoming `--accent-ink` on hover. Badges, icons,
chips and counts are **all neutral**.

### Unit colour coding

The build spec calls for per-unit colours in the list and calendar. Do **not** use a rainbow. Use
a single-hue ladder — five steps of the ochre-to-ink axis, plus a swatch shape difference so it
survives colourblindness and greyscale printing:

```css
--u1: #C2571A;  --u2: #6E5B3E;  --u3: #2E4A46;
--u4: #7A3E4A;  --u5: #3D4668;
```

Unit colour appears only as a **3px left edge** on rows and a 8×8px square before the code. Never
as a filled background, never as coloured text.

### Dark mode

Support it via `prefers-color-scheme`. Invert with the same warm tint — `--paper: #16130F`,
`--ink-900: #F2EDE6`. The accent stays the same hue but lightens to `#E0813F` to hold contrast.
Do not add a toggle; follow the OS.

---

## 4. Layout

**No page is a centred stack of full-width sections with identical max-widths.** Structure:

```
┌───────────────────────────────────────────────────────────────┐
│ header — full bleed, 1px bottom rule, 64px tall               │
│   wordmark (left)              session selector (right)       │
├───────────────────────────────────────────────────────────────┤
│ TERM RULER — full bleed, 72px tall, 1px bottom rule           │  ← §7
├───────────────────────────────────────────────────────────────┤
│  content: max-width 1120px, but a 60/40 asymmetric grid       │
│  ┌────────────────────────────────┬──────────────────────┐    │
│  │ assessment list (60%)          │ rail (40%)           │    │
│  │                                │  · unit picker       │    │
│  │                                │  · selected chips    │    │
│  │                                │  · download          │    │
│  │                                │  · disclaimer        │    │
│  └────────────────────────────────┴──────────────────────┘    │
└───────────────────────────────────────────────────────────────┘
```

The asymmetry is deliberate and is the layout's one broken symmetry. The rail is **sticky** on
desktop and does not scroll with the list.

The term ruler bleeds edge-to-edge past the 1120px container. That is the second intentional
break — one element escaping the grid.

### Spacing scale

```css
--s-1: 4px;  --s-2: 8px;  --s-3: 12px;  --s-4: 20px;
--s-5: 32px; --s-6: 56px; --s-7: 96px;
```

Apply with intent, not uniformly:

- Within a row (code → name → weight): `--s-3`
- Between consecutive rows in the same week: `--s-2` — they should feel like one block
- Between weeks: `--s-4`
- Between month groups: `--s-6` with the month label hanging in the left margin
- Above/below the term ruler: `--s-5`

Never write `gap: 24px` on every container.

### Breakpoints

Test all four. The 768–1024 band is where generated layouts break.

| Width | Behaviour |
|---|---|
| 375px | Single column. Rail collapses to a top block. Term ruler shrinks to 48px, keeps ticks, drops labels. Row layout stacks name under the date. |
| 768px | Still single column, but the rail becomes a 2-up horizontal band (picker left, download right). Ruler shows every third week label. |
| 1024px | Grid engages at 58/42. Rail becomes sticky. |
| 1440px | Full 60/40 at 1120px max-width. Month labels move into the left margin. |
| 2560px | Container does **not** grow. Increase page side padding only; the ruler still bleeds full width. Do not let line lengths stretch. |

---

## 5. Surfaces, borders, shadows

- Default surface: `--paper`. Rows sit directly on it with a `--rule-soft` divider. **No cards.**
- Exactly two elements are elevated, and they use the same near-invisible diffuse shadow:

```css
--shadow: 0 1px 2px rgba(26,23,20,.04), 0 8px 24px -12px rgba(26,23,20,.10);
```

1. The **autocomplete dropdown**
2. The **assessment detail panel**

Nothing else has a shadow. Not buttons, not the header, not the rail.

- Borders are `1px solid var(--rule)`. Never 2px, never a shadow-as-border.
- `--radius: 3px` everywhere. The only exception: selected-unit chips are `--radius-pill`. That
  single deviation is what makes the 3px read as chosen rather than default.

---

## 6. Interactive states

Every interactive element defines `:hover`, `:focus-visible`, `:active`, and `:disabled`.
**Vary the timings** — a single `duration-300` across the site is a tell.

| Element | Hover | Focus-visible | Active | Timing |
|---|---|---|---|---|
| Assessment row | bg → `--accent-wash` | 2px `--accent` outline, offset -1px | — | `background 90ms linear` |
| Primary button | bg darkens to `--accent-ink` | outline 2px offset 3px | `translateY(1px)`, no shadow | `background 140ms ease-out, transform 60ms` |
| Secondary button | border → `--ink-500` | as above | `translateY(1px)` | `border-color 200ms ease` |
| Unit chip remove | ⓧ goes `--ink-300` → `--error` | outline | scale(.94) | `color 120ms, transform 80ms` |
| Autocomplete item | bg `--rule-soft` | same as hover + left 3px `--accent` | — | `none` (instant — it's a menu) |
| Link | `--accent-ink`, underline thickens to 1.5px | outline | — | `color 160ms ease` |
| Ruler tick | grows 4px taller, tooltip | — | — | `height 110ms cubic-bezier(.2,.8,.3,1)` |

Focus ring: `outline: 2px solid var(--accent); outline-offset: 2px;` — never `outline: none`
without a replacement. Keyboard tab order must follow visual order. The autocomplete supports
↑/↓/Enter/Escape.

### Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; }
}
```

---

## 7. The signature element — the Term Ruler

This is the one thing nobody defaults to, and the site's memorable idea. Build it properly.

A full-bleed horizontal strip under the header showing the **entire teaching session** as a single
line, from Week 1 to the end of the exam period.

- A 1px baseline in `--rule` spans the viewport.
- Week boundaries are 6px tick marks in `--rule`, labelled `01`…`13` in `--t-label` beneath.
  The mid-semester break renders as a 1px dotted segment instead of solid.
- Every assessment in the selected units is a **vertical tick rising from the baseline**, with
  **height proportional to its weight** — 4px at 2%, 44px at 50%. Ticks use the unit's colour from
  the ladder in §3.
- Coincident deadlines stack side by side at 2px wide, 1px apart, forming a visible "wall" where
  a week is loaded. That density *is* the information.
- "Today" is a solid `--accent` vertical line running the full 72px height, with the date in
  `--t-label` above it.
- Assessments with only a week number render at 40% opacity.
- Hovering a tick shows a small tooltip (unit code, name, weight, date) and dims all others to 30%.
- Clicking a tick scrolls the list to that assessment and briefly flashes its row background.
- With no units selected, the ruler shows the baseline, week ticks and today marker only — it is
  never empty or hidden.

It must be readable at 375px (48px tall, labels dropped, ticks preserved).

---

## 8. Required states

Design all four. Missing states are the most common generated-site gap.

**Loading.** Skeleton rows — 3 grey bars at `--rule-soft`, sized to the real row geometry, with a
slow 1.4s opacity pulse between .4 and .7. Not a spinner. Not shimmer-sweep.

**Empty (no units selected).** The only place `--t-display` in Instrument Serif appears in the
app. Copy exactly:

> ### Nothing due yet.
> Add a unit code to see every assessment for the semester in one list.

Below it, a single line of `--t-small` in `--ink-500` suggesting three real codes as clickable
text: `AMME2200 · ELEC3204 · COMP3308`.

**Error (data fetch failed).** Left-aligned, `--error` hairline on the left edge, no icon:

> ### Couldn't load unit data.
> The assessment data failed to download. This is usually temporary.
> [ Try again ]

**Unit has no assessments parsed.** Inline under the chip, `--t-small`, `--warn`:

> Outline published but no assessments could be read. [View the outline ↗]

---

## 9. 404 page

A real one, at `/404.html`. Same header. Instrument Serif display, off-centre — sitting at the
left edge of the content grid, not centred:

> ### Week 14.
> There's no such page — the same way there's no such teaching week.
> [ Back to your assessments ]

No illustration. No emoji.

---

## 10. Details that are usually skipped

```css
::selection { background: var(--accent-wash); color: var(--ink-900); }

html { caret-color: var(--accent); scrollbar-gutter: stable; }

/* Scrollbar — thin, neutral, no track */
* { scrollbar-width: thin; scrollbar-color: var(--ink-300) transparent; }
*::-webkit-scrollbar { width: 10px; height: 10px; }
*::-webkit-scrollbar-thumb { background: var(--ink-300); border-radius: var(--radius-pill);
  border: 3px solid transparent; background-clip: content-box; }
*::-webkit-scrollbar-track { background: transparent; }
```

**Favicon.** An SVG favicon drawn inline, not a downloaded asset: a single ochre vertical tick on
a paper-coloured square — a one-element quotation of the term ruler. Ship `favicon.svg` plus a
32px PNG fallback.

**Head tags** — fill in properly, no placeholders:

```html
<title>USyd Assessment Calendar</title>
<meta name="description" content="Enter your University of Sydney unit codes and get every assessment due date for the semester in one list, exportable to your calendar. Unofficial.">
<meta property="og:title" content="USyd Assessment Calendar">
<meta property="og:description" content="Every due date for your units, in one place.">
<meta property="og:image" content="/og.png">
<meta name="theme-color" content="#FBFAF8" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#16130F" media="(prefers-color-scheme: dark)">
```

**OG image** (`/og.png`, 1200×630): generate it as a static asset — paper background, the wordmark
in Instrument Serif at the left, and a rendering of the term ruler across the lower third. No
text stacked in the centre. Produce it with a small Python/Pillow script committed as
`tools/make_og.py` so it's reproducible.

**Accessibility floor.** All text meets AA. `--accent-ink` (not `--accent`) for accent-coloured
text on light backgrounds. Every icon-only control has an `aria-label`. The list is a real
`<ul>`; the calendar grid uses `role="grid"`. Announce unit add/remove via an `aria-live="polite"`
region. Test the whole flow — add a unit, switch view, download — with the keyboard only.

**No JS fallback.** A `<noscript>` line in the body explaining the site needs JavaScript, styled
like the error state.

---

## 11. Copy

Use these strings verbatim. Do not rewrite them into something smoother.

| Location | Copy |
|---|---|
| Wordmark | `Assessment Calendar` (Instrument Serif) + `USyd` in `--t-label` beneath |
| Disclaimer strip | *Unofficial.* Dates come from published unit outlines and change without notice. Canvas is the source of truth. Updated {date}. |
| Unit input placeholder | `Unit code — e.g. AMME2200` |
| Primary button | `Download .ics` |
| After download | `8 events exported. 2 assessments had no fixed date and were left out:` followed by the list. |
| Approximate badge | `approx.` |
| Approximate tooltip | `The outline gives only a week number. The exact date is on Canvas.` |
| View toggle | `List` / `Calendar` |
| Row metadata format | `6% · 23:59 · Week 5` — middle dots, no labels |
| No-fixed-date group heading | `No fixed date` |
| Exam row detail | `Formal exam period` — quoted from the outline, not paraphrased |

Tone: factual, slightly dry, sentence case. Full stops on complete sentences. No exclamation
marks anywhere in the interface.

---

## 12. Self-check before declaring done

- [ ] Zero emoji, zero gradients, zero scroll-reveal animations
- [ ] Accent appears in exactly four roles; count them in the stylesheet
- [ ] One border radius (plus the single documented pill exception)
- [ ] Shadow declared once, used on two elements
- [ ] At least five distinct spacing values in use, non-uniformly
- [ ] Seven type sizes in use, with per-size line-heights
- [ ] Term ruler works at 375px and 2560px
- [ ] Loading, empty, error and no-assessment states all implemented
- [ ] `/404.html` exists and is styled
- [ ] Favicon, OG image, meta description all real
- [ ] Full keyboard pass completes the add → export flow
- [ ] Greyscale screenshot still legible (unit differentiation survives)
- [ ] Search the codebase for `indigo`, `violet`, `Inter`, `rounded-xl`, `duration-300` — no hits
