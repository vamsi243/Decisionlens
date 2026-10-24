"""Translate the board's fixed UI wording into every menu language, once.

Finds every `t("…")` and `msg("…")` literal in web/src, asks Azure AI Translator for the ones
a locale file doesn't have yet, and writes web/src/i18n/<lang>.json (sorted, English keys).
Placeholders such as `{km}` are protected from translation; an entry that loses one is
dropped, so the board falls back to English for it. Strings no longer in the code are removed.
scripts/i18n_glossary.json holds hand-checked wording that always wins over the translator.

Run after adding UI text:  uv run python scripts/i18n_strings.py
Needs AZURE_TRANSLATOR_KEY (and region) in .env.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from service.settings import get_settings  # noqa: E402

SRC = ROOT / "web" / "src"
OUT = SRC / "i18n"
GLOSSARY = ROOT / "scripts" / "i18n_glossary.json"
LANGS = ["es", "fr", "pt", "de", "hi"]
CALL = re.compile(r"""\b(?:t|msg)\(\s*"((?:[^"\\]|\\.)+)"\s*[,)]""")
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def strings() -> list[str]:
    found: set[str] = set()
    for f in [*SRC.rglob("*.tsx"), *SRC.rglob("*.ts")]:
        if "types" in f.parts:
            continue
        for m in CALL.finditer(f.read_text(encoding="utf-8")):
            found.add(json.loads(f'"{m.group(1)}"'))  # unescape \" and friends
    return sorted(found)


def protect(s: str) -> str:
    esc = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return PLACEHOLDER.sub(lambda m: f'<span class="notranslate">{{{m.group(1)}}}</span>', esc)


def unprotect(s: str) -> str:
    s = re.sub(r'<span class="notranslate">\s*(\{\w+\})\s*</span>', r"\1", s)
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def translate(texts: list[str], lang: str) -> list[str]:
    st = get_settings()
    if not st.azure_translator_key:
        sys.exit("AZURE_TRANSLATOR_KEY is not set in .env")
    headers = {
        "Ocp-Apim-Subscription-Key": st.azure_translator_key,
        "Content-Type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }
    if st.azure_translator_region:
        headers["Ocp-Apim-Subscription-Region"] = st.azure_translator_region
    out: list[str] = []
    for i in range(0, len(texts), 100):
        chunk = texts[i : i + 100]
        res = httpx.post(
            f"{st.azure_translator_endpoint.rstrip('/')}/translate",
            params={"api-version": "3.0", "from": "en", "to": lang, "textType": "html"},
            headers=headers,
            json=[{"Text": protect(t)} for t in chunk],
            timeout=30,
        )
        res.raise_for_status()
        out += [unprotect(r["translations"][0]["text"]) for r in res.json()]
    return out


def main() -> None:
    src = strings()
    print(f"{len(src)} UI strings in web/src")
    glossary = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    for lang in LANGS:
        path = OUT / f"{lang}.json"
        have: dict[str, str] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        fixed: dict[str, str] = glossary.get(lang, {})
        stale = sorted(set(fixed) - set(src))
        if stale:
            print(f"{lang}: glossary entries no longer in the code: {stale}")
        todo = [s for s in src if s not in have and s not in fixed]
        got = dict(zip(todo, translate(todo, lang), strict=True)) if todo else {}
        merged = {s: (fixed.get(s) or have.get(s) or got.get(s, "")) for s in src}
        lost = [
            s
            for s, v in merged.items()
            if set(PLACEHOLDER.findall(s)) != set(PLACEHOLDER.findall(v))
        ]
        for s in lost:
            del merged[s]
        path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(
            f"{lang}: {len(todo)} new, {len(merged)} total, {len(lost)} dropped (placeholder lost)"
        )


if __name__ == "__main__":
    main()
