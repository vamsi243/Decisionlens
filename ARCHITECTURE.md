# Architecture

## Overview
```mermaid
flowchart LR
  G[generator] -->|JSONL| S[service: stream]
  S --> E[engine]
  E --> S
  S -->|key moment| A[agents]
  A -->|MCP tools| M[mcp_server] --> E
  S -->|WebSocket| W[web board]
```

## Local vs Azure
The service talks to infrastructure only through three ports (`service/ports.py`). `RUN_MODE` picks the adapters in one factory (`service/factory.py`):

| Port | `RUN_MODE=local` | `RUN_MODE=azure` (Phase 8) |
| --- | --- | --- |
| `StreamSource` (frames, events, pacing) | `FileReplay`: JSONL at 1/2/4/8×, pause, seek | `EventHubsSource` |
| `StateStore` (moments, analyses, overlays, stats) | `MemoryStore` | `CosmosStore` |
| `Publisher` (fan-out to boards) | `WebSocketPublisher` | `SignalRPublisher` |

```mermaid
flowchart LR
  SRC[StreamSource] -->|FramePacket| PIPE[Pipeline]
  PIPE -->|WorkloadTracker / StatsTracker / IntensityTracker| ST[(StateStore)]
  PIPE -->|MomentDetector| Q[[analysis queue]]
  Q --> W[analysis worker<br/>options + what-if in a thread] --> ST
  PIPE --> PUB[Publisher] --> B[boards]
  W --> PUB
```

**Seeking.** At start-up the pipeline replays the whole match silently (about 3 s). It saves a copy of its state every match minute and collects every key moment, then warms the analysis cache. A seek restores the nearest checkpoint and fast-forwards at most 599 frames. A test checks the result is identical to a straight replay.

**Backpressure.** Each WebSocket client has its own bounded queue. A slow browser drops its oldest messages instead of stalling the pipeline.

## Process flow
1. **Ingest.** The source emits a `FramePacket` (tracking frame + events) on the replay clock.
2. **Interpret.** Workload, fatigue, team stats and intensity update incrementally.
3. **Publish.** The frame is forwarded byte-for-byte; stats go out every second, workload every 5 s, intensity every minute.
4. **Detect.** `MomentDetector` checks the frame and its events against the key-moment rules.
5. **Analyse.** A detected moment is queued; a worker computes the option map and the what-if off the event loop.
6. **Store.** Moments and analyses go to the `StateStore`, keyed by deterministic ids.
7. **Explain** (Phase 6). The agents turn the analysis into grounded cards.
8. **Render** (Phase 5). The board draws frames, cards, arrows and ghosts.

## The board (web/)
```mermaid
flowchart LR
  WS[/ws/] --> ST[stream.ts dispatch]
  ST -->|frame| FB[frames.ts<br/>mutable buffer]
  ST -->|everything else| Z[(Zustand match store)]
  FB --> RAF[rAF loop<br/>writes SVG attributes]
  Z --> R[React: top bar, feed, scrubber, drawer]
  P[(prefs store<br/>localStorage)] --> R
  R -->|REST| API[/replay/*, /moments/]
```
- **Frames bypass React.** At 8× there are 80 frames a second. They go into a two-frame buffer. A `requestAnimationFrame` loop interpolates between the last two and writes `transform` attributes directly, so React re-renders at most 10 times a second (the clock). A seek or a gap snaps instead of gliding. With `prefers-reduced-motion` it shows frames as they arrive.
- **Cost at 8×:** about 16 µs to handle a message and 8 µs per interpolated sample, which is under 2 ms of main-thread time per second.
- **Moments in a replay.** `/moments?all=true` gives the scrubber every marker up front. Missing analyses are fetched on demand, so seeking forward still fills the feed. After a seek the server republishes stats, workload and intensity immediately.
- **Pages.** Hash routes (`#/`, `#/recap`, `#/how`), so any static host serves them with no rewrite rules. The recap and How it works pages are lazy-loaded chunks that use Lenis smooth scrolling (snap on desktop, off for reduced motion).
- **Recap story.** `GET /recap` builds the full-time recap from the pipeline's final state (kept from the warm-up), so it works whatever the live replay is doing. Turning points are ordered by what-if swing. Each chapter's scroll progress (Framer Motion `useScroll`) picks a frame from `GET /moments/{id}/frames` for the pinned `StaticBoard`.
- **Lazy charts.** The stats drawer (recharts) is a separate chunk loaded on first open: 457 KB initial JS (153 KB gzipped).

## Agents and router
| Trigger | Runs (agents/router.py) |
| --- | --- |
| Every frame or event | Engine only, no model |
| Key moment | Moment → What-if → Narrator |
| Fatigue over 80 | What-if (fresh sub, engine) → Narrator |
| Language change | Translator only |
| Half-time, full-time | Interpreter → Recap |

```mermaid
sequenceDiagram
  participant P as Pipeline
  participant W as Analysis worker
  participant O as Orchestrator
  participant M as Moment agent
  participant WI as What-if agent
  participant T as MCP tools (/mcp)
  participant N as Narrator (mini + nano)
  participant G as Grounding guard
  P->>W: key moment (snapshot + engine question)
  W->>W: option map + default what-if (engine)
  W->>O: MomentAnalysis
  O->>M: FACTS
  M-->>O: framing sentence
  O->>WI: FACTS + fresh subs
  WI->>T: what_if_swap(moment, mode, ...)
  T-->>WI: engine before/after, ranges, drivers
  WI-->>O: why this swap (no numbers)
  O->>N: FACTS (with the chosen swap's engine numbers)
  N-->>G: analyst card, fan line
  G-->>O: ok, or retry once, or engine template
  O->>P: Overlay (store + WebSocket)
```

- **Shared state, not message passing.** Agents never hand numbers to each other. The What-if agent's swap goes through the MCP tool into the `StateStore`, and the Narrator reads the engine's result.
- **Timeouts and retry.** Each call has 25 s. After an error, the one retry uses the fallback deployment; after an ungrounded answer, it uses the same model, told which numbers were wrong. Then the card falls back to the template.
- **Cache.** Answers are cached by match, moment (or recap), agent, model and prompt version, in memory and in `data/cache/` (gitignored). Replaying a match costs nothing after the first run. A cached what-if stores the tool arguments and replays them on the engine, so cached numbers are always engine numbers.
- **Cost guard.** Model calls happen only at key moments and the two whistles, about 17 moments and 2 recaps per match, at up to 4 calls each.
- **MCP security.** The MCP SDK's DNS-rebinding protection stays on; the agents reach the tools on 127.0.0.1.

## Synthetic match generator
```mermaid
flowchart LR
  R[roster.py<br/>teams, archetypes, profiles] --> S[sim.py<br/>10 Hz simulator]
  RU[rules.py<br/>outcome probabilities] --> S
  SC[script.py<br/>scripted moments, subs] -->|director| S
  S --> WR[writer.py] --> F[(meta / players / events / tracking JSONL)]
```
- **Deterministic:** one NumPy `Generator` seeded from the match seed; no wall-clock or hash-order dependence. Same seed → byte-identical files (tested).
- **Outcome first, then physics:** when a player passes, crosses or shoots, the outcome is sampled at the kick and the ball flight is built to match it. If the ball then runs loose, only the team that "won" it may collect, so the event log and tracking agree (a test holds disagreement under 1%; it is 0.2% on seed 42).
- **Scripted moments** are Python generators run by a director: they stop play with a restart near the scene, steer the players involved, and force the outcome. The key event carries `scripted:<moment>` tags as ground truth for the Phase 3 detector.

## Probability and metrics engine
```mermaid
flowchart TB
  PH[physics.py<br/>arrival times, ball flight, pitch control] --> PR[probability.py<br/>pass, aerial, xG, recovery, duel]
  FA[fatigue.py] --> SN[snapshot.py<br/>one frame + modifiers]
  PR --> MO[moments.py<br/>the question at a key moment]
  SN --> MO --> WI[whatif.py<br/>swap + drivers]
  SN --> OP[options.py<br/>option map + xT]
  MC[montecarlo.py<br/>P10-P90 ranges] --> WI & OP
  ME[metrics.py<br/>stats, workload, intensity] -.live trackers.-> SV[service, Phase 4]
  PR --> GEN[generator samples outcomes]
```
- **One source of numbers.** The generator calls the engine to sample every pass, shot, header and duel, and slows players with the engine's fatigue model. So the ground truth is drawn from the same probabilities the app explains. Calibration on seed 42: pass ECE 0.022, Brier 0.141.
- **Spells of pressure.** Around each scripted moment, the attacking side runs and shoots more for up to 2 minutes before and 90 s after, and duels are fiercer. Big moments happen in intense spells, and this makes the intensity index rise around them, as F9 needs.
- **Incremental by design.** `WorkloadTracker`, `StatsTracker` and `IntensityTracker` consume one frame or event at a time, so the live service (Phase 4) and batch analysis share code.

## Data contracts
**Event semantics.** `outcome` is always from `player_id`'s point of view. For a pass or cross, `target_id` is the intended receiver and `end` the intended point, even when it fails. In an aerial duel `player_id` is the defending-side player and `target_id` the attacker. For tackle, pressure and foul, `player_id` is the defender and `target_id` the ball carrier. For a dribble, `player_id` is the carrier. The full list is in the `Event` docstring (`contracts/tracking.py`).

Defined once as Pydantic v2 models in `contracts/`, exported to JSON Schema in `contracts/schema/`, and compiled to TypeScript in `web/src/types/contracts.ts` (`uv run python tasks.py schema`). A test fails if the committed schema drifts from the models.

One clock (`t_ms` from kick-off) and one coordinate system: 105 x 68 m, origin at the home team's defending bottom-left corner, `z` = ball height. Coordinates may sit up to 5 m outside the pitch (run-offs, nets); probabilities are validated to 0-1.

| Record | Frequency | Module |
| --- | --- | --- |
| `MatchMeta`, `PlayerProfile` | once | `contracts/match.py` |
| `TrackingFrame`, `Event`, `WorkloadState` | 10 Hz / per action / 1 Hz | `contracts/tracking.py` |
| `KeyMoment`, `OptionSet`, `WhatIf`, `Overlay` | per moment / card | `contracts/analysis.py` |

## Design decisions
| Decision | Why | Trade-off |
| --- | --- | --- |
| Rules-based simulator, not physics or learned agents | Deterministic, fast (90 min in ~25 s), and lets us script key moments exactly | Movement is football-shaped, not broadcast-accurate |
| Scripted moments via dead-ball restarts | A restart is a natural way to place the ball where the scene needs it | Each scripted moment starts with a short stoppage |
| Gzipped tracking in the repo | 13 MB instead of 73 MB keeps the repo clonable | Replay reads `.jsonl.gz` |
| Analytic arrival-time models, not learned ones | Transparent, explainable maths with no training data (synthetic only) | Less nuanced than models trained on real tracking |
| Common random numbers in what-ifs | Before and after use the same Monte Carlo draws, so the difference is the swap, not noise | Ranges are correlated, not independent |

**Known generator limitations (seed 42):** wide players and full-backs cover 12–14 km with 2–3 km of high-speed running, above typical real values (10–12 km and about 1 km). Centre-backs cover about 9.5 km. Every failed pass is collected by the opponent and logged as an interception, so interceptions (~190) run higher than in real data. The generator and the engine share one fatigue model: the engine replays it from tracking, and its result is within 0.5 points of the live tracker (tested). Seed 42 has fewer shots (~19) and fouls (~14) than a typical match.

## Security and cost
_TODO_
