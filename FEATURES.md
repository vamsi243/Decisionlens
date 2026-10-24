# Features

Status: **done** / **partial** / **todo** / **cut**. Priority: M must, S should, C cut first.

| # | Feature | Pri | Status | How to see it | Stage |
| --- | --- | --- | --- | --- | --- |
| F1 | Synthetic match generator | M | done — seeded and deterministic, all 5 scripted moments, outcomes sampled from the engine | `make generate SEED=42`, then `uv run python scripts/dot_viewer.py data/samples/match_42 --start 85:58 --end 86:18` | Ingest |
| F2 | Live stream of events + 10 Hz tracking | M | done — `FileReplay` at 1×/2×/4×/8× with pause and seek; WebSocket `/ws`; rate tested at every speed | `make replay`, connect to `ws://localhost:8000/ws` | Ingest |
| F3 | Tactics board | M | done — SVG pitch, 22 players, ball with a fading trail; 60 fps interpolation between 10 Hz frames; resizes with the window | `make dev` → http://localhost:5173 | Render |
| F4 | Name tags + speed/distance badges | M | done — speed badge above 25 km/h (7 m/s); a distance badge as each new kilometre is passed; name tags for the focused player and players in a moment | board | Render |
| F5 | Live stats | M | done — engine `StatsTracker` (a test recounts it from raw events); team tab in the stats drawer | chart icon → Team | Interpret |
| F6 | Pass quality | M | partial — `pass_success` + `pass_difficulty` (0–100); UI in Phase 5 | `engine/probability.py` | Interpret |
| F7 | Workload | M | partial — distance, high-speed running and sprints match tracking within 1% (tested); workload table in the drawer; heat maps computed but not drawn yet | chart icon → Workload | Interpret |
| F8 | Fatigue score and status | M | done — shared fatigue model; modifiers feed every probability; fatigue bars coloured by status; fatigue-alert cards | chart icon → Workload | Interpret |
| F9 | Match intensity index | M | done — 5-minute index; every key-moment window sits above the match median (tested); bar chart with key-moment lines | chart icon → Intensity | Interpret |
| F10 | Key-moment detector | M | done — rules over events and tracking (never the scripted tags); flags all 5 scripted moments plus goals, real big chances and fatigue alerts (17 on seed 42) | `GET /moments?all=true` | Explain |
| F11 | Option map | M | done — up to 4 options with p_success, P10–P90 range, xT gain and path; curved arrows sized by probability, best in green, chosen ringed | replay a moment from the scrubber | Explain |
| F12 | What-if swap | M | done — archetype, custom or fresh-sub swap; before → after with ranges and drivers; dashed ghost on the board, card in the rail | moment cards | Explain |
| F13 | Grounded agent explanations | M | todo | | Explain |
| F14 | Analyst vs fan mode | M | partial — the same moment renders as a numbers card (analyst) or one plain line (fan); agent-written text in Phase 6 | top bar toggle | Personalize |
| F15 | Favourite player and club | M | partial — halo and name tag on the board; their cards ringed in the feed; feed ordering in Phase 7 | settings sheet | Personalize |
| F16 | Language switch | M | todo | | Personalize |
| F17 | Automated recap | M | todo | | Explain |
| F18 | Timeline scrubber | M | done — drag or arrow keys to seek; amber markers jump to a few seconds before a moment and replay it | bottom bar | Render |
| F19 | Scroll-driven recap page | S | todo | | Render |
| F20 | Calibration chart | S | partial — `make calibrate` prints reliability bins, Brier score and ECE; chart in Phase 9 | `engine/calibration.py` | Explain |
| F21 | Overlay JSON export | S | todo | | Render |
| F22 | Custom profile builder | C | todo | | Personalize |
| F23 | Application Insights traces | S | todo | | — |
