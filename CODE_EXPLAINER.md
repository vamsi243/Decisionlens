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
| `rules.py` | Stub probabilities (pass success, xG, aerial win, tackle/dribble). Phase 3 swaps in the engine |
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
_TODO_

## How one key moment becomes a card
_TODO_

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
_TODO_

## Testing approach
_TODO_
