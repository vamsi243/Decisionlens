# Code explainer

## Folder tour
| Folder | What lives there |
| --- | --- |
| `contracts/` | Pydantic models — the one definition of every record |
| `generator/` | Seeded match simulator |
| `engine/` | Every number: metrics, fatigue, probabilities |
| `service/` | FastAPI app, stream pipeline, adapters |
| `mcp_server/` | Engine functions exposed as MCP tools |
| `agents/` | Router, orchestrator and the five agents |
| `web/` | React tactics board |
| `tasks.py` | Cross-platform task runner used by the Makefile |
| `service/` | `ports.py` (interfaces), `adapters/` (file replay, memory store, WebSocket, Azure stubs), `pipeline.py`, `main.py` (REST + WS) |
| `infra/` | Bicep for the Phase 4 hello deploy (registry, Container Apps, managed identity) |
| `mcp_server/` | `context.py` (what the tools can see: the pipeline + store), `server.py` (six tools on the MCP SDK's `MCPServer`), `__main__.py` (standalone stdio server) |
| `agents/` | `router.py` (decision table), `backend.py` (Agent Framework on Azure OpenAI), `orchestrator.py`, `facts.py`, `grounding.py`, `templates.py`, `prompts.py`, `cache.py`, `translator.py` |
| `web/src/state/` | `frames.ts` (frame buffer + interpolation), `match.ts` (Zustand store fed by the socket), `prefs.ts` (persona, favourites, language; saved locally) |
| `web/src/pages/` | `RecapPage.tsx` (scroll story with pinned pitch), `HowPage.tsx` (five stages + agent diagram) |
| `web/src/lib/` | `router.ts` (hash routes), `useLenis.ts` (smooth scroll + snap), `export.ts` (overlay JSON), `words.ts` (fan wording) |
| `web/src/components/` | `board/` (pitch, players, ball, option arrows, what-if ghost), `TopBar`, `Scrubber`, `MomentFeed`/`MomentCard`, `StatsDrawer`, `SettingsSheet`, `ui/` (shadcn-style Radix primitives) |

## Contracts in practice
- `contracts/base.py` — `Point`, `Probability`, `ProbRange` (median + 10th-90th percentile, must be ordered), pitch constants.
- Every model forbids unknown fields, so a typo in a producer fails loudly instead of silently dropping data.
- `contracts/export.py` writes one schema per record plus a `contracts.json` bundle; `web/scripts/gen-types.mjs` turns the bundle into TS.
- `tests/factories.py` holds one valid example of every record; `tests/test_contracts.py` round-trips each and checks the validation rules.

## The generator (`generator/`)
| File | What it does |
| --- | --- |
| `roster.py` | Two invented 16-player squads, formations as team-relative slots, archetype base profiles with seeded jitter |
| `sim.py` | `MatchSim`: one `step()` per 0.1 s — director → carrier decision → targets → movement → ball → duels → pressure → fatigue → substitutions |
| `script.py` | The five scripted key moments, substitutions and the knock |
| `writer.py` | Streams tracking lines while simulating, then writes meta, players and events |

**One tick of the simulator**
1. *Targets.* Each player's formation slot slides with the ball (half the ball's distance from halfway), pushes up 6 m in possession and drops 5 m out of it; defenders stay goal-side. Targets are low-pass filtered (~1.5 s) so the block flows instead of twitching.
2. *Roles on top.* Runners make forward runs in possession; the nearest defender presses the carrier and the second covers; receivers and interceptors chase the ball's landing point.
3. *Movement.* Desired velocity toward the target, capped (jog ≤ 4.5 m/s unless urgent), acceleration-limited, all scaled by fatigue (`1 - 0.0022 × fatigue`).
4. *Ball.* Glued to the carrier, or on a flight `s(t) ∝ 1 - e^{-kt}` (drag) with a parabolic height `4h·u(1-u)` for lofted balls and crosses, or rolling loose with friction.
5. *Decisions.* Every 1–3 s (sooner under heavy pressure) the carrier shoots, crosses, clears or picks a pass by softmax over `p_success × progress`.

**Team-relative coordinates.** `rel(team, xy)` mirrors the away team on both axes, so every rule is written once as "attacking toward x = 105".

**Adding an archetype:** add it to `contracts.Archetype`, give it a row in `ARCHETYPE_BASE` (and optionally `RUN_RATE` / `DRIBBLERS` in `sim.py`), then regenerate the schema with `make schema`.

## How one frame travels
_On the board:_ `stream.ts` hands each frame to `frames.push()`. The `Board` component's `requestAnimationFrame` loop calls `frames.sample(now)`, which interpolates between the last two frames over 100 ms ÷ speed, and moves each player's `<g>` by setting its `transform`.

_In the service:_
1. `FileReplay.next_packet()` waits until the frame is due: `clock start + n × 0.1 s / speed`. If it falls more than 1 s behind, it drops the backlog.
2. `Pipeline.handle()` passes the packet to `_process()`. That updates `WorkloadTracker` (distance, high-speed running, sprints, heat, fatigue), `StatsTracker`, `IntensityTracker` and `MomentDetector`, all held in `LiveState`.
3. The raw frame bytes are wrapped as `{"type":"frame","data":…}` and fanned out to every WebSocket client's queue.
4. Every 10th frame a `MatchStats` snapshot is stored and published.

## How one key moment becomes a card
1. `MomentDetector.on_event()` sees, say, an `aerial_duel` the defender lost inside his own box.
2. It builds a `KeyMoment` (id `km_<frame>_<type>`) and a `MomentSpec`: "does RIV_02 win this header, asked at the moment of the cross?". It also takes a `Snapshot` of the cross frame from its 20 s ring buffer.
3. The pipeline stores and publishes the moment, then queues a `Job`, along with the players still on the bench.
4. `analysis_worker` runs `engine.whatif.what_if` (fresh aerial centre-back from the bench) and, for on-ball moments, `engine.options.option_set` in a thread. The result is stored and published as `analysis`.
5. `Orchestrator.submit_moment` queues it. The router picks the steps: for a key moment, Moment → What-if → Narrator.
6. `agents/facts.py` turns the analysis into FACTS (percentages as whole numbers, names, drivers, workload at the time of the moment).
7. Each agent call goes through `_ask`: response cache → model (25 s timeout) → `grounding.check` → one retry → `templates.py`.
8. The result is an `Overlay`: `text[persona][language]`, the engine payload, a `source` (agents / mixed / template) and a step trace. It is stored and pushed to boards as an `overlay` message. A language switch calls `GET /overlays/{id}?lang=` (Azure AI Translator).


## The probability maths (`engine/`)

**Getting somewhere** (`physics.arrival_time`). A player drifts on his current velocity for his reaction time, then accelerates from rest at `a` up to top speed `v`:

```
d_acc = v² / 2a
t(d)  = reaction + √(2d / a)                  if d ≤ d_acc
      = reaction + v/a + (d − d_acc) / v      otherwise   (d = distance minus a 1 m control radius)
```
Fatigue scales the inputs. At fatigue 100, top speed drops to ×0.78, acceleration to ×0.70 and reaction time rises to ×1.40.

**Ball flight.** A ground pass slows with drag: `s(t) = D (1 − e^{−kt}) / (1 − e^{−kT})`, with k = 0.35 and an average speed of 11.5 m/s. Passes longer than 32 m are lofted: k = 0.25, 15 m/s, and they can only be intercepted in the last 25% of their flight.

**Who wins a race.** `P(player first) = σ((t_ball − t_player − margin) / 0.45 s)`, the same logistic used everywhere.

| Probability | Formula |
| --- | --- |
| Pass success | `Π_defenders (1 − 0.85·max_lane σ(…)) × P(receiver arrives) × σ(3.6 + (passing − 70)/15 − 1.8·pressure − 0.03·d)` |
| Pass difficulty | `100 × (0.8·(1 − p) + 0.2·pressure)` |
| Aerial duel | Bradley–Terry: `w = arrival × σ((reach − ball height)/12 cm) × e^{(reach − 250)/40 + (aerial − 70)/50}`, defender ×1.3 |
| xG | `σ(0.2 − 0.16·dist + 0.9·angle − 1.2·pressure − 1.2·header + (finishing − 70)/40)` |
| Recovery run | `1 − Π_path (1 − 0.35·σ((t_carrier − t_chaser)/0.5))`, with the carrier at 75% of top speed toward the box edge |
| xT | analytic grid: `0.004 + 0.03·(x/105)² + 0.55·xG(x, y)` |

**Ranges.** 300 Monte Carlo runs jitter every player's reaction time (sd 0.04 s) and speed and acceleration (sd 5%); the range is the 10th–90th percentile. Before and after a swap share the same seed.

**What-if drivers.** The engine compares the attributes that matter for the moment, all fatigue-adjusted: reach, aerial rating, reaction and fatigue for a header; top speed, acceleration, reaction and fatigue for a recovery run. They come out as plain text ("+32 cm reach", "fresher legs (fatigue 70 → 0)"). The drivers' numbers come from the engine too.

**Adding a moment type:** add it to `MomentType`, write a branch in `moments.evaluate` and `spec_for_event`, list its driver factors in `whatif.FACTORS` and its preferred archetype in `PREFERRED_ARCHETYPE`.

## Extending
- **A new agent:** add its instructions to `agents/prompts.py` (bump `PROMPT_VERSION`), add a `Step` and the triggers that run it to `agents/router.py`, and call `_ask` for it in `agents/orchestrator.py`. Give it a template in `agents/templates.py`, so it still works without a model.
- **A new MCP tool:** add a method to `mcp_server/context.py` (the engine does the maths) and register it in `mcp_server/server.py`. To let the What-if agent use it, list it in `agents/backend.MCP_TOOLS`.

## Testing approach
_TODO_
