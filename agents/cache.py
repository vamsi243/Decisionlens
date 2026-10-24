"""Response cache: never pay twice for the same card.

Keyed by match, moment (or recap), agent, model and prompt version. Kept in memory and mirrored
either to a small JSON file (local) or, through `sink`, to Cosmos DB (Azure), so restarting the
replay or waking a scaled-to-zero container does not repeat model calls.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger("decision_lens.agents")


class ResponseCache:
    def __init__(
        self,
        path: Path | None,
        *,
        initial: dict[str, str] | None = None,
        sink: Callable[[str, str], None] | None = None,
    ) -> None:
        self.path = path
        self.sink = sink
        self.data: dict[str, str] = dict(initial or {})
        if path and path.exists():
            try:
                self.data.update(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                log.warning("ignoring unreadable cache %s", path)

    @staticmethod
    def key(*parts: object) -> str:
        return "|".join(str(p) for p in parts)

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def put(self, key: str, text: str) -> None:
        self.data[key] = text
        if self.sink is not None:
            self.sink(key, text)
        if self.path:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(
                    json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8"
                )
            except OSError:
                log.warning("could not write cache %s", self.path)
