# Features

Status: **done** / **partial** / **todo** / **cut**. Priority: M must, S should, C cut first.

| # | Feature | Pri | Status | How to see it | Stage |
| --- | --- | --- | --- | --- | --- |
| F1 | Synthetic match generator | M | done — seeded and deterministic, all 5 scripted moments, outcomes sampled from the engine | `make generate SEED=42`, then `uv run python scripts/dot_viewer.py data/samples/match_42 --start 85:58 --end 86:18` | Ingest |
| F2 | Live stream of events + 10 Hz tracking | M | todo | | Ingest |
| F3 | Tactics board | M | todo | | Render |
| F4 | Name tags + speed/distance badges | M | todo | | Render |
| F5 | Live stats | M | partial — engine `StatsTracker` (a test recounts it from raw events); UI in Phase 5 | `engine/metrics.py` | Interpret |
| F6 | Pass quality | M | partial — `pass_success` + `pass_difficulty` (0–100); UI in Phase 5 | `engine/probability.py` | Interpret |
| F7 | Workload | M | partial — `WorkloadTracker`: distance, high-speed running, sprints, heat map; matches tracking within 1% (tested) | `engine/metrics.py` | Interpret |
| F8 | Fatigue score and status | M | partial — shared fatigue model; modifiers feed every probability and also slow players in the generator | `engine/fatigue.py` | Interpret |
| F9 | Match intensity index | M | partial — 5-minute index; every key-moment window sits above the match median (tested); chart in Phase 5 | `engine/metrics.py` | Interpret |
| F10 | Key-moment detector | M | todo | | Explain |
| F11 | Option map | M | partial — up to 4 options, each with p_success, P10–P90 range, xT gain and path; rendering in Phase 5 | `engine/options.py` | Explain |
| F12 | What-if swap | M | partial — archetype, custom or fresh-sub swap; before → after with ranges and drivers | `engine/whatif.py` | Explain |
| F13 | Grounded agent explanations | M | todo | | Explain |
| F14 | Analyst vs fan mode | M | todo | | Personalize |
| F15 | Favourite player and club | M | todo | | Personalize |
| F16 | Language switch | M | todo | | Personalize |
| F17 | Automated recap | M | todo | | Explain |
| F18 | Timeline scrubber | M | todo | | Render |
| F19 | Scroll-driven recap page | S | todo | | Render |
| F20 | Calibration chart | S | partial — `make calibrate` prints reliability bins, Brier score and ECE; chart in Phase 9 | `engine/calibration.py` | Explain |
| F21 | Overlay JSON export | S | todo | | Render |
| F22 | Custom profile builder | C | todo | | Personalize |
| F23 | Application Insights traces | S | todo | | — |
