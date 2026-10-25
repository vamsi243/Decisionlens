# Decision Lens design

How the board looks and why. Colours and fonts live in [`web/src/styles/tokens.css`](web/src/styles/tokens.css); this file is the guide to using them. The look is **Royal Purple**: the league's deep purple as the frame, a lilac-white page, white cards, heavy geometric headings. It nods to the Premier League's identity without using its lion, wordmark, typeface or name.

## Principles

1. **The pitch is the hero.** Everything else frames it; nothing sits on top of it except what the engine draws.
2. **Colour carries meaning.** Green means the chance went up, red means it went down, blue is Riverside, yellow is Hillton, cyan/teal marks a key moment, pink means live. Nothing decorative uses those colours.
3. **Numbers come from the engine** and are set in the mono face, so they read as data, not prose.
4. **Quiet until it matters.** Purple and white most of the time; colour only on what changed.
5. **Readable everywhere.** Text meets 4.5:1, motion respects reduced-motion, every control works with a keyboard, and the whole board works in six languages.

## Colour

### Brand and surfaces

| Token | Light (page) | On the purple chrome | Use |
| --- | --- | --- | --- |
| `--chrome` | `#37003C` | — | Nav bar, the match copilot, primary buttons, the score pill |
| `--bg` | `#F6F3F8` | `#37003C` | Page background |
| `--surface` | `#FFFFFF` | `#4A0F50` | Cards, panels |
| `--panel-2` | `#EDE6F0` | `#2A002E` | Inset areas, stat tiles |
| `--ink` | `#2B0030` | `#FFFFFF` | Text, primary buttons |
| `--muted` | `#6E5A73` | `#CDBBD6` | Secondary text (5.6:1 / 9:1) |
| `--muted-2` | `#8A7A8F` | `#A08AAA` | Tertiary text, axis labels |
| `--line`, `--line-2` | purple at 10% / 20% | white at 14% / 24% | Hairlines and dividers |

Anything inside an element with the `chrome` class picks up the right-hand column automatically, so buttons, toggles and selects need no dark variant.

### Meaning

| Token | Value | Means | Never use it for |
| --- | --- | --- | --- |
| `--key` | `#087380` on light, `#04F5FF` on chrome | Key-moment text: minutes, eyebrows, the active card's border | Warnings, decoration |
| `--key-bright` | `#04F5FF` | Key-moment fills: the card's type tag, timeline markers, your questions in the copilot (purple text on it) | Text on white |
| `--live` | `#E90052` | The LIVE badge and dot | Anything else, so "live" stays unmistakable |
| `--green` | `#118453` | Chance went up, the better option, success | Team colour |
| `--red` | `#C0362F` | Chance went down, turnovers, errors | Live state (that is pink) |
| `--amber` | `#BA6603` | Fatigue warnings only | Key moments (that is `--key`) |

### Match (unchanged across themes)

| Token | Value | Use |
| --- | --- | --- |
| `--pitch-1`, `--pitch-2` | `#2F8F3A`, `#29823A` | Mowing stripes |
| `--pitch-line` | white at 72% | Markings |
| `--riv`, `--riv-rim`, `--riv-ink` | `#2F7DE1`, `#0C3F86`, `#185FA5` | Riverside fill, outline, text on white |
| `--hil`, `--hil-rim`, `--hil-ink` | `#F2C230`, `#8A6400`, `#7A5900` | Hillton fill, outline, text on white |
| `--on-pitch`, `--on-pitch-halo` | white, dark green at 85% | Labels drawn on grass |
| `--heat` | `#FF4D3D` | Heat map |

Cyan (`#04F5FF`) is only readable on the purple. On white it becomes the teal `#087380`; the token switches for you.

## Typography

| Role | Face | Weight | Where |
| --- | --- | --- | --- |
| Display | Urbanist (variable) | 800, 900 for the score | Page titles, card titles, team names, the brand |
| Body | Inter (variable) | 400, 500, 600 | Everything else |
| Numbers | DM Mono | 400, 500 | Clock, percentages, stats (`.num`, tabular figures) |

All three are SIL OFL and self-hosted through Fontsource. Headings use `font-display font-extrabold tracking-tight`. Sentence case everywhere; capitals only for the LIVE badge and short eyebrows.

| Size | Use |
| --- | --- |
| 40–48px | Page titles (`text-4xl`/`lg:text-5xl`) |
| 20–26px | Card and section titles |
| 14–16px | Body |
| 12–13px | Labels, captions |
| 11px | Chips and the smallest captions only |

## Shape, depth and spacing

- Radii: `--radius-xl` 32px for page panels, `--radius-lg` 20px (`rounded-2xl`) for cards, `--radius-md` 12px for buttons and chips; pills are fully round.
- Shadows are faint (`--shadow-sm/md/lg`); hierarchy comes from surface colour and borders, not depth.
- Spacing follows Tailwind's 4px scale: 12–16px inside cards, 16–24px between them, 40–56px between page sections. No section is taller than it needs to be.

## Motion

- One brand ease, `--ease` = `cubic-bezier(.22,1,.36,1)`, 200–700ms.
- **Nav underline:** one white 2px bar glides (spring) to the link you hover or focus and back to the current page when you leave.
- **Cards** fade up 10px when they arrive; the active moment gets a teal border.
- **How it works film:** a five-stage loop (3.2s a stage) with a progress line, pausing on hover; each stage plays a small scene.
- **Board:** 60 fps interpolation between 10 Hz frames; option arrows draw in.
- Everything above collapses to an instant change under `prefers-reduced-motion`.

## Layout

### Nav (every page)

Purple bar, sticky. Brand on the left, then Home · How it works · Live · Recap as plain text links with the gliding white underline; sound, Analyst/Fan and language on the right. No pills or highlight boxes on the links.

### Live

```
┌ nav ───────────────────────────────────────────────────────────────┐
├──────────────────────────────────────┬──┬──────────────────────────┤
│ score strip: teams · score · clock · LIVE │  │ Key moments (scrolls)    │
│ ┌ table card (white) ────────────────┐ │⋮ │                          │
│ │ pitch                              │ │  ├──────────────────────────┤
│ │ play · speed · timeline · tools    │ │  │ Match copilot (purple)   │
│ └────────────────────────────────────┘ │  │                          │
│ legend                                 │  │                          │
└──────────────────────────────────────┴──┴──────────────────────────┘
```

- The handle (⋮) resizes the split: drag, arrow keys (Shift for bigger steps), Home/End, double-click to reset. The pitch takes 40–72% of the width and the choice is saved per browser.
- The right column is at least 820px tall and otherwise as tall as the table. Moments (top) and the copilot (bottom, a little larger) share it and scroll inside, so a smaller pitch gives them more room.
- Below 1024px everything stacks: score, pitch, moments, copilot.

### How it works

One short page: an intro with the system film beside it, then five stage cards in two columns (Explain spans both, with the agent diagram and the router table). No full-screen sections or scroll snapping.

### Home and Recap

Home is a promo page with a looping key-moment clip. Recap is a scroll story with the pitch pinned beside green/red bullets.

## Components

| Component | Look |
| --- | --- |
| Score strip | White card; team squares in team colours; the score in white on a purple pill (Urbanist 900); clock in mono; pink LIVE pill |
| Moment card | White card; a cyan tag with the type and minute, team square and name; Urbanist 24px title in purple; the chance before → after in Urbanist 900 at 36px, the after in green or red, "with <swap>"; green ▲ / red ▼ lines (no tint); the agent's line under a hairline, three lines then More. Cards stack one after another in the moments column |
| Copilot | Purple panel under the moments: CopilotKit in dark mode with its theme variables pointed at the palette (`styles/index.css`); answers in white, your questions on cyan, a white input box; no icon in the header |
| Table card | White card: the pitch at full width; then one control bar (play/pause, speeds, the timeline with cyan diamond markers and a football for each goal, ringed in the scoring team's colour, stats and settings) that puts the timeline on its own row when the card is under 576px; then each bench in its own box, side by side above 512px and stacked below (container queries, so it follows the split, not the window) |
| Stat tile | `--panel-2` background, mono value, muted label |
| Buttons | Primary: purple fill, white text. Secondary: white with a hairline border. On chrome they invert automatically |
| Chips | Fully round; tinted background in the same hue as the text (12% green/red) |

## Icons

Lucide outline icons for controls only (play, settings, replay, follow, language). No AI-style decoration: no sparkles, magic wands, robots or verified badges. The logo (aperture mark) is the only brand icon.

## Accessibility

- Contrast: body text ≥ 4.5:1 on every surface listed above; muted text 5.6:1 on the page and 9:1 on the purple.
- Colour is never the only signal: chance chips carry ▲/▼, the live badge says LIVE, teams also have names and numbers.
- Real buttons and links throughout; the resize handle is a focusable `separator` with arrow-key control; the nav underline follows keyboard focus.
- Motion respects `prefers-reduced-motion`.

## Language

Every visible string goes through `t("…")` or `msg("…")` (see CODE_EXPLAINER, "How the language switch works"). Layouts must allow about 40% longer text (German, Portuguese) and Devanagari: no fixed widths on labels, buttons that wrap rather than clip.

## Changing the look

1. Change values in `tokens.css` (both the `:root` and the `.chrome` blocks), not in components.
2. Add a new colour as a token and map it in `styles/index.css` (`--color-*`) so Tailwind classes exist for it.
3. Keep the meaning table true: if a colour starts meaning something new, give it a new token.
4. Check contrast on both the page and the purple.
