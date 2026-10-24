# Decision Lens

**Every moment, every option, every fan.** Live match intelligence on a fully synthetic football match: a sleek 2D tactics board, a transparent probability engine, and Azure OpenAI agents that explain what happened, what was possible and who could have done it.

> Built for the Microsoft Premier League "Inside the Game" hackathon. All data is synthetic — *Riverside FC* vs *Hillton United*, invented players.

## The problem
_TODO (Phase 9)_

## What it does
_TODO — see [FEATURES.md](FEATURES.md)._

## The sample match
`data/samples/match_42/` holds one generated match for judges: `meta.jsonl`, `players.jsonl`, `events.jsonl` and `tracking.jsonl.gz` (10 Hz, 54,000 frames). Regenerate it in about 25 s with `make generate SEED=42`; the same seed always produces byte-identical files.

| Minute | Scripted key moment |
| --- | --- |
| 23' | Line-breaking pass — Quill (RIV_06) splits Hillton's midfield to Reyes-Ward |
| 38' | Turnover under a high press — Hillton's press forces Varga (RIV_05) into a loose pass |
| 57' | Big chance missed — Reyes-Ward drags a shot wide from 11 m |
| 71' | Tired full-back beaten on a recovery run — Kollmann (HIL_07) outruns Holt (RIV_03) |
| 86' | Late aerial duel at the back post — Morrow (HIL_09) out-jumps Pell (RIV_02) and scores |

## The engine
Every number in the app comes from `engine/`, never from a language model. It holds:
- live metrics, workload and fatigue;
- pass, aerial-duel, xG and recovery-run probabilities;
- an option map with expected threat;
- what-if swaps with Monte Carlo ranges.

The generator samples its outcomes from these same models, so the match and the explanations always agree. Check it yourself:

```bash
uv run python tasks.py calibrate
```

On seed 42, pass predictions land within 2.2 percentage points of what happened (ECE 0.022).

## Microsoft and Azure tech
_TODO (Phase 8)_

## Quick start (local)

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 20+ (pnpm via `corepack`).

```bash
cp .env.example .env
uv sync
(cd web && corepack pnpm install)
uv run python tasks.py dev     # or: make dev
```

API on http://localhost:8000, web on http://localhost:5173.

| Task | Command |
| --- | --- |
| Tests | `uv run python tasks.py test` (`make test`) |
| Lint | `uv run python tasks.py lint` (`make lint`) |
| Generate a match | `uv run python tasks.py generate --seed 42` (`make generate SEED=42`) |
| Azure smoke test | `uv run python scripts/smoke_azure.py` |

## The tactics board
`uv run python tasks.py dev` opens the board on http://localhost:5173. Press play and pick 1×, 2×, 4× or 8×.

- **Pitch:** Riverside's players are filled ink discs and Hillton's are white rings. The ball leaves a short amber trail. A badge appears when a player sprints (over 25 km/h) or passes another kilometre.
- **Key moments:** they collect in the right rail. Each amber diamond on the scrubber replays one.
- **Option map:** with *pause at key moments* on (the default), the replay stops on each moment. Green arrows show the best option, grey ones the alternatives, and the dashed green ghost the what-if.
- **Stats drawer** (chart icon): team stats, workload and fatigue, and the intensity chart.
- **Settings** (sliders icon): persona, favourite club and player, language, what-if profile.

## The stream service
`uv run python tasks.py dev` (or `make replay` for the API alone) serves the sample match on http://localhost:8000:

| Endpoint | What it does |
| --- | --- |
| `GET /match`, `GET /players` | Match metadata, replay status, squads |
| `GET /moments` (`?all=true`) | Key moments so far (or the whole replay, for the scrubber) |
| `GET /moments/{id}/analysis` | Engine option map + what-if for a moment |
| `GET /stats`, `/workload`, `/intensity` | Live team stats, player workload, intensity windows |
| `POST /replay/play`, `/pause`, `/seek {t_ms}`, `/speed {speed: 1, 2, 4 or 8}` | Replay controls |
| `GET /overlays/{id}` | A rendered card (from Phase 6) |
| `WS /ws` | `hello`, then frames, events, stats, workload, intensity, moments, analyses and status |

## Azure deploy
Phase 4 ships a hello-world deploy of the stream service to Azure Container Apps (Phase 8 adds the rest):

```bash
azd auth login
azd up
```

This creates a resource group with a Basic container registry (the image is built remotely in it, so local Docker is not needed), a Container Apps environment (consumption, scales to zero), a small Log Analytics workspace, and the `api` container app, which pulls with a managed identity. Remove it all with `azd down --purge`.

## Environment variables
See [.env.example](.env.example).

## Synthetic-data statement
No real matches, players, clubs, badges or footage are used anywhere.

## Cost
Azure free tiers first, everything else on the $200 free credit. _Details in Phase 8._

## Third-party licences
_TODO (Phase 9)_ — all dependencies are MIT / Apache-2.0 / BSD / ISC; fonts (Inter, Geist, DM Mono) are SIL OFL.

## Licence
MIT — see [LICENSE](LICENSE).
