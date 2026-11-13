# Comandos de U11 (product-metrics). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

# Las politicas de U1 que se evaluan sin firmas ni consultas a la API (las mismas que `STATIC_POLICIES` de platform/Makefile).
STATIC_POLICIES := disallow-latest.yaml require-run-as-non-root.yaml disallow-privileged.yaml disallow-host-path.yaml require-ro-rootfs.yaml require-resources.yaml require-priority-class.yaml require-criticality-label.yaml disallow-plain-secrets.yaml disallow-rbac-wildcards.yaml restrict-loadbalancer.yaml restrict-registries.yaml
# `pass: 0` no aprueba: ninguna regla vio un recurso.
KYVERNO_OK := pass: [1-9][0-9]*, fail: 0, warn: 0, error: 0
TOOLS := $(ROOT)/platform/.tools/bin
CRDS := $(ROOT)/product-metrics/tests/fixtures/crds
POLICIES := $(ROOT)/product-metrics/policies/conftest
ENVS := kind staging prod
U1 := $(ROOT)/platform/.tools/integration/u11
APPS := $(foreach e,$(ENVS),$(ROOT)/vectra-risk-gitops/apps/$(e)/product-metrics.yaml)

.PHONY: lint types imports test coverage gen-rules rules image image-test policy-chart policy-chart-u1 quota-flows gitops runbooks links traceability check

lint:
	$(UV) ruff check product-metrics
	$(UV) ruff format --check product-metrics

# NFR-U11-30: mypy en modo estricto sobre `vectra_product` (la configuracion `strict` esta en el `pyproject.toml` de la raiz).
types:
	$(UV) mypy product-metrics/src/vectra_product

imports:
	$(UV) lint-imports --config product-metrics/.importlinter

# Pasos 1 a 9: las pruebas **de integracion** con el perfil `ci` (500 ejemplos, semilla impresa en la cabecera, sin `-q`). `tests/unit` y `tests/property` las corre el
# primer comando de `coverage` con el mismo perfil: aqui no se repiten (C-7). La prueba de la imagen (`image-test`) va despues de construirla. No corre `-m volume` (Paso 7).
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests/integration -p no:cacheprovider -m "not volume" \
		--ignore=product-metrics/tests/integration/test_image.py

# Paso 5 (NFR-U11-30): cobertura de ramas del 100 % en `compute` y `noise`, con `tests/unit` y `tests/property` y el perfil `ci`. `mutmut` esta diferido por la demo (T3).
# Paso 8 (NFR-U11-30): cobertura de ramas >= 90 % en el resto (`vectra_product` entero); corre las pruebas del proceso real y las de ejemplos con el perfil por omision (las de
# `ci` ya las corre `test`), sin repetir las de render (`test_chart`, `test_gen_rules`, `test_dashboards`, que no cubren `vectra_product` y ya corrieron arriba) ni la de la
# imagen (`image-test`). No corre `-m volume` (diferida, T3).
coverage:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests/unit product-metrics/tests/property -p no:cacheprovider \
		--cov=vectra_product.compute --cov=vectra_product.noise --cov-branch --cov-fail-under=100
	cd $(ROOT) && uv run pytest product-metrics/tests -p no:cacheprovider -m "not volume" \
		--ignore=product-metrics/tests/integration/test_image.py --ignore=product-metrics/tests/unit/test_chart.py \
		--ignore=product-metrics/tests/unit/test_gen_rules.py --ignore=product-metrics/tests/unit/test_dashboards.py \
		--cov=vectra_product --cov-branch --cov-fail-under=90 --cov-report=term-missing

# Paso 12: las reglas generadas (`chart/files/generated-rules.yaml`) y su deriva (BR-U11-06; P-U11-05).
gen-rules:
	$(UV) python product-metrics/tools/gen_rules.py --check

# Paso 12: el `spec` de la PrometheusRule renderizada en los tres entornos (identico), contra el archivo versionado, y `promtool` (`check rules` y `test rules`).
# **Falla** si falta `promtool` o `helm` (no se salta con rc 0) o si el versionado difiere (se regenera con `gen_rules.py --spec`).
rules:
	$(UV) python product-metrics/tools/gen_rules.py --spec --check
	$(TOOLS)/promtool check rules $(ROOT)/product-metrics/observability/rules/product-metrics.rules.yaml
	$(TOOLS)/promtool test rules $(ROOT)/product-metrics/observability/rules/tests/*.yaml

# Paso 10: imagen local, con el contexto en la raiz de vectra-risk/. El `docker push` a `kind-registry` y el digest real los hace el operador en la verificacion
# consolidada de U12 Paso 18: `product-metrics/docs/imagenes.md`. `hadolint` va antes (falla si falta).
image:
	$(TOOLS)/hadolint $(ROOT)/product-metrics/Dockerfile
	cd $(ROOT) && docker build -t localhost:5001/vectra/product-metrics:dev -f product-metrics/Dockerfile .

# Paso 10/11 (CA-4): el contenedor real arranca con lo que pone el chart. Corre **despues** de `image`, para no probar una imagen vieja (candidata de U09-T04, F-03).
image-test:
	$(UV) pytest product-metrics/tests/integration/test_image.py -p no:cacheprovider -v

# Paso 11: el render de cada entorno con lo que usa Argo CD (`components.yaml`), `kubeconform -strict` con los CRD de `tests/fixtures/crds/` y `conftest` de
# `policies/conftest/` (por documento y con todo el render junto). `test_chart.py` tiene un caso que falla por cada regla. **Falla** si falta una herramienta.
policy-chart:
	cd $(ROOT) && rm -rf $(U1)/render && mkdir -p $(U1)/render
	for env in $(ENVS); do \
		cd $(ROOT) && uv run python platform/tests/integration.py --chart product-metrics/chart --namespace vectra-app --env $$env --out $(U1)/render/$$env && \
		$(TOOLS)/kubeconform -strict -summary -schema-location default -schema-location '$(CRDS)/{{.ResourceKind}}.json' $(U1)/render/$$env/*.yaml && \
		$(TOOLS)/conftest test --policy $(POLICIES) $(U1)/render/$$env/*.yaml && \
		$(TOOLS)/conftest test --combine --namespace chart_set --policy $(POLICIES) $(U1)/render/$$env/*.yaml || exit 1; \
	done

# Las politicas de U1 (Kyverno y rego) sobre el render de cada entorno, y las pruebas de Kyverno de U1 (`require-hpa-bounds` con y sin la exencion).
# `platform check-chart` rinde los tres entornos en un mismo directorio y Kyverno aborta con recursos repetidos (`panic`; candidata de U03-T04 y U04-T05): aqui se rinde un entorno por directorio.
policy-chart-u1:
	cd $(ROOT) && rm -rf $(U1)/u1 && mkdir -p $(U1)/u1
	for env in $(ENVS); do \
		mkdir -p $(U1)/u1/$$env/policies && \
		cd $(ROOT) && uv run python platform/tests/integration.py --chart product-metrics/chart --namespace vectra-app --env $$env --out $(U1)/u1/$$env/resources && \
		cd $(ROOT)/platform/policies/kyverno && cp $(STATIC_POLICIES) $(U1)/u1/$$env/policies/ && \
		{ $(TOOLS)/kyverno apply $(U1)/u1/$$env/policies --resource $(U1)/u1/$$env/resources > $(U1)/u1/$$env/report.txt 2>&1 || true; } && \
		{ grep -E '$(KYVERNO_OK)' $(U1)/u1/$$env/report.txt || { grep -E 'fail:|FAIL|error|panic' $(U1)/u1/$$env/report.txt | head -40; exit 1; }; } && \
		$(TOOLS)/conftest test --policy $(ROOT)/platform/policies/rego $(U1)/u1/$$env/resources && \
		$(TOOLS)/conftest test --combine --namespace hpa --policy $(ROOT)/platform/policies/rego $(U1)/u1/$$env/resources || exit 1; \
	done
	cd $(ROOT) && $(TOOLS)/kyverno test platform/policies/kyverno

# Paso 11 (NFR-U11-14; INF-U11-04): cuota y flujos. El plan dice `conftest test platform/policies/quotas/`; en el repositorio esa comprobacion es
# `quotas/render.py --check` y `test_every_workload_declares_requests_and_limits_and_fits_the_quota`. Mas la deriva de las politicas de red de U1 y las pruebas
# de `test_chart.py` de CODEOWNERS, flujos, cuota y el `Server` metrics-8081.
quota-flows:
	$(UV) python platform/policies/quotas/render.py --check
	$(UV) pytest "platform/tests/test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota" -p no:cacheprovider -q
	$(UV) python platform/network/generate.py --check
	$(UV) pytest platform/network/tests -p no:cacheprovider -q
	$(UV) pytest product-metrics/tests/unit/test_chart.py -p no:cacheprovider -q -k "codeowners or flows or quota or metrics_8081"

# Paso 15: la Application (una por entorno, sin auto-sync, wave 5) y las olas.
gitops:
	$(UV) python vectra-risk-gitops/generate.py --check
	$(UV) python platform/tests/test_waves.py
	for app in $(APPS); do $(TOOLS)/kyverno apply $(ROOT)/platform/policies/kyverno/disallow-argocd-auto-sync.yaml --resource $$app || exit 1; done

# Paso 13: cada `runbook_url` de las seis reglas apunta a un archivo que sigue la plantilla de U1 (con un comando en cada paso de «Verificacion»).
runbooks:
	$(UV) python platform/tests/test_runbooks.py --root product-metrics
	$(UV) python platform/tests/test_runbooks.py --root product-metrics --operational
	$(UV) python contracts/tools/forbidden_phrases.py product-metrics/observability/dashboards/product.json product-metrics/observability/runbooks/*.md product-metrics/README.md

# Paso 17: enlaces relativos del Markdown de la unidad.
links:
	$(UV) python platform/tests/test_links.py --root product-metrics

# La trazabilidad usa la lista «Diferido por la demo» de `evidence/cierre-demo.md` (P-4; `DECISIONES-LOOP.md` §6).
traceability:
	$(UV) python platform/tests/test_traceability.py --unit product-metrics --all

# Paso 18 (cierre acotado a la demo): las verificaciones estaticas, las propiedades y las pruebas de integracion, las de reglas, imagen, chart, admision, cuota,
# flujos, runbooks, enlaces y trazabilidad de los Pasos 1 a 15. Falla si falta una herramienta (`promtool`, `helm`, `kubeconform`, `conftest`, `kyverno`,
# `hadolint`, Docker): no se salta con rc 0. Diferidos por la demo: el workflow (Paso 14, T4), `mutmut` y la prueba de volumen (T3) y la verificacion en kind (Paso 16, U12).
check: lint types imports test coverage gen-rules rules image image-test policy-chart policy-chart-u1 quota-flows gitops runbooks links traceability
