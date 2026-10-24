# Features

Status: **done** / **partial** / **todo** / **cut**. Priority: M must, S should, C cut first.

| # | Feature | Pri | Status | How to see it | Stage |
| --- | --- | --- | --- | --- | --- |
| F1 | Synthetic match generator | M | done — seeded and deterministic, all 5 scripted moments, outcomes sampled from the engine | `make generate SEED=42`, then `uv run python scripts/dot_viewer.py data/samples/match_42 --start 85:58 --end 86:18` | Ingest |
| F2 | Live stream of events + 10 Hz tracking | M | done — locally: `FileReplay` at 1×/2×/4×/8× with pause and seek; in Azure: a shared live broadcast through Event Hubs on wall-clock time with personal moment clips; rate tested | `make replay`; `LIVE_SIMULATION=true` for the live path | Ingest |
| F3 | Tactics board | M | done — SVG pitch, 22 players, ball with a fading trail; 60 fps interpolation between 10 Hz frames; resizes with the window | `make dev` → http://localhost:5173 | Render |
| F4 | Name tags + speed/distance badges | M | done — speed badge above 25 km/h (7 m/s); a distance badge as each new kilometre is passed; name tags for the focused player and players in a moment | board | Render |
| F5 | Live stats | M | done — engine `StatsTracker` (a test recounts it from raw events); team tab in the stats drawer | chart icon → Team | Interpret |
| F6 | Pass quality | M | partial — `pass_success` + `pass_difficulty` (0–100); UI in Phase 5 | `engine/probability.py` | Interpret |
| F7 | Workload | M | done — distance, high-speed running and sprints match tracking within 1% (tested); workload table in the drawer; heat map of the followed player on the board | chart icon → Workload; follow a player → Heat map | Interpret |
| F8 | Fatigue score and status | M | done — shared fatigue model; modifiers feed every probability; fatigue bars coloured by status; fatigue-alert cards | chart icon → Workload | Interpret |
| F9 | Match intensity index | M | done — 5-minute index; every key-moment window sits above the match median (tested); bar chart with key-moment lines | chart icon → Intensity | Interpret |
| F10 | Key-moment detector | M | done — rules over events and tracking (never the scripted tags); flags all 5 scripted moments plus goals, real big chances and fatigue alerts (17 on seed 42) | `GET /moments?all=true` | Explain |
| F11 | Option map | M | done — up to 4 options with p_success, P10–P90 range, xT gain and path; curved arrows sized by probability, best in green, chosen ringed | replay a moment from the scrubber | Explain |
| F12 | What-if swap | M | done — archetype, custom or fresh-sub swap; before → after with ranges and drivers; dashed ghost on the board, card in the rail | moment cards | Explain |
| F13 | Grounded agent explanations | M | done — five Agent Framework agents behind a rules router; a grounding guard rejects any number not in the engine payload (retry, then template). Verified with a scripted backend; a live model run needs your Azure keys (`scripts/smoke_azure.py`) | moment cards, `GET /agents/traces` | Explain |
| F14 | Analyst vs fan mode | M | done — analyst: option map with %, ranges, drivers, charts, JSON export; fan: one plain line in larger type, best/chosen arrows only, what-if in words. Same moment, clearly different cards | top bar toggle | Personalize |
| F15 | Favourite player and club | M | done — click a player (or use settings) to follow them: halo, name tag, their moments in a strip at the top of the feed, heat map; club filter on the feed | click a player | Personalize |
| F16 | Language switch | M | done — `GET /overlays/{id}?lang=` translates through Azure AI Translator (cached, no model call); without a key cards stay in English and the feed says so | language select | Personalize |
| F17 | Automated recap | M | done — the period-end event runs Interpreter → Recap; recap cards appear in the feed at half-time and full-time | play past 45:00 | Explain |
| F18 | Timeline scrubber | M | done — drag or arrow keys to seek; amber markers jump to a few seconds before a moment and replay it | bottom bar | Render |
| F19 | Scroll-driven recap page | S | done — pinned pitch; each turning point is a chapter whose scroll progress replays the moment; Lenis smooth scroll with section snap on desktop | `#/recap` | Render |
| F20 | Calibration chart | S | partial — `make calibrate` prints reliability bins, Brier score and ECE; chart in Phase 9 | `engine/calibration.py` | Explain |
| F21 | Overlay JSON export | S | done — "Overlay JSON" on every analyst card, and "export every card" in the stats drawer (time-coded, both personas, engine payload) | analyst card footer | Render |
| F22 | Custom profile builder | C | todo | | Personalize |
| F23 | Application Insights traces | S | partial — OpenTelemetry via Azure Monitor: one trace per trigger (moment, half-time, full-time) with a child span per agent step, plus Agent Framework's GenAI spans; verified to run locally, not yet seen in a deployed workspace | Azure portal → Application Insights → Transactions | — |
