# Decision Lens

**Every moment, every option, every fan.** Live match intelligence on a fully synthetic football match: a 2D tactics board, a transparent probability engine, and Azure OpenAI agents that explain what happened, what was possible and who could have done it.

> Built for the Microsoft Premier League "Inside the Game" hackathon. All data is synthetic — *Riverside FC* vs *Hillton United*, invented players.

| | |
| --- | --- |
| **Live demo** | **https://orange-ocean-05183100f.5.azurestaticapps.net** (free, no sign-in, running until 10 Nov 2026) |
| **Demo video** | _link coming soon_ |
| **Project pitch** | [PITCH.md](PITCH.md) |

## How judges can test it
Open the live demo; nothing to install and no account. The app scales to zero when idle, so the first load after a quiet spell can take 10–20 s.

1. **Live** (top nav). The match is a shared live broadcast that loops every 90 minutes; the score, clock and LIVE badge sit above the pitch.
2. **Key moments** appear on the right as they happen. Each card shows the chance before → after a what-if swap, and green ▲ / red ▼ reasons, all engine numbers.
3. **Click a cyan marker** on the timeline under the pitch (or *Replay* on a card) to replay that moment on your own board, with the options drawn as arrows. *Back to live* rejoins the broadcast.
4. **Switch Analyst ↔ Fan** in the nav: the same moment becomes a different card, and fan mode adds the follow-cam, momentum bar and commentary.
5. **Click a player** for their stats and key decisions; *Follow* them to highlight them and put their moments first.
6. **Change the language** (the language menu at the right of the nav): the menus, cards, commentary and copilot answers all switch.
7. **Ask the match copilot** (purple panel, under the moments), e.g. "who should mark Dax Morrow?" or "how many passes has Reyes-Ward completed?". It answers from engine tools.
8. **Analyst extras:** the chart icon under the pitch opens team stats, workload, intensity with the match's rhythm (control, pressure or chaos, window by window), and the calibration chart (the engine's predicted chances against what happened); every analyst card exports overlay JSON.

To run it yourself instead, see [Quick start](#quick-start-local).

## The problem
Broadcasts show what happened, not what was possible. A fan sees a header lost at the back post; an analyst wants to know whether it was ever winnable, what the other options were, and whether a fresh substitute would have changed it. Those answers usually take a video analyst hours after the match. Decision Lens gives them live, on the board, with every number coming from a model you can check rather than from a language model's guess.

## What it does
- **Watch the match live** on a tactics board: Riverside in blue, Hillton in yellow, 10 Hz tracking, benches, a timeline with key-moment markers.
- **Key moments explain themselves.** Each one gets a card: the options the player had (drawn on the pitch with their odds), the best one, the one chosen, and a what-if swap such as "a fresh centre-back: 4% → 46%", as green and red bullets.
- **Hover a player** for distance, fatigue, sprints, passes, shots, tackles and aerials; **click** for the 2–3 decisions that cost them most in goal odds, plus their best one.
- **Ask the match copilot** beside the board, under the key moments: "who should mark Dax Morrow?", "he's busy, who's next?", "how many passes has Reyes-Ward completed?". Answers come from engine tools and draw a chart in the chat.
- **Analyst or fan.** The same moment as numbers, ranges and drivers, or one plain line.
- **Follow a club or a player**, read the scroll-driven full-time recap.
- **Switch language** (English, Español, Français, Português, Deutsch, हिन्दी): the whole board changes, from the menus to the cards, the commentary and the copilot's answers.

Full list with status: [FEATURES.md](FEATURES.md). Colours, type and layout rules: [DESIGN.md](DESIGN.md).

## The sample match
`data/samples/match_42/` holds one generated match: `meta.jsonl`, `players.jsonl`, `events.jsonl` and `tracking.jsonl.gz` (10 Hz, 54,000 frames). Regenerate it in about a minute with `make generate SEED=42`; the same seed always produces byte-identical files.

It ends **1-1**: Reyes-Ward scores for Riverside at 70', Morrow equalises for Hillton at 87' from the late aerial duel. The engine detects **14 key moments**: the five scripted ones below, both goals, one more big chance (Reyes-Ward at 1') and six fatigue alerts.

| Minute | Scripted key moment |
| --- | --- |
| 23' | Line-breaking pass — Quill (RIV_06) splits Hillton's midfield to Reyes-Ward |
| 38' | Turnover under a high press — Hillton's press forces Varga (RIV_05) into a loose pass |
| 57' | Big chance missed — Reyes-Ward drags a shot wide |
| 71' | Tired full-back beaten on a recovery run — Kollmann (HIL_07) outruns Holt (RIV_03) |
| 86' | Late aerial duel at the back post — Morrow (HIL_09) out-jumps Pell (RIV_02) and scores |

(The board shows minutes as the match clock does, so a moment at 23:10 appears as 24'.)

## The engine
Every number in the app comes from `engine/`, never from a language model. It holds:
- live metrics, workload and fatigue;
- pass, aerial-duel, xG, recovery-run and ground-duel probabilities;
- an option map with expected threat, and goal odds for every on-ball decision;
- what-if swaps with Monte Carlo ranges;
- marking matchups (who should mark whom).

The generator samples its outcomes from these same models, so the match and the explanations always agree. Check it yourself:

```bash
uv run python tasks.py calibrate
```

On seed 42, pass predictions land within 1.2 percentage points of what happened (ECE 0.012, Brier 0.134). It writes `data/samples/match_42/calibration.json`, which the board plots in the stats drawer (chart icon → Calibration).

## Microsoft and Azure tech
- **Azure OpenAI in Foundry** through **Microsoft Agent Framework** (a mini model for analyst text, recaps and the copilot, a nano model for fan lines, a fallback deployment)
- **Model Context Protocol** server (official MCP Python SDK) exposing the engine to the agents
- **AG-UI** (`agent-framework-ag-ui`) serving the match copilot to a CopilotKit chat
- **Azure AI Translator** for the language switch (UI wording once at build time, match text live and cached)
- **Azure Container Apps**, **Event Hubs**, **Cosmos DB**, **SignalR Service**, **Static Web Apps**, **Key Vault**, **Container Registry**, **Application Insights** (OpenTelemetry), deployed with **azd + Bicep**, all with one managed identity

## Quick start (local)

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 20+ (pnpm via `corepack`).

```bash
cp .env.example .env
uv sync
(cd web && corepack pnpm install)
uv run python tasks.py dev     # or: make dev
```

API on http://localhost:8000, web on http://localhost:5173. Without Azure keys in `.env`, every card is an engine template and the copilot is off; everything else works.

| Task | Command |
| --- | --- |
| Tests (123) | `uv run python tasks.py test` (`make test`) |
| Lint (ruff, mypy, tsc) | `uv run python tasks.py lint` (`make lint`) |
| Generate a match | `uv run python tasks.py generate --seed 42` (`make generate SEED=42`) |
| Calibration | `uv run python tasks.py calibrate` |
| Azure smoke test | `uv run python scripts/smoke_azure.py` |
| Check a deployment | `uv run python scripts/check_deploy.py` |
| Translate new UI wording | `uv run python scripts/i18n_strings.py` (needs the Translator key; fixes go in `scripts/i18n_glossary.json`) |

## Four pages
| Page | What you get |
| --- | --- |
| **Home** (`#/`) | What Decision Lens does, with a looping clip of the 86' aerial duel and its what-if. |
| **How it works** (`#/how`) | The five stages and the agent architecture, with live numbers from the running match. |
| **Live** (`#/live`) | The tactics board, key-moment cards, the player panel and the match copilot. |
| **Recap** (`#/recap`) | The full-time story as green/red bullets, then scroll by scroll: the pitch stays pinned and each turning point replays. |

## The live board
- **The table.** The pitch sits on a white card under the score strip. Under the pitch, one control bar holds play/pause, speed (1×–8×), the timeline (a cyan marker per key moment), stats and settings; each team's bench sits in its own box below it. Drag the handle between the board and the moments column to resize the pitch.
- **On the pitch.** Blue tokens for Riverside, yellow for Hillton, every player named. The ball is white with a short trail. A badge appears when a player sprints (over 25 km/h) or passes another kilometre.
- **Option map.** With *pause at key moments* on (the default), the replay stops on each moment. The white arrow is the best option, faint ones the alternatives, each with its chance of success; the dashed ring is the what-if.
- **Players.** Hover a token (or a bench player) for their numbers. Click to open the player panel: stats, the moment they're in, and their key decisions with Replay. Follow a player from there: halo, their moments first in the feed, heat map in analyst mode.
- **Cards.** Green ▲ for what raised the chance, red ▼ for what lowered it, with a team stripe. Analysts can unfold the agent's one-line read; every card exports as time-coded overlay JSON.
- **Fan mode** (toggle in the nav). Tap a player and the **follow-cam** zooms the pitch onto them and glides with them, with a card showing their goals, shots, headers and an energy bar. A **momentum bar** shows who's on top over the last five minutes; goals and big chances drop a **banner** with *Watch again*; **live commentary** runs under the pitch. Cards become big one-line stories with *Watch again* and *Follow*, the feed starts with *players to watch*, and the analyst controls (speeds, stats drawer, percentages) are hidden. Commentary, banners and the momentum bar are engine templates and engine stats: no model calls.
- **Sounds.** Quiet tactile sounds when you follow or let go of a player, open or close a panel, replay a moment, switch modes, or scroll past moment cards, and a short chime on goals. They're synthesised in the browser (no audio files) and the speaker button in the nav mutes them.
- **Match copilot.** The chat in the right-hand column, under the key moments. Suggestions to start; answers follow what you're looking at (minute, analyst or fan, the player you follow).

## The agents
Built with **Microsoft Agent Framework** on **Azure OpenAI in Foundry**, at the lowest reasoning effort, with a fallback deployment:

| Agent | Job |
| --- | --- |
| Interpreter | Summarises the live state for the recap |
| Moment | Frames why a key moment matters |
| What-if | Picks the most instructive swap and runs it through the `what_if_swap` MCP tool; it never computes numbers |
| Narrator | One short line per card for analysts (≤ 25 words) and fans (≤ 15 words, no numbers) |
| Recap | The half-time and full-time story in two sentences |
| Decisions | At each whistle, one line per player decision for the player panel (one call per team) |
| Copilot | Answers viewers' questions with engine tools (player lookup, stats, decisions, best marker, match state) |

A **rules router** (a plain decision table) decides what runs: frames and events never touch a model; key moments run Moment → What-if → Narrator; the whistles run Interpreter → Recap → Decisions; a language change only calls Azure AI Translator. The copilot runs only when someone asks: 40 questions an hour per caller, 600 overall.

**Every number is checked.** A grounding guard rejects any card text with a number that isn't in the engine payload, and the length and fan-wording rules are enforced in code. A rejected card is retried once, then a template card built from engine numbers takes its place. Without Azure keys, every card is that template. `GET /agents/traces` shows where each text came from.

**MCP server.** Six engine tools (`get_match_state`, `get_player_workload`, `get_options`, `what_if_swap`, `get_intensity`, `get_recap_facts`), built with the official MCP Python SDK (v2). They are mounted at `/mcp` in the service, and can also run standalone over stdio for any MCP client:

```bash
uv run python -m mcp_server --match data/samples/match_42
```

## The stream service
`uv run python tasks.py dev` (or `make replay` for the API alone) serves the sample match on http://localhost:8000:

| Endpoint | What it does |
| --- | --- |
| `GET /match`, `GET /players` | Match metadata, replay status, squads |
| `GET /moments` (`?all=true`) | Key moments so far (or the whole replay, for the timeline) |
| `GET /moments/{id}/analysis` | Engine option map + what-if for a moment |
| `GET /moments/{id}/frames` (`?full=true`) | Tracking frames around a moment (for replays and clips; `full` for the recap, which may replay moments the live broadcast hasn't reached) |
| `GET /stats`, `/workload`, `/intensity` | Live team stats, player workload, intensity windows |
| `GET /calibration` | Reliability bins, ECE and Brier score for the pass and shot models |
| `GET /players/{id}/stats` | One player so far: km, fatigue, sprints, top-speed loss, passes, shots, goals, tackles, aerials, interceptions (the hover card) |
| `GET /players/{id}/decisions` | The 2-3 decisions that cost a player most in goal odds so far, plus their best one, with analyst and fan lines (the player panel) |
| `GET /players/{id}/heatmap` (`?full=true`) | Share of time in each 5 m cell |
| `GET /overlays` (`?all=true`) | Agent cards so far: analyst + fan text, engine payload, source |
| `GET /overlays/{id}?lang=es` | A card translated by Azure AI Translator (no model call, cached) |
| `POST /translate {lang, texts}` | Batch-translate engine text (moment titles, bullets, commentary); cached per string, 400 calls an hour per caller |
| `GET /agents/traces` | Which router steps ran per trigger and where each text came from |
| `GET /recap` | The full-time recap, whatever the live replay is doing |
| `GET /recap/moments` | The recap's turning points as moments, for its scroll chapters |
| `GET /showcase` | The home page replay: the 86' aerial duel's frames and analysis, and the match's key-moment count |
| `POST /copilot` | The match copilot over AG-UI (Server-Sent Events) for the CopilotKit chat |
| `POST /replay/play`, `/pause`, `/seek {t_ms}`, `/speed {speed: 1, 2, 4 or 8}` | Replay controls (locked in the live broadcast) |
| `POST /mcp/` | The MCP server (streamable HTTP) |
| `WS /ws` | `hello`, then frames, events, stats, workload, intensity, moments, analyses, cards and status |
| `GET /config`, `/negotiate`, `/health` | Live/SignalR flags for the board, the SignalR client token, health |

## Azure deploy
Everything runs on free tiers or the free credit. You need:
- the [Azure Developer CLI](https://aka.ms/azd);
- **Docker Desktop, running**: azd builds the API image locally (ACR remote builds are blocked on free-credit subscriptions);
- **pnpm on your PATH**: azd builds the board with it (`npm install -g pnpm@9.15.9`, or `corepack enable pnpm` from an admin terminal);
- an Azure OpenAI resource in Foundry with your deployments created by hand. The defaults are `gpt-5.4-mini`, `gpt-5.4-nano` and `gpt-4.1-mini`; set the names you actually deployed.

```bash
azd auth login
azd env new decision-lens
azd env set AZURE_OPENAI_ENDPOINT https://<your-resource>.openai.azure.com/
azd env set AZURE_OPENAI_API_KEY <key>             # stored in Key Vault, never in the repo
azd env set AZURE_OPENAI_DEPLOYMENT_MINI <name>    # e.g. gpt-5-mini
azd env set AZURE_OPENAI_DEPLOYMENT_NANO <name>    # e.g. gpt-5-mini
azd env set AZURE_TRANSLATOR_KEY <key>             # optional
azd env set AZURE_TRANSLATOR_REGION <region>       # optional
azd env set AZURE_COSMOS_LOCATION westus2          # optional: Cosmos DB region (default eastus2)
azd up
```

`azd up` provisions `infra/` (Bicep), builds and pushes the API image, deploys the board to Static Web Apps and points it at the API. It prints the public board URL (`SERVICE_WEB_URI`). After a code change, `azd deploy` updates both services; then check it with `uv run python scripts/check_deploy.py`.

**Common snags.** Cosmos DB allows one free-tier account per subscription, and a failed create can hold it: delete the failed account and wait until it's gone, or set `COSMOS_FREE_TIER=false` (about $23 a month). If a region is out of Cosmos DB capacity, pick another with `AZURE_COSMOS_LOCATION`.

| Resource | Tier | What it does | Expected cost to 10 Nov |
| --- | --- | --- | --- |
| Container Apps | consumption, min 0 / max 1 replica | stream service, engine, MCP tools, agents, copilot | free grant while idle; a few dollars while watched |
| Event Hubs | Basic, 1 TU | the live match feed | about $0.36/day |
| Cosmos DB for NoSQL | free tier, 400 RU/s | moments, analyses, cards, agent cache (partitioned by match and data version) | free |
| SignalR Service | Free | moments and cards to every board | free (20,000 messages/day) |
| Static Web Apps | Free | the board | free |
| Container Registry | Basic | API image | about $0.17/day |
| Key Vault, App Insights, Log Analytics | standard / pay-as-you-go | keys, traces | cents (1 GB/day cap) |
| Azure OpenAI | pay per token | cards, recaps, copilot | cents; the copilot is capped at 600 questions an hour |

**Live broadcast.** In Azure the match is a shared live broadcast that loops every 90 minutes, on wall-clock time. Every viewer sees the same moment, so there's no seek or speed control. Clicking a key moment plays a personal clip on your own board, then rejoins live. The score, clock and moments list stay at the live point during a clip, and the timeline only marks moments that have already happened (the server won't list or replay later ones), so nothing is spoiled. The app scales to zero when nobody is watching, so the first visit after a quiet spell takes 10–20 s to wake. Try the live behaviour locally with `LIVE_SIMULATION=true`.

When judging ends (10 Nov), remove everything:

```bash
azd down --purge
```

## Environment variables
See [.env.example](.env.example). `.env` is gitignored; locally the board reads `VITE_API_URL`, and a deployed board reads `/config.json` written by the azd hook (ignored in local dev).

## Synthetic-data statement
No real matches, players, clubs, badges or footage are used anywhere.

## Cost
Azure free tiers first, everything else on the $200 free credit (see the table under Azure deploy). Nothing is upgraded to pay-as-you-go beyond model tokens, and no Marketplace or partner models are used.

## Third-party licences
All dependencies are MIT, Apache-2.0, BSD or ISC; the fonts (Inter, Urbanist, DM Mono) are SIL OFL and self-hosted. Notable ones: React, Vite, Tailwind CSS, Radix UI, Framer Motion, Zustand, d3, recharts, Lenis (web); FastAPI, Pydantic, NumPy, orjson, the MCP Python SDK, Microsoft Agent Framework and `agent-framework-ag-ui` (service). The match copilot uses CopilotKit (`@copilotkit/react-core`, MIT) and the AG-UI client (`@ag-ui/client`, MIT); CopilotKit's hosted Intelligence service and its inspector are not used.

## Licence
MIT — see [LICENSE](LICENSE).
