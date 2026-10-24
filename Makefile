SEED ?= 42
RUN := uv run python tasks.py

.PHONY: dev test lint generate replay schema calibrate deploy

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

calibrate:
	$(RUN) calibrate

deploy:
	azd up
