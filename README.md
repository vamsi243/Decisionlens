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
- **Azure OpenAI in Foundry** (`gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-4.1-mini` fallback) through **Microsoft Agent Framework**
- **Model Context Protocol** server (official MCP Python SDK) exposing the engine to the agents
- **Azure AI Translator** for per-card language switching
- **Azure Container Apps**, **Event Hubs**, **Cosmos DB**, **SignalR Service**, **Static Web Apps**, **Key Vault**, **Container Registry**, **Application Insights** (OpenTelemetry), deployed with **azd + Bicep**, all with one managed identity

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

## Three pages
| Page | What you get |
| --- | --- |
| **Live** (`#/`) | The tactics board, key-moment cards, scrubber, stats drawer. Click a player to follow them (halo, name tag, their moments first in the feed, heat map in analyst mode). |
| **Recap** (`#/recap`) | The full-time story, scroll by scroll. The pitch stays pinned and scrolling through each turning point replays it, ending on the option map and the what-if ghost. |
| **How it works** (`#/how`) | The five stages and the agent architecture, with live numbers from the running match. |

**Analyst vs fan.** The analyst card shows the option map, ranges, drivers, workload, intensity and a heat map, and every card exports as time-coded overlay JSON. The fan view is one plain-words line in larger type; on the board, fans see only the best and chosen options and a what-if ghost labelled in words.

## The agents
Five agents built with **Microsoft Agent Framework** on **Azure OpenAI in Foundry** (`gpt-5.4-mini` for analyst text and recaps, `gpt-5.4-nano` for fan lines, lowest reasoning effort, `gpt-4.1-mini` as the fallback):

| Agent | Job |
| --- | --- |
| Interpreter | Summarises the live state for the recap |
| Moment | Frames why a key moment matters |
| What-if | Picks the most instructive swap and runs it through the `what_if_swap` MCP tool; it never computes numbers |
| Narrator | Writes the analyst card and the fan line from the engine payload |
| Recap | Half-time and full-time turning points |

A **rules router** (a plain decision table) decides what runs: frames and events never touch a model; key moments run Moment → What-if → Narrator; a language change only calls Azure AI Translator.

**Every number is checked.** Before a card is shown, a grounding guard rejects any number that is not in the engine payload. A rejected card is retried once (told which numbers were wrong), and if that fails too, a template card built from engine numbers takes its place. Without Azure keys, every card is that template. You can see where each card came from in `GET /agents/traces`.

**MCP server.** Six engine tools (`get_match_state`, `get_player_workload`, `get_options`, `what_if_swap`, `get_intensity`, `get_recap_facts`), built with the official MCP Python SDK (v2). They are mounted at `/mcp` in the service, and can also run standalone over stdio for any MCP client:

```bash
uv run python -m mcp_server --match data/samples/match_42
```

## The stream service
`uv run python tasks.py dev` (or `make replay` for the API alone) serves the sample match on http://localhost:8000:

| Endpoint | What it does |
| --- | --- |
| `GET /match`, `GET /players` | Match metadata, replay status, squads |
| `GET /moments` (`?all=true`) | Key moments so far (or the whole replay, for the scrubber) |
| `GET /moments/{id}/analysis` | Engine option map + what-if for a moment |
| `GET /stats`, `/workload`, `/intensity` | Live team stats, player workload, intensity windows |
| `GET /players/{id}/stats` | One player so far: km, fatigue, sprints, top-speed loss, passes, shots, goals, tackles, aerials, interceptions (the hover card) |
| `GET /players/{id}/decisions` | The 2-3 decisions that cost a player most in goal odds so far, plus their best one, with analyst and fan lines (the player panel) |
| `POST /copilot` | The match copilot over AG-UI (Server-Sent Events) for the CopilotKit chat; 40 questions an hour per caller, 600 overall |
| `POST /replay/play`, `/pause`, `/seek {t_ms}`, `/speed {speed: 1, 2, 4 or 8}` | Replay controls |
| `GET /overlays` (`?all=true`) | Agent cards so far: analyst + fan text, engine payload, source |
| `GET /overlays/{id}?lang=es` | A card translated by Azure AI Translator (no model call, cached) |
| `GET /agents/traces` | Which router steps ran per trigger and where each text came from |
| `GET /moments/{id}/frames` | Tracking frames around a moment (for replays) |
| `GET /players/{id}/heatmap` (`?full=true`) | Share of time in each 5 m cell |
| `GET /recap` | The full-time recap, whatever the live replay is doing |
| `POST /mcp/` | The MCP server (streamable HTTP) |
| `WS /ws` | `hello`, then frames, events, stats, workload, intensity, moments, analyses and status |

## Azure deploy
Everything runs on free tiers or the free credit. You need the [Azure Developer CLI](https://aka.ms/azd) and an Azure OpenAI deployment in Foundry (created by hand: `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-4.1-mini`). The Translator key is optional. azd builds the board with `pnpm` itself, so pnpm must be on your PATH (`npm install -g pnpm@9.15.9`, or `corepack enable pnpm` from an admin terminal).

```bash
azd auth login
azd env new decision-lens
azd env set AZURE_OPENAI_ENDPOINT https://<your-resource>.openai.azure.com/
azd env set AZURE_OPENAI_API_KEY <key>          # stored in Key Vault, never in the repo
azd env set AZURE_TRANSLATOR_KEY <key>          # optional
azd env set AZURE_TRANSLATOR_REGION <region>    # optional
azd up
```

`azd up` provisions `infra/` (Bicep), builds the API image with your local Docker (start Docker Desktop first; ACR remote builds are blocked on free-credit subscriptions) and pushes it to the registry, deploys the board to Static Web Apps and points it at the API. It prints the public board URL (`SERVICE_WEB_URI`).

| Resource | Tier | What it does | Expected cost to 10 Nov |
| --- | --- | --- | --- |
| Container Apps | consumption, min 0 / max 1 replica | stream service, engine, MCP tools, agents | free grant while idle; a few dollars while watched |
| Event Hubs | Basic, 1 TU | the live match feed | about $0.36/day |
| Cosmos DB for NoSQL | free tier, 400 RU/s | moments, analyses, cards, agent cache | free |
| SignalR Service | Free | moments and cards to every board | free (20,000 messages/day) |
| Static Web Apps | Free | the board | free |
| Container Registry | Basic | API image | about $0.17/day |
| Key Vault, App Insights, Log Analytics | standard / pay-as-you-go | keys, traces | cents (1 GB/day cap) |

**Live broadcast.** In Azure the match is a shared live broadcast that loops every 90 minutes, on wall-clock time. Every viewer sees the same moment, so there's no seek or speed control. Clicking a key moment plays a personal clip on your own board, then rejoins live. The app scales to zero when nobody is watching, so the first visit after a quiet spell takes 10–20 s to wake. Try the live behaviour locally with `LIVE_SIMULATION=true`.

When judging ends (10 Nov), remove everything:

```bash
azd down --purge
```

## Environment variables
See [.env.example](.env.example).

## Synthetic-data statement
No real matches, players, clubs, badges or footage are used anywhere.

## Cost
Azure free tiers first, everything else on the $200 free credit (see the table under Azure deploy). Nothing is upgraded to pay-as-you-go, and no Marketplace or partner models are used.

## Third-party licences
_TODO (Phase 9)_ — all dependencies are MIT / Apache-2.0 / BSD / ISC; fonts (Inter, Geist, DM Mono) are SIL OFL. The match copilot uses CopilotKit (`@copilotkit/react-core`, MIT), the AG-UI client (`@ag-ui/client`, MIT) and Microsoft's `agent-framework-ag-ui` (MIT); CopilotKit's hosted Intelligence service is not used.

## Licence
MIT — see [LICENSE](LICENSE).
