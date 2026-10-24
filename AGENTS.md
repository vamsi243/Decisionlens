# AGENTS.md — working rules for Decision Lens

Read `docs/BUILD_PLAN.md` for the full spec. These rules apply to every session.

1. **One phase at a time.** Finish every task and acceptance check in a phase, then stop and summarise what changed before starting the next.
2. **Local first.** Build and run everything with `RUN_MODE=local`. Azure adapters come in Phase 8 only.
3. **Never invent numbers in the language model.** Every probability, stat and metric comes from the engine; agents only explain engine output.
4. **Verify fast-moving APIs before coding.** Check current official docs for Microsoft Agent Framework, the MCP Python SDK, Azure OpenAI and Azure AI Translator.
5. **No secrets in the repo.** Keys live in `.env` (gitignored); commit only `.env.example`.
6. **Tests and lint pass before every commit.** Small commits, conventional messages (`feat(engine): add aerial duel probability`).
7. **Keep docs current.** Update `README.md`, `FEATURES.md`, `ARCHITECTURE.md`, `CODE_EXPLAINER.md` at the end of each phase.
8. **Ask, don't guess,** when a decision changes scope, cost or the data contract.

## Constraints

- Synthetic data only: teams *Riverside FC* and *Hillton United*, invented player names. No real clubs, players, badges.
- $0 out of pocket: Azure free tiers + $200 credit only.
- LLM calls only at key moments, half-time and full-time — never per frame.
- No 3D. Permissive open-source licences only.

## Commands

`make` is optional; every target is also available through the cross-platform runner:

| Make | Runner (works on Windows without make) |
| --- | --- |
| `make dev` | `uv run python tasks.py dev` |
| `make test` | `uv run python tasks.py test` |
| `make lint` | `uv run python tasks.py lint` |
| `make generate SEED=42` | `uv run python tasks.py generate --seed 42` |
| `make replay` | `uv run python tasks.py replay` |
| `make schema` | `uv run python tasks.py schema` |

Web uses pnpm through corepack: run `corepack pnpm <cmd>` from inside `web/` (corepack reads its pinned version there).

## Layout

`contracts/` Pydantic models (source of truth) · `generator/` simulator · `engine/` all numbers ·
`service/` FastAPI stream · `mcp_server/` MCP tools · `agents/` router + agents · `web/` React app.
