PYTHON ?= python3

.PHONY: bootstrap dev demo test eval build demo-reset package models demo-container stop-container
bootstrap:
	$(PYTHON) scripts/dev.py bootstrap
dev:
	$(PYTHON) scripts/dev.py dev
demo:
	$(PYTHON) scripts/dev.py demo
build:
	$(PYTHON) scripts/dev.py build
test:
	$(PYTHON) scripts/dev.py test
eval:
	$(PYTHON) scripts/dev.py eval
demo-reset:
	$(PYTHON) scripts/demo_reset.py
package:
	$(PYTHON) scripts/package.py
models:
	$(PYTHON) scripts/download_models.py
demo-container:
	docker compose up --build --wait
stop-container:
	docker compose down
