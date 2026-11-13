# Comandos de U8 `case-management`. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

# Las politicas de U1 que se evaluan sin firmas ni consultas a la API (las mismas que `STATIC_POLICIES` de platform/Makefile).
STATIC_POLICIES := disallow-latest.yaml require-run-as-non-root.yaml disallow-privileged.yaml disallow-host-path.yaml require-ro-rootfs.yaml require-resources.yaml require-priority-class.yaml require-criticality-label.yaml disallow-plain-secrets.yaml disallow-rbac-wildcards.yaml restrict-loadbalancer.yaml restrict-registries.yaml
# `pass: 0` no aprueba: ninguna regla vio un recurso.
KYVERNO_OK := pass: [1-9][0-9]*, fail: 0, warn: 0, error: 0
TOOLS := $(ROOT)/platform/.tools/bin
# `integration.py` llama a `helm` por el PATH: la version fijada de install-tools.sh.
export PATH := $(TOOLS):$(PATH)
CRDS := $(ROOT)/case-management/tests/fixtures/crds
POLICIES := $(ROOT)/case-management/policies/conftest
ENVS := kind staging prod
# Los renders van a platform/.tools/integration/u8 (no a /tmp, que es un tmpfs casi lleno). `promtool` escribe en TMPDIR: se le da uno dentro del repositorio.
U1 := $(ROOT)/platform/.tools/integration/u8
PROMTOOL_TMP := $(ROOT)/platform/.tools/tmp

.PHONY: lint test check image image-mock test-image policy-chart policy-chart-u1 quota-flows rules runbooks openapi links traceability

lint:
	$(UV) ruff check case-management
	$(UV) ruff format --check case-management
	cd $(ROOT) && MYPYPATH=case-management/src:case-management/core_banking_mock/src uv run mypy --strict case-management/src case-management/core_banking_mock/src
	$(UV) lint-imports --config case-management/.importlinter

# Las pruebas de migraciones levantan PostgreSQL con Testcontainers (Docker local, sin cluster; AUTONOMIA-01).
# Paso 18 (U08-T04, NFR-U8-50): ramas >= 95 % en `vectra_case` y 100 % en los ocho modulos que entran (`retention` sin umbral: diferido por la
# demo; `mutmut` diferido, T3). `case-management/pytest.ini` apunta la cobertura a `vectra_case` y no a la de U0.
COV_100 := --include='*/vectra_case/case_fsm.py,*/vectra_case/backoff.py,*/vectra_case/decision.py,*/vectra_case/views.py,*/vectra_case/intake.py,*/vectra_case/evidence.py,*/vectra_case/evaluation.py,*/vectra_case/sweeps.py'
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests case-management/core_banking_mock/tests --ignore=case-management/tests/integration/test_image.py -q -p no:cacheprovider --rootdir=case-management --cov=vectra_case --cov-branch --cov-fail-under=95
	cd $(ROOT) && uv run coverage report --rcfile=case-management/coveragerc --fail-under=100 $(COV_100)


# Paso 19: dos imagenes, con el contexto en la raiz de vectra-risk/. El `docker push` a `kind-registry` y el digest real los hace el operador en la
# verificacion consolidada de U12 Paso 18 (enmienda 8): case-management/docs/imagenes.md. `check` construye las dos ANTES de `test_image.py`.
image:
	cd $(ROOT) && docker build -t localhost:5001/vectra/case-management:dev -f case-management/Dockerfile .

image-mock:
	cd $(ROOT) && docker build -t localhost:5001/vectra/core-banking-mock:dev -f case-management/core_banking_mock/Dockerfile .

# Paso 19/20 (CA-4): los cuatro contenedores reales arrancan con lo que pone el chart. Necesita las dos imagenes (`image` e `image-mock`): `check` las construye antes. Si Docker
# no esta, la prueba FALLA (no se salta).
test-image:
	cd $(ROOT) && uv run pytest case-management/tests/integration/test_image.py -v -p no:cacheprovider --rootdir=case-management --no-cov

# Paso 20 (CA-2, CA-3, CA-7): el render de cada entorno con los values que usa Argo CD (`components.yaml`: los del entorno, `values-kind.yaml` en kind y
# `values/<env>/case-management.yaml`), `kubeconform -strict` con los CRD de `ExternalSecret`, `ServiceMonitor` y `PrometheusRule` (tests/fixtures/crds/), `conftest` de
# `policies/conftest/` (por documento y con todo el render junto), la misma pasada con el Job rt5-demo y las reglas sobre los ARCHIVOS de values de staging y produccion.
# `tests/unit/test_chart.py` tiene un caso que falla por cada regla. Necesita platform/install-tools.sh y **falla** si falta una herramienta: no se salta con rc 0.
policy-chart:
	cd $(ROOT) && rm -rf $(U1)/render $(U1)/rt5 && mkdir -p $(U1)/render $(U1)/rt5
	for env in $(ENVS); do \
		cd $(ROOT) && uv run python platform/tests/integration.py --chart case-management/chart --namespace vectra-app --env $$env --out $(U1)/render/$$env && \
		$(TOOLS)/kubeconform -strict -summary -schema-location default -schema-location '$(CRDS)/{{.ResourceKind}}.json' $(U1)/render/$$env/*.yaml && \
		$(TOOLS)/conftest test --policy $(POLICIES) $(U1)/render/$$env/*.yaml && \
		$(TOOLS)/conftest test --combine --namespace chart_set --policy $(POLICIES) $(U1)/render/$$env/*.yaml || exit 1; \
	done
	cd $(ROOT) && $(TOOLS)/helm template case-management case-management/chart -n vectra-app -f vectra-risk-gitops/envs/kind/values.yaml -f case-management/chart/values-kind.yaml -f vectra-risk-gitops/values/kind/case-management.yaml --set probes.runId=20261112-0900 > $(U1)/rt5/kind.yaml
	cd $(ROOT) && test "$$(grep -c 'name: rt5-demo-20261112-0900' $(U1)/rt5/kind.yaml)" = 1 && ! grep -n ttlSecondsAfterFinished $(U1)/rt5/kind.yaml
	cd $(ROOT) && $(TOOLS)/conftest test --policy $(POLICIES) $(U1)/rt5/kind.yaml && $(TOOLS)/conftest test --combine --namespace chart_set --policy $(POLICIES) $(U1)/rt5/kind.yaml
	cd $(ROOT) && ! $(TOOLS)/helm template case-management case-management/chart -n vectra-app -f vectra-risk-gitops/envs/kind/values.yaml -f case-management/chart/values-kind.yaml --set probes.runId=manual > /dev/null 2>&1
	cd $(ROOT) && for env in kind staging prod; do test -s vectra-risk-gitops/values/$$env/case-management.yaml || { echo "falta $$env"; exit 1; }; done
	cd $(ROOT) && $(TOOLS)/conftest test --policy $(POLICIES) --namespace values.prod vectra-risk-gitops/values/prod/case-management.yaml
	cd $(ROOT) && $(TOOLS)/conftest test --policy $(POLICIES) --namespace values.staging vectra-risk-gitops/values/staging/case-management.yaml
	cd $(ROOT) && ! grep -rn "runId" vectra-risk-gitops/values/*/case-management.yaml case-management/chart/values.yaml case-management/chart/values-kind.yaml
	cd $(ROOT) && ! grep -rnE "schedule|timeZone" case-management/chart/values.yaml

# Las politicas de U1 (Kyverno y rego) sobre el render de cada entorno. `platform check-chart` rinde los tres entornos en un mismo directorio y Kyverno aborta con
# recursos repetidos (`panic`; C-6) y ademas borra `platform/.tools/integration/chart`: aqui se rinde un entorno por directorio.
policy-chart-u1:
	cd $(ROOT) && rm -rf $(U1)/u1 && mkdir -p $(U1)/u1
	for env in $(ENVS); do \
		mkdir -p $(U1)/u1/$$env/policies && \
		cd $(ROOT) && uv run python platform/tests/integration.py --chart case-management/chart --namespace vectra-app --env $$env --out $(U1)/u1/$$env/resources && \
		cd $(ROOT)/platform/policies/kyverno && cp $(STATIC_POLICIES) $(U1)/u1/$$env/policies/ && \
		{ $(TOOLS)/kyverno apply $(U1)/u1/$$env/policies --resource $(U1)/u1/$$env/resources > $(U1)/u1/$$env/report.txt 2>&1 || true; } && \
		{ grep -E '$(KYVERNO_OK)' $(U1)/u1/$$env/report.txt || { grep -E 'fail:|FAIL|error|panic' $(U1)/u1/$$env/report.txt | head -40; exit 1; }; } && \
		$(TOOLS)/conftest test --policy $(ROOT)/platform/policies/rego $(U1)/u1/$$env/resources && \
		$(TOOLS)/conftest test --combine --namespace hpa --policy $(ROOT)/platform/policies/rego $(U1)/u1/$$env/resources || exit 1; \
	done
	cd $(ROOT) && $(TOOLS)/kyverno test platform/policies/kyverno
	cd $(ROOT) && ! grep -rn "PolicyException" platform/policies case-management/chart
	cd $(ROOT) && ! grep -nE "case-service|case-worker|core-banking-mock" platform/policies/kyverno/require-spread-and-pdb.yaml

# INF-U8-05 y los flujos de U8: la cuota de `vectra-app` y `vectra-mock` (el plan dice `conftest test platform/policies/quotas/`; en el repositorio es `render.py --check` y la
# prueba de integracion de U1), los flujos del plan (sin flujos nuevos; X01 sigue prohibido) y las pruebas de `test_chart.py` que los atan al render.
quota-flows:
	cd $(ROOT) && uv run python platform/policies/quotas/render.py --check
	cd $(ROOT) && uv run pytest "platform/tests/test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota" -q -p no:cacheprovider
	cd $(ROOT) && uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -q -p no:cacheprovider
	cd $(ROOT) && for id in F04 F07 F10 F15 F16 F17 F40 F44 F50 F60 F104 F105; do grep -q "id: $$id," platform/network/flows.yaml || { echo "falta $$id"; exit 1; }; done
	cd $(ROOT) && grep -qE "id: F15, from: \[case-worker\], to: \[scoring-service\], port: 8080" platform/network/flows.yaml && grep -qE "id: F40, from: \[case-service, case-worker\]" platform/network/flows.yaml && grep -qE "id: F104, from: \[case-worker, case-service\]" platform/network/flows.yaml
	cd $(ROOT) && test "$$(grep -cE 'id: X01, from: (scoring-service|explainability-service), to: core-banking-mock' platform/network/forbidden.yaml)" = 2
	cd $(ROOT) && grep -q "_catch_all: core-mock-catch-all" platform/network/flows.yaml
	cd $(ROOT) && grep -q "U8: { requests: \[6.44, 5.3\], limits: \[29.9, 12.35\] }" platform/policies/quotas/quotas.yaml && grep -q "U8: { requests: \[0.59, 0.32\], limits: \[2.93, 0.98\] }" platform/policies/quotas/quotas.yaml

# Paso 21: `CoreWriteAttempt`. El archivo versionado es el `spec` de la PrometheusRule renderizada: se compara con el render de kind y de staging (WRITE=1 lo regenera), y
# `promtool` lo revisa y corre los casos de `rules/tests/`. **Falla** si falta `promtool` (no se omite, a diferencia del `rules` de governance; F-02 de U04-T07).
rules:
	cd $(ROOT) && rm -rf $(U1)/rules && mkdir -p $(U1)/rules $(PROMTOOL_TMP)
	for env in kind staging; do \
		cd $(ROOT) && uv run python platform/tests/integration.py --chart case-management/chart --namespace vectra-app --env $$env --out $(U1)/rules/$$env || exit 1; \
	done
	cd $(ROOT) && uv run python case-management/tools/rules_spec.py $(U1)/rules/kind/case-management-kind.yaml $(U1)/rules/staging/case-management-staging.yaml $(if $(WRITE),--write,)
	cd $(ROOT) && test -x $(TOOLS)/promtool && $(TOOLS)/promtool check rules case-management/observability/rules/case-management.rules.yaml
	cd $(ROOT) && TMPDIR=$(PROMTOOL_TMP) $(TOOLS)/promtool test rules case-management/observability/rules/tests/*.yaml

runbooks:
	cd $(ROOT) && uv run python platform/tests/test_runbooks.py --root case-management
	cd $(ROOT) && uv run python contracts/tools/forbidden_phrases.py case-management/observability/runbooks/*.md case-management/docs/*.md

# Paso 22: el OpenAPI exportado coincide con el de la app y con el contrato de U0 (`check_openapi.py --write` lo regenera).
openapi:
	cd $(ROOT) && uv run python case-management/tools/check_openapi.py

links:
	cd $(ROOT) && uv run python platform/tests/test_links.py --root case-management

# La trazabilidad usa la lista «Diferido por la demo» de `evidence/cierre-demo.md` (P-4 de la enmienda).
traceability:
	cd $(ROOT) && uv run python platform/tests/test_traceability.py --unit case-management --all

# Paso 26 (cierre acotado a la demo): estaticas, pruebas con el perfil `ci` y la cobertura de los Pasos 1 a 18 (`test` incluye `tests/unit/test_chart.py`, `test_rules.py` y `test_openapi.py`),
# las dos imagenes y la prueba de los contenedores, el chart, la admision de U1, la cuota con los flujos, `CoreWriteAttempt`, los runbooks, el OpenAPI, los enlaces y la trazabilidad
# (`evidence/cierre-demo.md`). Nada toca un cluster (AUTONOMIA-01). El Paso 16 (CLI de retencion), el 24 (kind; U12 Paso 18), k6, firma y SBOM estan diferidos.
check: lint test image image-mock test-image policy-chart policy-chart-u1 quota-flows rules runbooks openapi links traceability
