# Decision Lens stream service (FastAPI + engine), replaying the committed sample match.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.13.3 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY contracts ./contracts
COPY engine ./engine
COPY generator ./generator
COPY service ./service
COPY mcp_server ./mcp_server
COPY agents ./agents
COPY data/samples/match_42 ./data/samples/match_42

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

ENV RUN_MODE=local \
    MATCH_DIR=data/samples/match_42 \
    REPLAY_AUTOPLAY=true \
    PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "/app/.venv/bin/uvicorn service.main:app --host 0.0.0.0 --port ${PORT}"]
