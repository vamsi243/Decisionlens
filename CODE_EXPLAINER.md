# Code explainer

## Folder tour
| Folder | What lives there |
| --- | --- |
| `contracts/` | Pydantic models â€” the one definition of every record |
| `generator/` | Seeded match simulator |
| `engine/` | Every number: metrics, fatigue, probabilities |
| `service/` | FastAPI app, stream pipeline, adapters |
| `mcp_server/` | Engine functions exposed as MCP tools |
| `agents/` | Router, orchestrator and the five agents |
| `web/` | React tactics board |
| `tasks.py` | Cross-platform task runner used by the Makefile |

## Contracts in practice
- `contracts/base.py` — `Point`, `Probability`, `ProbRange` (median + 10th-90th percentile, must be ordered), pitch constants.
- Every model forbids unknown fields, so a typo in a producer fails loudly instead of silently dropping data.
- `contracts/export.py` writes one schema per record plus a `contracts.json` bundle; `web/scripts/gen-types.mjs` turns the bundle into TS.
- `tests/factories.py` holds one valid example of every record; `tests/test_contracts.py` round-trips each and checks the validation rules.

## How one frame travels
_TODO_

## How one key moment becomes a card
_TODO_

## The probability maths
_TODO (Phase 3)_

## Extending
_TODO_

## Testing approach
_TODO_
