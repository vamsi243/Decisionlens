"""Check a Decision Lens deployment end to end.

Reads the URLs from the azd environment (or takes them as arguments) and checks the board, the
API, the live broadcast, SignalR, Cosmos-backed cards, the agents and the recap.

Run after `azd up`:  uv run python scripts/check_deploy.py
Or explicitly:       uv run python scripts/check_deploy.py --api https://ca-api-... --web https://...
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time

import httpx
import websockets

OK, WARN, FAIL = "PASS", "WARN", "FAIL"
results: list[tuple[str, str, str]] = []


def report(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))
    print(f"[{status}] {name}{': ' + detail if detail else ''}", flush=True)


def azd_value(key: str) -> str:
    exe = shutil.which("azd")
    if not exe:
        return ""
    out = subprocess.run([exe, "env", "get-value", key], capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else ""


def get(client: httpx.Client, url: str, **kw: object) -> httpx.Response:
    return client.get(url, timeout=60, **kw)  # type: ignore[arg-type]


async def ws_frames(api: str, seconds: float = 5.0) -> tuple[int, int, bool]:
    url = api.replace("https://", "wss://").replace("http://", "ws://") + "/ws"
    async with websockets.connect(url, max_size=None, open_timeout=60) as ws:
        hello = json.loads(await ws.recv())
        frames, first = 0, None
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=end - time.monotonic()))
            except TimeoutError:
                break
            if msg["type"] == "frame":
                frames += 1
                first = first if first is not None else msg["data"]["frame"]
        return frames, first or 0, hello["type"] == "hello"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=azd_value("SERVICE_API_URI"))
    ap.add_argument("--web", default=azd_value("SERVICE_WEB_URI"))
    a = ap.parse_args()
    api, web = a.api.rstrip("/"), a.web.rstrip("/")
    if not api:
        print("No API URL: pass --api or run inside the azd environment.")
        return 2
    print(f"API {api}\nWEB {web or '(not given)'}\n")

    with httpx.Client(follow_redirects=True) as c:
        # 1. wake the app (it scales to zero) and basic health
        t0 = time.monotonic()
        try:
            r = get(c, f"{api}/health")
            report(
                OK if r.status_code == 200 else FAIL,
                "API health",
                f"{r.json()} in {time.monotonic() - t0:.1f}s (includes any cold start)",
            )
        except httpx.HTTPError as exc:
            report(FAIL, "API health", str(exc))
            return 1

        cfg = get(c, f"{api}/config").json()
        report(
            OK if cfg.get("live") else WARN,
            "Live broadcast (Event Hubs)",
            f"live={cfg.get('live')}",
        )
        report(
            OK if cfg.get("signalr") else WARN,
            "SignalR configured",
            f"signalr={cfg.get('signalr')}",
        )

        status = get(c, f"{api}/match").json()["status"]
        drift = abs(status["frame"] - (int(time.time() * 10) % (status["duration_ms"] // 100)))
        report(
            OK if status.get("live") and drift < 100 else WARN,
            "Broadcast on wall-clock time",
            f"frame {status['frame']}, drift {drift} frames",
        )

        r = c.post(f"{api}/replay/seek", json={"t_ms": 0}, timeout=30)
        report(
            OK if r.status_code == 409 else WARN,
            "Replay controls locked in live mode",
            f"HTTP {r.status_code}",
        )

        # 2. frames over the service WebSocket
        try:
            n, first, hello = asyncio.run(ws_frames(api))
            report(
                OK if hello and n >= 30 else FAIL,
                "WebSocket frames",
                f"{n} frames in 5 s from frame {first} (expect ~50)",
            )
        except Exception as exc:
            report(FAIL, "WebSocket frames", repr(exc))

        # 3. SignalR negotiate (managed identity -> client token)
        if cfg.get("signalr"):
            r = get(c, f"{api}/negotiate")
            ok = r.status_code == 200 and "accessToken" in r.json()
            report(
                OK if ok else FAIL,
                "SignalR negotiate",
                r.json().get("url", r.text[:120]) if ok else r.text[:200],
            )

        # 4. moments, analyses, cards (Cosmos-backed) and agent traces
        moments = get(c, f"{api}/moments", params={"all": "true"}).json()
        report(OK if len(moments) >= 10 else WARN, "Key moments detected", str(len(moments)))
        deadline = time.monotonic() + 90
        cards: list[dict[str, object]] = []
        while time.monotonic() < deadline:
            cards = get(c, f"{api}/overlays", params={"all": "true"}).json()
            if len(cards) >= len(moments):
                break
            time.sleep(3)
        sources: dict[str, int] = {}
        for o in cards:
            sources[str(o["source"])] = sources.get(str(o["source"]), 0) + 1
        report(OK if cards else FAIL, "Cards generated", f"{len(cards)}/{len(moments)} {sources}")
        if cards and sources.get("template", 0) == len(cards):
            report(
                WARN,
                "Agents",
                "every card is an engine template: check AZURE_OPENAI_* and the deployments",
            )
        elif cards:
            report(
                OK,
                "Agents writing grounded cards",
                f"{sources.get('agents', 0) + sources.get('mixed', 0)} by agents",
            )
        if cards:
            r = get(c, f"{api}/overlays/{cards[0]['overlay_id']}", params={"lang": "es"})
            report(
                OK if r.status_code == 200 else WARN,
                "Translator",
                "es translation"
                if r.status_code == 200
                else f"HTTP {r.status_code} (no Translator key?)",
            )
        traces = get(c, f"{api}/agents/traces").json()
        report(OK if traces else WARN, "Agent traces", f"{len(traces)} triggers traced")

        # 5. recap and replay clip data
        r = get(c, f"{api}/recap")
        report(
            OK if r.status_code == 200 and r.json().get("kind") == "recap" else FAIL,
            "Full-time recap",
            r.json()["text"]["analyst"]["en"][:100] if r.status_code == 200 else r.text[:120],
        )
        if moments:
            fr = get(c, f"{api}/moments/{moments[0]['moment_id']}/frames").json()
            report(OK if len(fr) > 50 else FAIL, "Moment clip frames", f"{len(fr)} frames")

        # 6. the board on Static Web Apps, pointed at this API
        if web:
            r = get(c, web)
            report(
                OK if r.status_code == 200 and "Decision Lens" in r.text else FAIL,
                "Board on Static Web Apps",
                f"HTTP {r.status_code}",
            )
            r = get(c, f"{web}/config.json")
            ok = r.status_code == 200 and r.json().get("apiUrl", "").rstrip("/") == api
            report(OK if ok else FAIL, "Board points at the API", r.text.strip()[:120])

    fails = sum(1 for s, _, _ in results if s == FAIL)
    warns = sum(1 for s, _, _ in results if s == WARN)
    print(f"\n{len(results) - fails - warns} passed, {warns} warnings, {fails} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
