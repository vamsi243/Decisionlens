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

## The probability maths
_TODO (Phase 3)_

## Extending
_TODO_

## Testing approach
_TODO_
