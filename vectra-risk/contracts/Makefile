# Comandos de U0. Se ejecutan desde la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

.PHONY: openapi ts bench lint test check

openapi:
	$(UV) python contracts/tools/codegen.py

ts: openapi
	cd $(ROOT) && npm run -w contracts/ts generate

lint:
	$(UV) ruff check contracts
	$(UV) mypy --strict contracts/python
	$(UV) lint-imports --config contracts/.importlinter

test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest contracts/tests -q

bench:
	$(UV) pytest contracts/tests/bench -m benchmark --benchmark-json=benchmark.json
	$(UV) python contracts/tools/bench_gate.py benchmark.json

check: lint
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest contracts/tests -q --cov --cov-branch --cov-fail-under=95
	$(UV) python contracts/tools/coverage_gate.py
	$(UV) python contracts/tools/traceability.py --all
	$(MAKE) -C $(ROOT)/contracts bench
	$(MAKE) -C $(ROOT)/contracts openapi
	cd $(ROOT) && npm run -w contracts/ts generate
	cd $(ROOT) && git diff --exit-code contracts/openapi/ contracts/ts/src/generated/ contracts/ts/src/enums.generated.ts
	cd $(ROOT) && npm run -w contracts/ts typecheck && npm run -w contracts/ts lint && npm run -w contracts/ts test
	test ! -d $(ROOT)/contracts/python/vectra_contracts/src/vectra_contracts/repository
	test ! -d $(ROOT)/contracts/chart && test ! -f $(ROOT)/contracts/Dockerfile
