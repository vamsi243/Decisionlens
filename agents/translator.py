"""Azure AI Translator (Free F0) adapter: switch a card's language without a new model call.

Uses the Translator v3 REST API (`POST {endpoint}/translate?api-version=3.0&to=xx`). Results are
cached per overlay and language. Without a key, cards stay in English.
"""

from __future__ import annotations

import logging
import uuid

import httpx

from contracts import Overlay, Persona
from service.settings import Settings

log = logging.getLogger("decision_lens.translator")


class Translator:
    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.transport = transport  # injectable for tests
        self.endpoint = settings.azure_translator_endpoint.rstrip("/")
        self.key = settings.azure_translator_key
        self.region = settings.azure_translator_region
        self.cache: dict[tuple[str, str], Overlay] = {}

    @property
    def available(self) -> bool:
        return bool(self.key)

    async def translate(self, texts: list[str], to: str) -> list[str] | None:
        if not self.available:
            return None
        headers = {
            "Ocp-Apim-Subscription-Key": self.key,
            "Content-Type": "application/json",
            "X-ClientTraceId": str(uuid.uuid4()),
        }
        if self.region:
            headers["Ocp-Apim-Subscription-Region"] = self.region
        try:
            async with httpx.AsyncClient(timeout=10, transport=self.transport) as client:
                res = await client.post(
                    f"{self.endpoint}/translate",
                    params={"api-version": "3.0", "from": "en", "to": to},
                    headers=headers,
                    json=[{"Text": t} for t in texts],
                )
            res.raise_for_status()
            return [item["translations"][0]["text"] for item in res.json()]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            log.warning("translation to %s failed: %s", to, exc)
            return None

    async def overlay(self, ov: Overlay, lang: str) -> Overlay | None:
        """The overlay with text in `lang` added (cached), or None if translation is unavailable."""
        if lang == "en" or all(lang in t for t in ov.text.values()):
            return ov
        hit = self.cache.get((ov.overlay_id, lang))
        if hit is not None:
            return hit
        personas = [p for p in (Persona.ANALYST, Persona.FAN) if "en" in ov.text.get(p, {})]
        out = await self.translate([ov.text[p]["en"] for p in personas], lang)
        if out is None:
            return None
        text = {p: dict(v) for p, v in ov.text.items()}
        for p, t in zip(personas, out, strict=True):
            text[p][lang] = t
        done = ov.model_copy(update={"text": text})
        self.cache[(ov.overlay_id, lang)] = done
        return done
