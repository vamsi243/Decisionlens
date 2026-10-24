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

BATCH = 100  # Translator v3 takes up to 1,000 texts a request; stay well inside
MAX_CACHED = 50_000


class Translator:
    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.transport = transport  # injectable for tests
        self.endpoint = settings.azure_translator_endpoint.rstrip("/")
        self.key = settings.azure_translator_key
        self.region = settings.azure_translator_region
        self.cache: dict[tuple[str, str], Overlay] = {}
        self.strings: dict[tuple[str, str], str] = {}  # (lang, English) -> translation

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

    async def texts(self, texts: list[str], lang: str) -> list[str] | None:
        """Engine and UI strings in `lang`, each translated once and then cached. Repeats (names,
        templates) cost nothing; new ones go to Translator in batches. None if unavailable."""
        if lang == "en":
            return list(texts)
        todo = list(dict.fromkeys(t for t in texts if t.strip() and (lang, t) not in self.strings))
        for i in range(0, len(todo), BATCH):
            chunk = todo[i : i + BATCH]
            out = await self.translate(chunk, lang)
            if out is None:
                return None
            if len(self.strings) > MAX_CACHED:  # a bounded cache: start again rather than grow
                self.strings.clear()
            self.strings.update({(lang, src): dst for src, dst in zip(chunk, out, strict=True)})
        return [self.strings.get((lang, t), t) for t in texts]

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
