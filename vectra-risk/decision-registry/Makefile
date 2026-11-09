# Comandos de U3 `decision-registry`. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
# Las politicas de U1 que se evaluan sin firmas ni consultas a la API (las mismas que `STATIC_POLICIES` de platform/Makefile).
STATIC_POLICIES := disallow-latest.yaml require-run-as-non-root.yaml disallow-privileged.yaml disallow-host-path.yaml require-ro-rootfs.yaml require-resources.yaml require-priority-class.yaml require-criticality-label.yaml disallow-plain-secrets.yaml disallow-rbac-wildcards.yaml restrict-loadbalancer.yaml restrict-registries.yaml
# `pass: 0` no aprueba: ninguna regla vio un recurso.
KYVERNO_OK := pass: [1-9][0-9]*, fail: 0, warn: 0, error: 0

.PHONY: lint test check policy-chart policy-chart-u1 render-chart
TOOLS := $(ROOT)/platform/.tools/bin
CHART := $(ROOT)/decision-registry/chart

lint:
	$(UV) ruff check decision-registry
	cd $(ROOT) && MYPYPATH=decision-registry/src uv run mypy --strict decision-registry/src
	$(UV) lint-imports --config decision-registry/.importlinter

# Las pruebas de integracion levantan PostgreSQL con Testcontainers (Docker local, sin cluster; AUTONOMIA-01).
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests -q

# El chart minimo de U3 (Paso 12 acotado a la demo): `helm template` + `conftest` (limites de tiempo, `Forbid`, sidecar nativo, sin
# Secret plano). Las reglas estan en `chart/policy/`; `test_chart.py` tiene un caso que falla por cada una. Necesita platform/install-tools.sh.
render-chart:
	$(TOOLS)/helm template decision-registry $(CHART)

policy-chart:
	$(TOOLS)/helm template decision-registry $(CHART) | $(TOOLS)/conftest test --policy $(CHART)/policy -
	$(TOOLS)/helm template decision-registry $(CHART) | $(TOOLS)/conftest test --combine --namespace chart_set --policy $(CHART)/policy -

# Las politicas de U1 (Kyverno y rego) sobre el render de kind. `platform check-chart` rinde los tres entornos en un mismo directorio y
# Kyverno aborta con recursos repetidos; aqui se rinde uno solo.
policy-chart-u1:
	cd $(ROOT) && rm -rf platform/.tools/integration/u3 && mkdir -p platform/.tools/integration/u3/policies
	cd $(ROOT) && uv run python platform/tests/integration.py --chart decision-registry/chart --namespace vectra-app --env kind --out platform/.tools/integration/u3/resources
	cd $(ROOT)/platform/policies/kyverno && cp $(STATIC_POLICIES) $(ROOT)/platform/.tools/integration/u3/policies/
	$(TOOLS)/kyverno apply $(ROOT)/platform/.tools/integration/u3/policies --resource $(ROOT)/platform/.tools/integration/u3/resources > $(ROOT)/platform/.tools/integration/u3/report.txt 2>&1 || true
	grep -E '$(KYVERNO_OK)' $(ROOT)/platform/.tools/integration/u3/report.txt || { grep -E 'fail:|FAIL|error|panic' $(ROOT)/platform/.tools/integration/u3/report.txt | head -40; exit 1; }
	$(TOOLS)/conftest test --policy $(ROOT)/platform/policies/rego $(ROOT)/platform/.tools/integration/u3/resources
	$(TOOLS)/conftest test --combine --namespace hpa --policy $(ROOT)/platform/policies/rego $(ROOT)/platform/.tools/integration/u3/resources

# Verificaciones estaticas (AUTONOMIA-01). Crece con los pasos del plan.
check: lint test policy-chart policy-chart-u1
