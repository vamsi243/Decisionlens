"""Response cache: never pay twice for the same card.

Keyed by match, moment (or recap), persona, model and prompt version. Kept in memory and
mirrored to a small JSON file, so restarting the replay does not repeat model calls.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("decision_lens.agents")


class ResponseCache:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.data: dict[str, str] = {}
        if path and path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                log.warning("ignoring unreadable cache %s", path)

    @staticmethod
    def key(*parts: object) -> str:
        return "|".join(str(p) for p in parts)

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def put(self, key: str, text: str) -> None:
        self.data[key] = text
        if self.path:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(
                    json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8"
                )
            except OSError:
                log.warning("could not write cache %s", self.path)
