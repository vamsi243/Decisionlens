# Decision Lens

**Every moment, every option, every fan.** Live match intelligence on a fully synthetic football match: a sleek 2D tactics board, a transparent probability engine, and Azure OpenAI agents that explain what happened, what was possible and who could have done it.

> Built for the Microsoft Premier League "Inside the Game" hackathon. All data is synthetic — *Riverside FC* vs *Hillton United*, invented players.

## The problem
_TODO (Phase 9)_

## What it does
_TODO — see [FEATURES.md](FEATURES.md)._

## Microsoft and Azure tech
_TODO (Phase 8)_

## Quick start (local)

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 20+ (pnpm via `corepack`).

```bash
cp .env.example .env
uv sync
(cd web && corepack pnpm install)
uv run python tasks.py dev     # or: make dev
```

API on http://localhost:8000, web on http://localhost:5173.

| Task | Command |
| --- | --- |
| Tests | `uv run python tasks.py test` (`make test`) |
| Lint | `uv run python tasks.py lint` (`make lint`) |
| Generate a match | `uv run python tasks.py generate --seed 42` (`make generate SEED=42`) |
| Azure smoke test | `uv run python scripts/smoke_azure.py` |

## Azure deploy
_TODO (Phase 8): `azd up`._

## Environment variables
See [.env.example](.env.example).

## Synthetic-data statement
No real matches, players, clubs, badges or footage are used anywhere.

## Cost
Azure free tiers first, everything else on the $200 free credit. _Details in Phase 8._

## Third-party licences
_TODO (Phase 9)_ — all dependencies are MIT / Apache-2.0 / BSD / ISC; fonts (Inter, Geist, DM Mono) are SIL OFL.

## Licence
MIT — see [LICENSE](LICENSE).
