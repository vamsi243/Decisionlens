# Decision Lens: Build Plan

Oct 24, 2026 · @Sai

A phase-by-phase build specification for a coding agent. Submission deadline: Oct 28, 2026, about 6pm Sydney (27 Oct 11:59pm PT).

## How to use this plan

Paste this whole document into the repo as `docs/BUILD_PLAN.md` and tell the coding agent: *"Read docs/BUILD\_PLAN.md and AGENTS.md, then do Phase 0. Stop at its checkpoint."* Then continue one phase at a time.

**Working rules for the coding agent**

1. **One phase at a time.** Finish every task and acceptance check in a phase, then stop and summarise what changed before starting the next.
2. **Local first.** Build and run everything with `RUN_MODE=local`. Azure adapters come in Phase 8 only.
3. **Never invent numbers in the language model.** Every probability, stat and metric comes from the engine; agents only explain engine output.
4. **Verify fast-moving APIs before coding.** Check the current official docs or GitHub for Microsoft Agent Framework, the MCP Python SDK, Azure OpenAI and Azure AI Translator SDKs, and use what they say now, not memory.
5. **No secrets in the repo.** Keys live in `.env` (gitignored); commit only `.env.example`.
6. **Tests and lint pass before every commit.** Small commits with clear messages (`feat(engine): add aerial duel probability`).
7. **Keep docs current.** Update `README.md`, `FEATURES.md`, `ARCHITECTURE.md` and `CODE_EXPLAINER.md` at the end of each phase.
8. **Ask, don't guess,** when a decision changes scope, cost or the data contract.

Phase 0 also creates a short `AGENTS.md` at the repo root that repeats these rules, so every session picks them up.

## Project summary and hackathon expectations

**Decision Lens: Every moment, every option, every fan.** A live match intelligence app for the Microsoft Premier League "Inside the Game" hackathon. It streams a fully synthetic football match, shows it on a sleek 2D tactics board, and at key moments explains what happened, what was possible and who could have done it, with every number backed by a transparent probability engine and every explanation written by Azure OpenAI agents.

The brief requires one pipeline with five stages. Each must be visible in the demo:

| Brief stage | Decision Lens delivers |
| --- | --- |
| Ingest | Synthetic events + 10 Hz tracking streamed live |
| Interpret | Live stats, workload, fatigue, intensity, pass difficulty |
| Explain | Option probabilities, what-if swaps, decision quality |
| Render | Time-coded overlay cards on the tactics board |
| Personalize | Analyst vs fan mode, favourite player and club, language switch |

Judging is five equally weighted criteria (20% each). What the build must show for each:

| Criterion | What judges must see |
| --- | --- |
| Technological implementation | Original synthetic data generator, clean tested code, Foundry, Agent Framework, MCP, Azure services |
| Agentic design and innovation | Five specialised agents, rules router, shared state, retries, MCP tools |
| Real-world impact | Broadcast-ready overlay JSON, works live, clear audiences |
| User experience and presentation | Sleek board, smooth motion, readable cards, a demo video under 2 minutes |
| Category adherence | Target: Best Multi-Agent System, while meeting the Grand Prize description |

## Features and acceptance criteria

Priority: **M** must ship, **S** should ship, **C** cut first if time runs out.

| # | Feature | Pri | Accepted when |
| --- | --- | --- | --- |
| F1 | Synthetic match generator (seeded, behaviour rules, scripted key moments) | M | Same seed gives identical output; a 90-minute match replays and looks like football |
| F2 | Live stream of events + 10 Hz tracking | M | Board receives frames at match speed and at 2×, 4×, 8× |
| F3 | Tactics board: pitch, 22 players, ball, smooth motion | M | 60 fps interpolation between frames; resizes cleanly |
| F4 | Player name tags with speed and distance badges at thresholds | M | Badge appears when a player passes the sprint threshold |
| F5 | Live stats: possession, passes, pass accuracy, shots, ball and shot speed | M | Numbers match a recount from the raw events |
| F6 | Pass quality: distance, accuracy, difficulty rating | M | Every pass has a difficulty 0–100 from the engine |
| F7 | Workload: distance, high-speed running, sprints, heat map | M | Totals match tracking within 1% |
| F8 | Fatigue score and physical status | M | Fatigue changes engine probabilities via modifiers |
| F9 | Match intensity index per 5 minutes | M | Chart shows clear rises around key moments |
| F10 | Key-moment detector | M | Flags all scripted moments, few false positives |
| F11 | Option map with success probability and threat gain | M | Up to 4 options per moment, each with a range |
| F12 | What-if swap: archetype, custom profile, fresh substitute | M | Shows before → after probability with range and the drivers |
| F13 | Explanations by agents, grounded in engine output | M | Every number in the text appears in the engine payload |
| F14 | Analyst mode vs fan mode | M | Same moment produces clearly different cards |
| F15 | Favourite player and club focus | M | Focused player highlighted, their moments prioritised |
| F16 | Language switch via Azure AI Translator | M | Any card switches language without a new model call |
| F17 | Automated recap of turning points | M | Recap generated at half-time and full-time |
| F18 | Timeline scrubber with key-moment markers | M | Clicking a marker jumps to and replays that moment |
| F19 | Scroll-driven recap page | S | Recap reads as a scroll story with the pitch pinned |
| F20 | Calibration chart | S | Predicted vs observed success rates plotted |
| F21 | Overlay JSON export for broadcast | S | Time-coded JSON downloadable per moment |
| F22 | Custom profile builder with sliders | C | Sliders change profile and recompute instantly |
| F23 | Application Insights traces of agent runs | S | One trace per key moment visible in Azure |

## Constraints and non-negotiables

- **Synthetic data only.** No real matches, real players, real club names, badges or footage. Teams: *Riverside FC* and *Hillton United*, with invented player names.
- **$0 out of pocket.** Azure free account only: free tiers first, everything else on the $200 credit. Never upgrade to pay-as-you-go. No Azure Marketplace or partner models.
- **Models:** Azure OpenAI `gpt-5.4-mini` (explanations, recap) and `gpt-5.4-nano` (fan one-liners) in Foundry, lowest reasoning effort. Fallback `gpt-4.1-mini`.
- **The language model never produces numbers.** It receives engine output and writes words around it.
- **Language model calls only at key moments,** half-time and full-time; never per frame.
- **Public repo.** No secrets, ever. Managed identity in Azure, `.env` locally.
- **No 3D.** A sleek 2D board with smooth motion and scroll-driven sections instead.
- **Licences:** only open-source libraries with permissive licences and fonts free for commercial use. List third-party licences in the README.
- **Demo stays live until 10 Nov** (end of judging).

## Tech stack

| Layer | Choice |
| --- | --- |
| Backend language | Python 3.12, managed with `uv` |
| Data models | Pydantic v2 (single source of truth; export JSON Schema for the frontend) |
| Engine + stream service | FastAPI, uvicorn, NumPy |
| Agents | Microsoft Agent Framework (Python), Azure OpenAI in Foundry |
| Agent tools | MCP server (official MCP Python SDK) wrapping engine functions |
| Translation | Azure AI Translator (Free F0) |
| Tests and quality | pytest, ruff, mypy (engine and contracts) |
| Frontend | React 18 + TypeScript + Vite, pnpm |
| Styling | Tailwind CSS with design tokens from the design system below |
| UI primitives | shadcn/ui (Radix): Tabs, Toggle Group, Select, Slider, Sheet, Tooltip, Dialog |
| Pitch and overlays | Custom SVG pitch component + d3-scale, d3-shape, d3-interpolate |
| Motion | Framer Motion (cards, layout, presence) + `requestAnimationFrame` interpolation for players |
| Scroll | Lenis smooth scroll; Framer Motion `useScroll` for scroll-linked sections |
| Charts | Recharts (intensity, fatigue, calibration) |
| State | Zustand (match state, viewer preferences) |
| Icons | Lucide |
| Azure (Phase 8) | Event Hubs, Container Apps, Container Registry, Cosmos DB (free tier), SignalR (free), Static Web Apps (free), Key Vault, Application Insights, deployed with azd + Bicep |

## Design system

Light, calm and editorial, taking its palette from treg.to: an off-white `#f8f8f8` page, near-black ink, white cards, hairline borders, very soft shadows and large rounded corners. Use the colours and feel only; no treg branding, logo or copy. No 3D, no logos-as-decoration: the pitch and the numbers are the visuals.

**Tokens** (put in `web/src/styles/tokens.css`, map into Tailwind):

```css
:root {
  --bg: #f8f8f8;          /* page background (treg.to) */
  --surface: #ffffff;     /* cards, panels */
  --panel-2: #f0f0f0;     /* pitch surface, inset areas */
  --ink: #1a1a1a;         /* text, home team, primary buttons */
  --muted: #7c7c7c;       /* secondary text */
  --muted-2: #989898;     /* tertiary text, axis labels */
  --line: rgba(0,0,0,.10);   /* hairlines, pitch markings */
  --line-2: rgba(37,37,34,.20);
  --green: #118453;       /* probability up, success, ghost path */
  --red: #c0362f;         /* probability down, turnovers */
  --amber: #ba6603;       /* ball, fatigue warnings, key moments */
  --radius-xl: 32px;      /* large panels */
  --radius-lg: 20px;      /* cards */
  --radius-md: 12px;      /* buttons, chips */
  --shadow-sm: 0 2px 2px #00000008;
  --shadow-md: 0 2px 5px #00000007;
  --shadow-lg: 0 4px 18px #00000009;
  --ease: cubic-bezier(.22,1,.36,1);
  --font-sans: "Inter", "Segoe UI", system-ui, sans-serif;
  --font-display: "Geist", "Inter", system-ui, sans-serif;
  --font-mono: "DM Mono", ui-monospace, "SF Mono", Menlo, monospace;
}
```

**Typography:** Inter for body, Geist for headings, DM Mono for every number, clock and probability (tabular figures). All three are free to use; treg's own body font is commercial, so don't use it.

**Tactics board**

- Pitch: flat `--panel-2` surface, `--line` markings, rounded `--radius-xl` frame, no grass texture.
- Home players: filled `--ink` discs with white shirt numbers. Away players: white discs with an `--ink` ring. Shape differs as well as colour, so it reads without colour.
- Ball: small `--amber` dot with a short fading trail.
- Focused player: soft halo and name tag that follows them.
- Option arrows: curved d3 paths, thickness = probability, green for the best option, muted for the rest, with mono probability labels.
- What-if ghost: dashed green outline disc and dashed run path; the card shows `23% → 61%` with the range underneath.
- Motion: players interpolate between 10 Hz frames at 60 fps; cards enter with a short fade-and-rise on `--ease`; respect `prefers-reduced-motion`.

**Layout and scroll**

- **Live page:** top bar (score, clock, speed, mode, language); pitch centred and sticky; right rail is a scrollable feed of moment cards that auto-follows; timeline scrubber along the bottom with amber key-moment markers.
- **Recap page:** a scroll story. The pitch stays pinned on the left; each section scrolls in a turning point, and scroll progress replays that moment on the pitch. Smooth scrolling with Lenis, section snap on desktop.
- **How it works page:** scroll sections that walk through the five stages and the agent architecture.
- **Settings sheet:** persona, favourite club and player, language, what-if profile.
- Mobile: the pitch goes full width, the card feed sits below, and the scrubber stays sticky at the bottom.

## Repository structure

```text
decision-lens/
  README.md              pitch, screenshots, quick start, Azure deploy, licences
  FEATURES.md            every feature, status, how to see it in the app
  ARCHITECTURE.md        architecture + process flow (Mermaid), local vs Azure
  CODE_EXPLAINER.md      walkthrough of every module and how data moves
  AGENTS.md              working rules for coding agents
  .env.example           every variable, no values
  Makefile               dev, test, lint, generate, replay, deploy
  azure.yaml             azd project file
  contracts/             Pydantic models + exported JSON Schema
  generator/             match simulator, roster, archetypes, scripted moments
  engine/                metrics, workload, fatigue, probabilities, Monte Carlo
  service/               FastAPI app: stream, state, publisher, REST + WebSocket
    adapters/            file_replay, memory_store, ws_publisher, event_hubs, cosmos, signalr
  mcp_server/            engine functions exposed as MCP tools
  agents/                router, orchestrator, interpreter, moment, what_if, narrator, recap
  web/                   React app: board, cards, scrubber, recap, settings
  infra/                 Bicep modules for every Azure resource
  data/samples/          one generated match (JSONL) committed for judges
  tests/                 unit + integration tests
  docs/                  BUILD_PLAN.md, demo-script.md, screenshots/
```

## Data contracts

All records share one clock (`t_ms` from kick-off) and one coordinate system: 105 × 68 m pitch, origin at the home team's defending bottom-left corner, `z` for ball height. Define each as a Pydantic model in `contracts/` and export JSON Schema for the frontend types.

| Record | Frequency | Key fields |
| --- | --- | --- |
| `MatchMeta` | once | `match_id`, teams (id, name, formation, colours), pitch size, `tracking_hz`, `seed` |
| `PlayerProfile` | once per player | `player_id`, `team_id`, name, position, archetype, physical (height, max speed, accel, reaction, jump reach), skill (pass, aerial, tackle, finishing) |
| `TrackingFrame` | 10 per second | `frame`, `t_ms`, ball (`x`,`y`,`z`, `owner_id`), players (`id`, `x`, `y`, `vx`, `vy`) |
| `Event` | per action | `event_id`, `t_ms`, `period`, `type`, team, player, start/end, target, outcome, ball speed and height, pressure, tags, `frame_ref` |
| `WorkloadState` | every second | distance, high-speed running, sprints, recent load, `fatigue` 0–100, `status`, modifiers (speed, accel, reaction) |
| `KeyMoment` | per moment | `moment_id`, `t_ms`, type, players involved, `frame_range` |
| `OptionSet` | per moment | up to 4 options: action, target, `p_success`, `range`, `xt_gain`, `path` |
| `WhatIf` | per moment | actual vs counterfactual (`profile`, `p_success`, `range`), `drivers`, ghost path |
| `Overlay` | per card | `overlay_id`, `t_ms`, `show_for_ms`, `kind`, payload, `text` by persona and language |

Event types: `pass`, `cross`, `shot`, `dribble`, `tackle`, `interception`, `aerial_duel`, `clearance`, `foul`, `possession_change`, `pressure`, `substitution`, `goal`, `knock`, `period_start`, `period_end`.

The full JSON examples are in the earlier project plan; the Pydantic models are the source of truth once written.

## Phases 0–3: foundation, data and engine

### Phase 0 — Bootstrap (Sat morning)

**Goal:** an empty but runnable monorepo with tooling and rules in place.

- Create the folder structure above, `AGENTS.md`, `.gitignore` (include `.env`), `.env.example`, MIT `LICENSE`.
- Python: `uv` project, ruff, mypy, pytest; FastAPI "hello" endpoint in `service/`.
- Web: Vite + React + TS + Tailwind + shadcn/ui; load Inter, Geist, DM Mono; add `tokens.css`; one blank page using the tokens.
- `Makefile` targets: `dev`, `test`, `lint`, `generate`, `replay`.
- Stub `README.md`, `FEATURES.md`, `ARCHITECTURE.md`, `CODE_EXPLAINER.md` with headings.
- A `scripts/smoke_azure.py` that calls the Foundry model and Translator once using `.env`.

**Checkpoint:** `make dev` starts API and web; `make test` and `make lint` pass; the smoke script prints a model reply and a translation.

### Phase 1 — Data contracts

**Goal:** one shared definition of every record.

- Pydantic models for all records in the contracts table, with validation (pitch bounds, probability 0–1).
- Export JSON Schema to `contracts/schema/`; generate TypeScript types into `web/src/types/` (e.g. `json-schema-to-typescript`).
- Round-trip tests: model → JSON → model.

**Checkpoint:** schemas exported, TS types compile, tests pass.

### Phase 2 — Synthetic match generator (Sat)

**Goal:** a believable 90-minute match from a seed.

- Roster: two teams, 11 starters + 5 subs each, invented names, archetype profiles (aerial CB, ball-playing CB, overlapping full-back, deep playmaker, box-to-box, pressing forward, target man, winger).
- Behaviour rules: block shifts toward the ball; nearest one or two defenders press; attackers make forward runs in possession; passes prefer open, forward teammates; tackles, interceptions, aerial duels, shots, fouls, substitutions; speed drops as fatigue rises.
- Ball physics: pass speed and arc, simple drag, height for crosses.
- Choose actions using the engine's probabilities (Phase 3), so ground truth is consistent; stub with simple rules first.
- Scripted key moments at fixed minutes: late aerial duel at the back post, tired full-back beaten on a recovery run, big chance missed, line-breaking pass, turnover under a high press.
- CLI: `make generate SEED=42` writes `data/samples/match_42/{meta,players,events,tracking}.jsonl`.
- A throwaway dot-plot viewer (matplotlib animation or a quick HTML page) to eyeball movement.

**Checkpoint:** same seed gives identical files; the dot plot looks like football; all scripted moments are present.

### Phase 3 — Probability and metrics engine (Sat)

**Goal:** every number in the app comes from here, tested.

- Metrics: possession, passes, pass accuracy, pass distance, ball and shot speed, distance, high-speed running, sprints, heat maps, intensity index per 5 minutes.
- Fatigue model: rises with high-speed running and recent load, recovers slowly; outputs modifiers for max speed, accel and reaction; `status` from `knock` events.
- Time-to-intercept and pitch control (logistic arrival-time model).
- Probabilities: pass success (product over defenders near the lane), aerial win (arrival × reach vs ball height), shot xG (distance, angle, pressure), duel/recovery-run success.
- Pass difficulty 0–100 from pass success and pressure.
- Option generation: up to 4 candidate actions per moment with `p_success`, `xt_gain` (simple xT grid), path.
- What-if: swap a profile (archetype, custom or fresh sub) and recompute with drivers ("+12 cm reach", "0.15 s faster reaction").
- Monte Carlo ranges: jitter reaction and speed \~300 runs; return median and 10th–90th percentile.
- Calibration: compare predicted vs generated outcomes on the sample match.

**Checkpoint:** unit tests for each function, including edge cases; a known scripted aerial duel gives a sensible before/after; calibration error reported.

## Phases 4–6: stream, board and agents

### Phase 4 — Stream service (Sat evening)

**Goal:** a live feed the board can subscribe to, swappable for Azure later.

- Interfaces in `service/ports.py`: `StreamSource`, `StateStore`, `Publisher`.
- Local adapters: `FileReplay` (reads JSONL at 1×/2×/4×/8×, pause, seek), `MemoryStore`, `WebSocketPublisher`.
- `RUN_MODE=local|azure` chooses adapters in one factory; Azure adapters are stubs until Phase 8.
- Pipeline per frame: engine metrics → state → publish frame + stats; key-moment detector → enqueue for agents.
- REST: `GET /match`, `GET /players`, `GET /moments`, `POST /replay/{play|pause|seek|speed}`, `GET /overlays/{id}`. WebSocket: `/ws` streams frames, stats and overlays.
- Evening: deploy the hello-world service container with `azd up` to flush out Azure setup issues early.

**Checkpoint:** a test client receives frames at the right rate; seek and speed work; the container answers in Azure.

### Phase 5 — Tactics board UI (Sun)

**Goal:** the sleek board from the design system, running live locally.

- `Pitch` (SVG, responsive, markings from pitch size), `PlayerDot`, `Ball` with trail, `NameTag`, `SpeedBadge`.
- 60 fps interpolation between 10 Hz frames; smooth seeking.
- Top bar: score, clock, speed control, persona toggle, language select.
- Right rail: scrollable moment-card feed (Framer Motion enter animations), auto-follow with "jump to live".
- Bottom: timeline scrubber with amber key-moment markers; click to replay a moment.
- Stats drawer: possession, passes, pass accuracy, workload table, intensity chart, fatigue bars.
- Option arrows and what-if ghost rendering from `OptionSet` and `WhatIf` (static data first, live once agents run).
- Settings sheet: persona, favourite club and player, language, what-if profile.
- Responsive layout and `prefers-reduced-motion`.

**Checkpoint:** the full match plays smoothly locally; markers replay moments; layout holds on mobile and desktop.

### Phase 6 — MCP tools and agents (Sun)

**Goal:** grounded explanations at key moments from a multi-agent system.

- MCP server exposing: `get_match_state`, `get_player_workload`, `get_options`, `what_if_swap`, `get_intensity`, `get_recap_facts`.
- Rules router (`agents/router.py`), a plain decision table, decides what runs:

| Trigger | Runs |
| --- | --- |
| Every frame or event | Engine only, no model |
| Key moment | Moment → What-if → Narrator |
| Fatigue over threshold | What-if (fresh sub) → Narrator |
| Language change | Translator only |
| Half-time, full-time | Recap |

- Agents (Microsoft Agent Framework, Foundry model): **Interpreter** (summarises live state), **Moment** (classifies and frames the moment), **What-if** (calls MCP tools, chooses the swap, never computes numbers), **Narrator** (analyst + fan text from engine payload), **Recap** (turning points).
- Orchestrator: shared state in the `StateStore`, handoffs, timeouts and one retry; on failure, publish a template card built from engine numbers.
- Grounding check: reject any agent text containing a number not present in the engine payload, then retry or fall back.
- Model routing: `gpt-5.4-nano` for fan one-liners, `gpt-5.4-mini` for analyst text and recap; lowest reasoning effort; cache by `moment_id` + persona.
- Translator adapter: translate cards on demand; cache by `overlay_id` + language.

**Checkpoint:** every scripted moment produces analyst and fan cards with correct numbers; the grounding check passes; killing the model call still shows a fallback card.

## Phases 7–9: personalization, Azure and polish

### Phase 7 — Personalization and recap (Mon)

**Goal:** the same intelligence as two genuinely different experiences.

- Analyst mode: option map, probability ranges, drivers, workload and intensity charts, overlay JSON export.
- Fan mode: one-line cards, plain words ("much more likely to win that header"), fewer numbers, larger type.
- Favourite club filter and favourite player focus (halo, name tag, their moments first in the feed).
- Language switch across every card and the recap.
- Recap page as a scroll story: pinned pitch, one section per turning point, scroll progress replays the moment.
- How it works page: scroll sections for the five stages and the agent architecture.

**Checkpoint:** switching persona visibly changes the same moment's card; recap generated at half-time and full-time; scroll pages smooth on desktop and mobile.

### Phase 8 — Azure adapters and deployment (Mon)

**Goal:** the same app live on Azure, all on free tiers or the $200 credit.

- Adapters: `EventHubsSource` (a replay job sends the JSONL into Event Hubs), `CosmosStore`, `SignalRPublisher`; same interfaces, chosen by `RUN_MODE=azure`.
- Bicep in `infra/` for: Container Registry, Container Apps (service + MCP, consumption, min replicas 0), Event Hubs Basic, Cosmos DB with free tier on, SignalR Free, Static Web Apps Free, Key Vault, Application Insights, managed identities and role assignments.
- Foundry and the model deployment are referenced by endpoint (created manually in Phase 0).
- `azd up` deploys everything; `azd down` documented for after judging.
- OpenTelemetry traces of each agent run to Application Insights.

**Checkpoint:** the public Static Web Apps link plays the match with live cards; no keys in code or config; Cost Management shows only credit-covered spend.

### Phase 9 — Docs, tests and demo polish (Tue)

**Goal:** a submission judges can understand in two minutes and run themselves.

- Complete the four docs files (spec below), with screenshots.
- Integration test: replay → engine → moment → agents (model mocked) → overlay.
- Calibration chart in the analyst drawer.
- Performance pass: smooth at 8× speed; no layout shift.
- `docs/demo-script.md`: a 110-second video script.
- Feature freeze Tuesday 6pm; Wednesday is recording and submission only.

**Checkpoint:** a fresh clone runs locally from the README in under 10 minutes; all tests green; demo script rehearsed.

## Documentation files

The coding agent creates these in Phase 0 as stubs, updates them every phase, and completes them in Phase 9.

| File | Must contain |
| --- | --- |
| `README.md` | Tagline and elevator pitch; hero screenshot or GIF; the problem; what it does; Microsoft and Azure tech used; quick start (local, under 10 minutes); Azure deploy with `azd up`; environment variables; demo video link; how judges can test; synthetic-data statement; cost and free-tier note; third-party licences; GitHub topics |
| `FEATURES.md` | Every feature F1–F23 with description, status (done / partial / cut), how to see it in the app, which brief stage and judging criterion it serves, screenshot where useful |
| `ARCHITECTURE.md` | Architecture diagrams for local and Azure, the eight-step process flow, agent layout and router table, data contracts, sequence for one key moment (Mermaid diagrams), design decisions and trade-offs, security (managed identity, no secrets), cost model |
| `CODE_EXPLAINER.md` | Walkthrough of each folder and key file in plain language; how one frame travels through the system; how one key moment becomes a card; how the probability maths works with formulas; how to add a new archetype, event type or agent; testing approach |

Write all four for a judge who has five minutes: short sections, diagrams before prose, no unexplained jargon.

## Definition of done and submission checklist

**Done means**

- [ ] All M features accepted; S features shipped or listed as partial in `FEATURES.md`
- [ ] Tests and lint green; no secrets in the repo history
- [ ] Runs locally from a fresh clone using the README
- [ ] Live on Azure via `azd up`, all on free tiers or the credit
- [ ] Every agent number traceable to the engine (grounding check on)
- [ ] Four docs files complete with diagrams and screenshots

**Submission (Wed, aim for 2pm Sydney)**

- [ ] Demo video under 2 minutes, public on YouTube or Vimeo, no copyrighted music
- [ ] Public GitHub repo URL
- [ ] Live demo link
- [ ] Project pitch: what it does, Microsoft and Azure tech used, problem solved
- [ ] English text throughout
- [ ] Keep every Azure resource running until 10 Nov, then `azd down`
