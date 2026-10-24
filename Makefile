SEED ?= 42
RUN := uv run python tasks.py

.PHONY: dev test lint generate replay schema deploy

dev:
	$(RUN) dev

test:
	$(RUN) test

lint:
	$(RUN) lint

generate:
	$(RUN) generate --seed $(SEED)

replay:
	$(RUN) replay

schema:
	$(RUN) schema

deploy:
	azd up
