# Plan: player insights (hover stats, decision panel, recap bullets)

Approved choices: no cards (no bookings in the generator); decision lines from engine templates
live, one agent call per team at half-time and at full-time to rewrite them (4 calls a match).

## 1. Contracts (additive, nothing existing changes)
`contracts/player.py`:
- `PlayerStats`: workload (km, high-speed running, sprints, fatigue, % off top speed, status) and
  counts from events (passes / completed, shots, goals, tackles / won, interceptions,
  aerial duels / won, dribbles / won, fouls).
- `DecisionOption`: action, target, p_success, `goal_odds` (chance the possession ends in a goal).
- `PlayerDecision`: when, kind (`on_ball` | `defending`), chosen vs best option, `goal_odds_gain`
  (best − chosen), what followed within 15 s (`goal_for`, `shot_for`, `goal_against`,
  `shot_against`, `lost_ball`), its xG, `positive`, card text per persona, source.
- `PlayerDecisions`: player, time, items.
Exported to JSON Schema and TypeScript like every other record.

## 2. Engine: `engine/decisions.py`
- Goal odds of an option: shot = xG; pass, cross, carry = p_success × xT at the end point
  (the threat grid value is the chance a possession from there becomes a goal).
- `score_on_ball(snapshot, event)`: the option scorer's candidates at the moment of a pass, shot,
  cross or dribble → chosen vs best by goal odds. No Monte Carlo (ranking only).
- `defending(events)`: a lost tackle or aerial duel, or being dribbled past, that is followed by an
  opponent shot within 15 s; costed by that shot's xG. The last defender involved is blamed.
- `consequence(events, t)`: what the next 15 s brought.
- `top_decisions(...)`: the 2–3 costliest plus the best positive one, so it isn't all negative.
- Template lines in the user's framing, e.g. "A pass to Venn would have raised the goal odds from
  2% to 9%", and plain words for fans.

## 3. Service
- Warm-up keeps every event and a snapshot at each on-ball decision (the detector's buffer).
- `GET /players/{id}/stats?t_ms=` and `GET /players/{id}/decisions?t_ms=` (up to the replay
  clock), scored lazily in a thread and cached per event.

## 4. Agents
- New `DECISIONS` prompt: given one team's players and their engine-ranked decisions, write one
  short line per decision for analysts and fans. Every number grounded; length-checked.
- Triggered from the period-end hook (half-time, full-time): one call per team, so 4 a match.
  Lines are cached by decision id; the endpoint returns agent text when it exists, else templates.

## 5. Web
- Hover a token: a small card with km, fatigue, sprints, top-speed loss and the event counts.
- Click a token: a side panel (Follow moved inside): stats, then the decisions with green ▲ / red ▼
  bullets, chosen vs best goal odds, what followed and a Replay button. During a pinned key
  moment, that moment's decision for the player comes first.
- Recap page: the story as green/red bullets built from engine facts; the agents' paragraph shrinks
  to two sentences and folds under "Read the recap".

## 6. Checks
Engine tests (goal odds, ranking, defending attribution), endpoint tests, the batched agent call
with a fake model, typecheck/build, browser check, docs.
