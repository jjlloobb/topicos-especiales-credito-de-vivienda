# Nota de voz del revisor humano. Se ejecuta desde cualquier sitio; corre en la raiz del workspace `vectra-risk/`. Ninguna orden graba, descarga ni publica.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
UV := cd $(ROOT) && uv run

.PHONY: lint types test check

lint:
	$(UV) ruff check loop/nota-de-voz
	$(UV) ruff format --check loop/nota-de-voz

types:
	$(UV) mypy loop/nota-de-voz/src/vectra_nota_de_voz

# Sin microfono, sin red y sin GitHub: grabador, transcriptor y `gh` son dobles. La prueba `manual` (modelo real) se omite.
# La misma orden que la CI (`.github/workflows/tests.yml`, con `path: loop/nota-de-voz`), mas la cobertura.
test:
	cd $(ROOT) && uv run pytest loop/nota-de-voz --rootdir=loop/nota-de-voz --import-mode=importlib -p no:cacheprovider \
		--cov=vectra_nota_de_voz --cov-branch --cov-fail-under=90 --cov-report=term-missing

check: lint types test
