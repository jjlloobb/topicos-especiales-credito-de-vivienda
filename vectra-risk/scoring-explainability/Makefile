# Comandos de U7 `scoring-explainability`. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
# Las politicas de U1 que se evaluan sin firmas ni consultas a la API (las mismas que `STATIC_POLICIES` de platform/Makefile).
STATIC_POLICIES := disallow-latest.yaml require-run-as-non-root.yaml disallow-privileged.yaml disallow-host-path.yaml require-ro-rootfs.yaml require-resources.yaml require-priority-class.yaml require-criticality-label.yaml disallow-plain-secrets.yaml disallow-rbac-wildcards.yaml restrict-loadbalancer.yaml restrict-registries.yaml
# `pass: 0` no aprueba: ninguna regla vio un recurso.
KYVERNO_OK := pass: [1-9][0-9]*, fail: 0, warn: 0, error: 0
TOOLS := $(ROOT)/platform/.tools/bin
CHART := $(ROOT)/scoring-explainability/chart
CRDS := $(ROOT)/scoring-explainability/tests/fixtures/crds
POLICIES := $(ROOT)/scoring-explainability/policies/conftest
ENVS := kind staging prod
U1 := $(ROOT)/platform/.tools/integration/u7
SRC := scoring-explainability/scoring/src:scoring-explainability/explainability/src

.PHONY: lint test coverage check image-scoring image-explainability render-chart policy-chart policy-chart-u1 traceability quota-flows

# Contratos de import-linter (`.importlinter`): BR-U7-11 (factuality no importa narrative), P-U0-07 y NFR-U7-43 (sin httpx directo
# ni librerias de circuit breaking: el breaker es el de vectra_common.deps), NFR-U7-32 (sin clientes de LLM; narrativa de plantilla).
# NFR-U7-30 y P-U7-07 (sin salida al core ni a internet desde U7) los cubre tests/unit/test_no_core_client.py.
lint:
	$(UV) ruff check scoring-explainability
	$(UV) ruff format --check scoring-explainability
	cd $(ROOT) && MYPYPATH=$(SRC) uv run mypy --strict scoring-explainability/scoring/src scoring-explainability/explainability/src
	$(UV) lint-imports --config scoring-explainability/.importlinter

test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests -q -p no:cacheprovider --import-mode=importlib

# Cobertura de ramas (NFR-U7-40, 42): toda la suite (logica pura, ejemplos, integracion con dobles, PBT-U7-01..08 en el perfil `ci`, 500
# ejemplos) con >= 95 % en los dos servicios; despues el 100 % por modulo: `policy`, `narrative` y `factuality` (logica pura, Paso 7)
# y `orchestrator` (Paso 13). `--cov` sin argumento mediria el `source` de la raiz (U0), por eso se nombran los paquetes.
# `mutmut` sobre `policy` y `factuality` se difiere (T3, enmienda §2.3).
coverage:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests -q -p no:cacheprovider --import-mode=importlib --cov=scoring --cov=explainability --cov-branch --cov-fail-under=95
	cd $(ROOT) && uv run coverage report --include="*/scoring/*" --fail-under=95
	cd $(ROOT) && uv run coverage report --include="*/explainability/*" --fail-under=95
	cd $(ROOT) && uv run coverage report --include="*/scoring/policy.py,*/explainability/narrative.py,*/explainability/factuality.py" --fail-under=100
	cd $(ROOT) && uv run coverage report --include="*/scoring/orchestrator.py" --fail-under=100
	test -s $(ROOT)/aidlc-docs/construction/scoring-explainability/code/logic.md
	test -s $(ROOT)/aidlc-docs/construction/scoring-explainability/code/services.md

# Paso 14: una imagen por servicio, con el contexto en la raiz de vectra-risk/. El `docker push` a `kind-registry` y el digest real los hace el
# operador en la verificacion consolidada de U12 Paso 18 (enmienda §8): scoring-explainability/docs/imagenes.md.
image-scoring:
	cd $(ROOT) && docker build -t localhost:5001/vectra/scoring-service:dev -f scoring-explainability/scoring/Dockerfile .

image-explainability:
	cd $(ROOT) && docker build -t localhost:5001/vectra/explainability-service:dev -f scoring-explainability/explainability/Dockerfile .

# Paso 15: el render de cada entorno con los values que usa Argo CD (`components.yaml`: los del entorno y `values/<env>/scoring-explainability.yaml`),
# `kubeconform -strict` con los CRD de `ExternalSecret` y `ServiceMonitor` (tests/fixtures/crds/) y `conftest` de `policies/conftest/` (por
# documento y con todo el render junto). `tests/unit/test_chart.py` tiene un caso que falla por cada regla. Necesita platform/install-tools.sh y
# **falla** si falta una herramienta: no se salta con rc 0.
render-chart:
	cd $(ROOT) && $(TOOLS)/helm template scoring-explainability $(CHART) -f vectra-risk-gitops/envs/kind/values.yaml -f vectra-risk-gitops/values/kind/scoring-explainability.yaml

policy-chart:
	cd $(ROOT) && rm -rf $(U1)/render && mkdir -p $(U1)/render
	for env in $(ENVS); do \
		cd $(ROOT) && uv run python platform/tests/integration.py --chart scoring-explainability/chart --namespace vectra-app --env $$env --out $(U1)/render/$$env && \
		$(TOOLS)/kubeconform -strict -summary -schema-location default -schema-location '$(CRDS)/{{.ResourceKind}}.json' $(U1)/render/$$env/*.yaml && \
		$(TOOLS)/conftest test --policy $(POLICIES) $(U1)/render/$$env/*.yaml && \
		$(TOOLS)/conftest test --combine --namespace chart_set --policy $(POLICIES) $(U1)/render/$$env/*.yaml || exit 1; \
	done

# Las politicas de U1 (Kyverno y rego) sobre el render de cada entorno. `platform check-chart` rinde los tres entornos en un mismo directorio y
# Kyverno aborta con recursos repetidos (`panic`; candidata de U03-T04 y U04-T05): aqui se rinde un entorno por directorio.
policy-chart-u1:
	cd $(ROOT) && rm -rf $(U1)/u1 && mkdir -p $(U1)/u1
	for env in $(ENVS); do \
		mkdir -p $(U1)/u1/$$env/policies && \
		cd $(ROOT) && uv run python platform/tests/integration.py --chart scoring-explainability/chart --namespace vectra-app --env $$env --out $(U1)/u1/$$env/resources && \
		cd $(ROOT)/platform/policies/kyverno && cp $(STATIC_POLICIES) $(U1)/u1/$$env/policies/ && \
		{ $(TOOLS)/kyverno apply $(U1)/u1/$$env/policies --resource $(U1)/u1/$$env/resources > $(U1)/u1/$$env/report.txt 2>&1 || true; } && \
		{ grep -E '$(KYVERNO_OK)' $(U1)/u1/$$env/report.txt || { grep -E 'fail:|FAIL|error|panic' $(U1)/u1/$$env/report.txt | head -40; exit 1; }; } && \
		$(TOOLS)/conftest test --policy $(ROOT)/platform/policies/rego $(U1)/u1/$$env/resources && \
		$(TOOLS)/conftest test --combine --namespace hpa --policy $(ROOT)/platform/policies/rego $(U1)/u1/$$env/resources || exit 1; \
	done

# INF-U7-02 e INF-U7-05: la cuota de `vectra-app` (el plan dice `conftest test platform/policies/quotas/`; en el repositorio es `render.py --check` y la
# prueba de integracion de U1) y los flujos de U7 (sin flujos nuevos; X01 y X02 siguen prohibidos).
quota-flows:
	cd $(ROOT) && uv run python platform/policies/quotas/render.py --check
	cd $(ROOT) && uv run pytest "platform/tests/test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota" -q -p no:cacheprovider
	cd $(ROOT) && uv run python platform/network/generate.py --check
	cd $(ROOT) && for id in F12 F15 F18 F19 F20 F21 F22 F23 F103; do grep -q "id: $$id," platform/network/flows.yaml || { echo "falta $$id"; exit 1; }; done
	cd $(ROOT) && test "$$(grep -cE 'id: X0[12], from: (scoring|explainability)-service' platform/network/forbidden.yaml)" = 4

# La trazabilidad usa la lista «Diferido por la demo» de `evidence/cierre-demo.md` (P-4).
traceability:
	cd $(ROOT) && uv run python platform/tests/test_traceability.py --unit scoring-explainability --all

# Paso 20 (cierre acotado a la demo): estaticas y pruebas de los Pasos 1 a 15 y 17 que entran (`coverage` corre las de `test` con la medicion, incluido
# `tests/unit/test_chart.py`), el chart, la admision de U1, la cuota con los flujos y la trazabilidad (`evidence/cierre-demo.md`). Nada toca un cluster
# (AUTONOMIA-01). El Paso 16 (alertas, T2), la carga con k6 (T3), la firma y el SBOM (T1) y el Paso 18 (U12) estan diferidos.
check: lint coverage policy-chart policy-chart-u1 quota-flows traceability
