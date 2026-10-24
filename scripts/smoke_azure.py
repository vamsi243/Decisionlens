"""Phase 0 smoke test: one Azure OpenAI (Foundry) call and one Translator call, using .env.

Run: uv run python scripts/smoke_azure.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import httpx
from openai import AzureOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.settings import get_settings


def smoke_model() -> bool:
    s = get_settings()
    if not (s.azure_openai_endpoint and s.azure_openai_api_key):
        print("[model] skipped: AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY not set")
        return False
    client = AzureOpenAI(
        azure_endpoint=s.azure_openai_endpoint,
        api_key=s.azure_openai_api_key,
        api_version=s.azure_openai_api_version,
    )
    for deployment in (s.azure_openai_deployment_mini, s.azure_openai_deployment_fallback):
        try:
            res = client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "user", "content": "Say 'Decision Lens ready' and nothing else."}
                ],
                reasoning_effort=s.azure_openai_reasoning_effort,  # type: ignore[arg-type]
                max_completion_tokens=200,
            )
        except Exception as exc:  # report and try the fallback deployment
            print(f"[model] {deployment} failed: {exc}")
            continue
        print(f"[model] {deployment}: {res.choices[0].message.content!r}")
        return True
    return False


def smoke_translator() -> bool:
    s = get_settings()
    if not s.azure_translator_key:
        print("[translator] skipped: AZURE_TRANSLATOR_KEY not set")
        return False
    headers = {
        "Ocp-Apim-Subscription-Key": s.azure_translator_key,
        "Content-Type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }
    if s.azure_translator_region:
        headers["Ocp-Apim-Subscription-Region"] = s.azure_translator_region
    res = httpx.post(
        f"{s.azure_translator_endpoint.rstrip('/')}/translate",
        params={"api-version": "3.0", "from": "en", "to": "es"},
        headers=headers,
        json=[{"Text": "Much more likely to win that header."}],
        timeout=15,
    )
    if res.status_code != 200:
        print(f"[translator] failed {res.status_code}: {res.text}")
        return False
    print(f"[translator] es: {res.json()[0]['translations'][0]['text']!r}")
    return True


if __name__ == "__main__":
    ok = [smoke_model(), smoke_translator()]
    raise SystemExit(0 if all(ok) else 1)
