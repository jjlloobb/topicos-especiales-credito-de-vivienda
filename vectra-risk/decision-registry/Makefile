# Comandos de U3 `decision-registry`. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
# Las politicas de U1 que se evaluan sin firmas ni consultas a la API (las mismas que `STATIC_POLICIES` de platform/Makefile).
STATIC_POLICIES := disallow-latest.yaml require-run-as-non-root.yaml disallow-privileged.yaml disallow-host-path.yaml require-ro-rootfs.yaml require-resources.yaml require-priority-class.yaml require-criticality-label.yaml disallow-plain-secrets.yaml disallow-rbac-wildcards.yaml restrict-loadbalancer.yaml restrict-registries.yaml
# `pass: 0` no aprueba: ninguna regla vio un recurso.
KYVERNO_OK := pass: [1-9][0-9]*, fail: 0, warn: 0, error: 0

.PHONY: lint test check policy-chart policy-chart-u1 render-chart coverage image
TOOLS := $(ROOT)/platform/.tools/bin
CHART := $(ROOT)/decision-registry/chart

lint:
	$(UV) ruff check decision-registry
	cd $(ROOT) && MYPYPATH=decision-registry/src uv run mypy --strict decision-registry/src
	$(UV) lint-imports --config decision-registry/.importlinter

# NFR-U3-51: las propiedades (Hypothesis) corren con el perfil `ci` (500 ejemplos, semilla impresa).
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

# Las politicas de U1 (Kyverno y rego) sobre el render de cada entorno, con los values que usa Argo CD (`components.yaml`).
# `platform check-chart` rinde los tres entornos en un mismo directorio y Kyverno aborta con recursos repetidos (`panic`): aqui se rinde
# un entorno por directorio.
ENVS := kind staging prod
U1 := $(ROOT)/platform/.tools/integration/u3

policy-chart-u1:
	cd $(ROOT) && rm -rf $(U1) && mkdir -p $(U1)
	for env in $(ENVS); do \
		mkdir -p $(U1)/$$env/policies && \
		cd $(ROOT) && uv run python platform/tests/integration.py --chart decision-registry/chart --namespace vectra-app --env $$env --out $(U1)/$$env/resources && \
		cd $(ROOT)/platform/policies/kyverno && cp $(STATIC_POLICIES) $(U1)/$$env/policies/ && \
		{ $(TOOLS)/kyverno apply $(U1)/$$env/policies --resource $(U1)/$$env/resources > $(U1)/$$env/report.txt 2>&1 || true; } && \
		{ grep -E '$(KYVERNO_OK)' $(U1)/$$env/report.txt || { grep -E 'fail:|FAIL|error|panic' $(U1)/$$env/report.txt | head -40; exit 1; }; } && \
		$(TOOLS)/conftest test --policy $(ROOT)/platform/policies/rego $(U1)/$$env/resources && \
		$(TOOLS)/conftest test --combine --namespace hpa --policy $(ROOT)/platform/policies/rego $(U1)/$$env/resources || exit 1; \
	done

# Cobertura de ramas (NFR-U3-52): >= 95 % en `vectra_registry` y 100 % en `chain`, `verify` y `append`. El `--cov` sin argumento mide el
# `source` de la raiz (solo U0), por eso se nombra el paquete. Mismo patron que reference-model/Makefile.
coverage:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests -q --cov=vectra_registry --cov-branch --cov-fail-under=95
	cd $(ROOT) && uv run coverage report --include="*/vectra_registry/chain.py,*/vectra_registry/verify.py,*/vectra_registry/append.py" --fail-under=100

# Imagen local de `decision-registry` (agregado al Paso 13). Contexto: la raiz de vectra-risk/. El `docker push` a `kind-registry` y el
# digest real en los values de kind los hace el operador en el Bloque H (AUTONOMIA-01): decision-registry/docs/imagen-kind.md.
image:
	cd $(ROOT) && docker build -t localhost:5001/vectra/decision-registry:dev -f decision-registry/Dockerfile .

# Verificaciones estaticas (AUTONOMIA-01). `coverage` corre las pruebas de `test` con la medicion (NFR-U3-52); la trazabilidad usa la lista
# «Diferido por la demo» de evidence/cierre-demo.md. Crece con los pasos del plan.
check: lint coverage policy-chart policy-chart-u1
	cd $(ROOT) && uv run python platform/tests/test_traceability.py --unit decision-registry --all
