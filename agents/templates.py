"""Template cards written from engine facts alone: the fallback whenever a model call fails,
times out, is ungrounded twice, or no model is configured. Grounded by construction."""

from __future__ import annotations

from typing import Any

VERB = {
    "aerial_duel": "to win that header",
    "recovery_run": "to catch the runner",
    "big_chance": "to score",
    "goal": "to score",
    "line_breaking_pass": "to find that pass",
    "press_turnover": "to play out of the press",
}


def swing(before: int, after: int) -> str:
    d = after - before
    if d > 25:
        return "much more likely"
    if d > 8:
        return "more likely"
    if d >= -8:
        return "about as likely"
    if d >= -25:
        return "less likely"
    return "much less likely"


def _short(label: str, start: bool = False) -> str:
    """Swap label for use in a sentence ('A deep playmaker' -> 'a deep playmaker' mid-sentence)."""
    s = label.replace(" (fresh sub)", "")
    if not start and (s.startswith("A ") or s.startswith("An ")):
        s = s[0].lower() + s[1:]
    return s


def _option_sentence(f: dict[str, Any]) -> str:
    opts = f.get("options")
    if not opts:
        return ""
    best = next((o for o in opts["list"] if o["best"]), None)
    chosen = next((o for o in opts["list"] if o["chosen"]), None)
    if best is None:
        return ""
    to = f" to {best['to']}" if best["to"] else ""
    s = f" The best option was a {best['action']}{to} at {best['success_pct']}%"
    if chosen and chosen is not best:
        cto = f" to {chosen['to']}" if chosen["to"] else ""
        s += f"; {opts['player']} chose a {chosen['action']}{cto} at {chosen['success_pct']}%"
    return s + "."


def moment_analyst(f: dict[str, Any]) -> str:
    s = f"{f['headline']} ({f['minute']}')."
    w = f.get("what_if")
    if w:
        lo, hi = w["actual_range_pct"]
        slo, shi = w["swap_range_pct"]
        s += (
            f" {w['player']} had a {w['actual_pct']}% chance (range {lo}-{hi}%);"
            f" {_short(w['swap'])} would have had {w['swap_pct']}% (range {slo}-{shi}%)"
        )
        s += f": {', '.join(w['drivers'])}." if w["drivers"] else "."
    s += _option_sentence(f)
    wl = f.get("workload")
    if wl and wl["fatigue"] >= 40:
        s += f" {wl['player']} was at fatigue {wl['fatigue']} after {wl['distance_km']} km."
    return s


def moment_fan(f: dict[str, Any]) -> str:
    w = f.get("what_if")
    if f["type"] == "goal":
        scorer = f["players"][0] if f["players"] else "They"
        return f"{scorer} scores for {f['team']}!"
    if w:
        verb = VERB.get(f["type"], "to come out on top")
        how = swing(w["actual_pct"], w["swap_pct"])
        return f"{_short(w['swap'], start=True)} would have been {how} {verb}."
    return f"{f['headline']}."


def fatigue_analyst(f: dict[str, Any]) -> str:
    wl = f.get("workload")
    if not wl:
        return f"{f['headline']}."
    s = (
        f"{wl['player']} is at fatigue {wl['fatigue']} after {wl['distance_km']} km,"
        f" {wl['top_speed_loss_pct']}% off top speed."
    )
    subs = f.get("fresh_subs") or []
    if subs:
        s += f" Fresh options on the bench: {', '.join(subs)}."
    return s


def fatigue_fan(f: dict[str, Any]) -> str:
    wl = f.get("workload")
    who = wl["player"] if wl else (f["players"][0] if f["players"] else "He")
    return f"{who} is running on empty: time for fresh legs?"


def recap_analyst(r: dict[str, Any]) -> str:
    teams = list(r["score"].items())
    (h, hg), (a, ag) = teams[0], teams[1]
    s = f"{h} {hg}-{ag} {a} after {r['minute']} minutes."
    if r["goals"]:
        s += " Goals: " + ", ".join(f"{g['scorer']} {g['minute']}'" for g in r["goals"]) + "."
    tp = next((t for t in r["turning_points"] if "what_if" in t), None)
    if tp:
        w = tp["what_if"]
        s += (
            f" Turning point: {tp['title']} ({tp['minute']}'), where {_short(w['swap'])}"
            f" would have moved the chance from {round(w['actual'] * 100)}% to"
            f" {round(w['with_swap'] * 100)}%."
        )
    if r["furthest_running"]:
        top = r["furthest_running"][0]
        s += f" {top['player']} ran furthest ({top['km']} km)."
    return s


def recap_fan(r: dict[str, Any]) -> str:
    teams = list(r["score"].items())
    (h, hg), (a, ag) = teams[0], teams[1]
    lead = "level" if hg == ag else (h if hg > ag else a) + " ahead"
    tp = r["turning_points"][0]["title"] if r["turning_points"] else "a tight contest"
    return f"{h} {hg}-{ag} {a}, {lead}. The moment everyone will talk about: {tp}."


# ------------------------------------------------------------------ player decisions
FOLLOW = {
    "goal_for": "{team} scored",
    "shot_for": "{team} had a shot",
    "goal_against": "{opponents} scored",
    "shot_against": "{opponents} had a shot",
    "lost_ball": "the ball was lost",
}


def _act(o: dict[str, Any]) -> str:
    return f"{o['action']} to {o['to']}" if o.get("to") else o["action"]


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def decision_analyst(f: dict[str, Any]) -> str:
    m = f["minute"]
    if f["kind"] == "defending":
        lost = f.get("lost") or {"what": "a duel", "to": "an opponent"}
        s = f"{m}' Lost {lost['what']} to {lost['to']}"
    elif f["positive"]:
        c = f["chosen"]
        s = f"{m}' {_cap(_act(c))} was the best option: {c['goal_odds_pct']}% goal odds"
    else:
        c, b = f["chosen"], f["better"]
        s = (
            f"{m}' {_cap(_act(c))} gave {c['goal_odds_pct']}% goal odds;"
            f" a {_act(b)} would have raised them to {b['goal_odds_pct']}%"
        )
    follow = FOLLOW.get(f["followed"])
    if follow and not (f["kind"] == "on_ball" and f.get("chosen", {}).get("action") == "shot"):
        s += f"; {follow.format(**f)} within {f['window_s']} s"
        if f.get("shot_xg_pct") is not None and f["followed"].startswith("shot"):
            s += f" ({f['shot_xg_pct']}% xG)"
    elif f["followed"] == "goal_for":
        s += ", and it went in"
    return s + "."


def decision_fan(f: dict[str, Any]) -> str:
    if f["kind"] == "defending":
        lost = f.get("lost") or {"what": "a duel", "to": "an opponent"}
        end = "scored" if f["followed"] == "goal_against" else "had a shot"
        return f"Lost {lost['what']} to {lost['to']}, and {f['opponents']} {end}."
    if f["positive"]:
        return (
            "Picked the best option, and it ended in a goal!"
            if f["followed"] == "goal_for"
            else "Picked the best option."
        )
    s = f"A {_act(f['better'])} would have given a better chance of a goal."
    if f["followed"] in ("goal_against", "shot_against"):
        s += f" {FOLLOW[f['followed']].format(**f)} soon after."
    return s
