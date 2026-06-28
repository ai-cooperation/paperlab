# Engine test harness (ENGINE_BUILD_PLAN.md Phase 0).
# `make test` runs Python (a-side); `make test-ts` runs the b-side Worker
# (vitest) once it exists (Phase 8); `make cov` prints the coverage report.
#
# PY defaults to the project .venv (numpy/matplotlib/fastapi/pytest live there);
# override on the CLI:  make test PY=python3
PY ?= /Users/user/projects/ai-paper-workshop/.venv/bin/python3.9
PYTEST := $(PY) -m pytest

.PHONY: help test cov test-fast test-ts test-all

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

test: ## a-side python tests
	$(PYTEST) tests/ -p no:cacheprovider

test-fast: ## a-side tests minus the slow (real-ML / network-shaped) lane
	$(PYTEST) tests/ -p no:cacheprovider -m "not slow"

cov: ## a-side tests with coverage report (framework + gates are the value)
	$(PYTEST) tests/ -p no:cacheprovider --cov=. --cov-config=.coveragerc

test-ts: ## b-side Worker tests (vitest + Miniflare) — wired in Phase 8
	@echo "[test-ts] no b-side worker in this tree yet (ENGINE_BUILD_PLAN Phase 8); skipping"

test-all: test test-ts ## full suite (python + b-side)
