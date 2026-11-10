# Comandos de U9 (bias-monitoring). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

# Las politicas de U1 que se evaluan sin firmas ni consultas a la API (las mismas que `STATIC_POLICIES` de platform/Makefile).
STATIC_POLICIES := disallow-latest.yaml require-run-as-non-root.yaml disallow-privileged.yaml disallow-host-path.yaml require-ro-rootfs.yaml require-resources.yaml require-priority-class.yaml require-criticality-label.yaml disallow-plain-secrets.yaml disallow-rbac-wildcards.yaml restrict-loadbalancer.yaml restrict-registries.yaml
# `pass: 0` no aprueba: ninguna regla vio un recurso.
KYVERNO_OK := pass: [1-9][0-9]*, fail: 0, warn: 0, error: 0
TOOLS := $(ROOT)/platform/.tools/bin
CHART := $(ROOT)/bias-monitoring/chart
CRDS := $(ROOT)/bias-monitoring/tests/fixtures/crds
POLICIES := $(ROOT)/bias-monitoring/policies/conftest
ENVS := kind staging prod
U1 := $(ROOT)/platform/.tools/integration/u9

.PHONY: lint imports test property coverage coverage-bias simulation image render-chart policy-chart policy-chart-u1 traceability check

lint:
	$(UV) ruff check bias-monitoring
	$(UV) ruff format --check bias-monitoring

imports:
	$(UV) lint-imports --config bias-monitoring/.importlinter

# Pasos 1 a 8: pruebas con el perfil `ci` (500 ejemplos, semilla impresa). La simulacion tiene su propio objetivo.
# Las pruebas de la libreria y la simulacion tienen sus propios objetivos (`coverage` y `simulation`): no se corren dos veces.
# Las propiedades del Bloque C (`tests/property` salvo las de la libreria) corren en el objetivo `property`.
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests -p no:cacheprovider -m "not simulation" \
		--ignore=bias-monitoring/tests/unit/test_stats.py --ignore=bias-monitoring/tests/unit/test_disparity_examples.py \
		--ignore=bias-monitoring/tests/property --ignore=bias-monitoring/tests/simulation

# Pasos 6 a 9: PBT-U9-03 (publish), 04, 05, 07 (compare) y 08 con el perfil `ci` y la semilla impresa (sin `-q`, que oculta la cabecera con la semilla). `test_run_machine.py` fija sus
# propios ejemplos: PBT-U9-05 va con 500 secuencias de hasta 80 pasos, la letra de NFR-U9-52 (decision del usuario, U09-T04 P-2 = a). Cada paso
# es una corrida completa contra los dobles (~16 ms): la maquina tarda ~2 min en el perfil `ci`. Las cifras medidas estan en `evidence/cierre-demo.md`.
property:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/property/test_freeze_rule.py \
		bias-monitoring/tests/property/test_context.py bias-monitoring/tests/property/test_publish.py \
		bias-monitoring/tests/property/test_run_machine.py bias-monitoring/tests/property/test_compare.py -p no:cacheprovider

# Paso 5 (NFR-U9-50): cobertura de ramas del 100 % en la libreria. `bias-monitoring/pytest.ini` apunta la cobertura a
# `vectra_disparity` y no a la de U0 de la raiz.
coverage:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/unit/test_stats.py bias-monitoring/tests/unit/test_disparity_examples.py bias-monitoring/tests/property/test_disparity.py bias-monitoring/tests/property/test_counts.py -q -p no:cacheprovider --cov=vectra_disparity --cov-branch --cov-fail-under=100

# Paso 10 (NFR-U9-50): cobertura de ramas de `vectra_bias` (CronJob y servicio): >= 95 % en el conjunto y 100 % en `freeze_rule`, `context` y
# `window`. `--cov=vectra_bias` reemplaza el `source` de `coveragerc` (que mide solo la libreria). Mide **todas** las pruebas de
# `bias-monitoring/tests` salvo la simulacion (que tiene su objetivo): repite las de `test` y `property`, porque la cobertura de ramas se
# mide sobre una sola corrida; es el costo de un numero real y no de la suma de dos.
coverage-bias:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests -p no:cacheprovider -m "not simulation" \
		--cov=vectra_bias --cov-branch --cov-fail-under=95
	cd $(ROOT) && uv run coverage report --include='*/freeze_rule.py,*/context.py,*/window.py' --fail-under=100

# Paso 11: imagen local, con el contexto en la raiz de vectra-risk/. El `docker push` a `kind-registry` y el digest real los hace el operador
# en la verificacion consolidada de U12 Paso 18: `bias-monitoring/docs/imagenes.md`.
image:
	cd $(ROOT) && docker build -t localhost:5001/vectra/bias-monitoring:dev -f bias-monitoring/Dockerfile .

# Paso 12: el render de cada entorno con los values que usa Argo CD (`components.yaml`: los del entorno y `values-monitoring-policy.yaml`),
# `kubeconform -strict` con los CRD de `ExternalSecret` y `ServiceMonitor` (tests/fixtures/crds/) y `conftest` de `policies/conftest/` (por
# documento y con todo el render junto). `test_chart.py` tiene un caso que falla por cada regla. Necesita platform/install-tools.sh y **falla**
# si falta una herramienta: no se salta con rc 0.
render-chart:
	cd $(ROOT) && $(TOOLS)/helm template bias-monitoring $(CHART) -f vectra-risk-gitops/envs/kind/values.yaml -f $(CHART)/values-monitoring-policy.yaml

policy-chart:
	cd $(ROOT) && rm -rf $(U1)/render && mkdir -p $(U1)/render
	for env in $(ENVS); do \
		cd $(ROOT) && uv run python platform/tests/integration.py --chart bias-monitoring/chart --namespace vectra-app --env $$env --out $(U1)/render/$$env && \
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
		cd $(ROOT) && uv run python platform/tests/integration.py --chart bias-monitoring/chart --namespace vectra-app --env $$env --out $(U1)/u1/$$env/resources && \
		cd $(ROOT)/platform/policies/kyverno && cp $(STATIC_POLICIES) $(U1)/u1/$$env/policies/ && \
		{ $(TOOLS)/kyverno apply $(U1)/u1/$$env/policies --resource $(U1)/u1/$$env/resources > $(U1)/u1/$$env/report.txt 2>&1 || true; } && \
		{ grep -E '$(KYVERNO_OK)' $(U1)/u1/$$env/report.txt || { grep -E 'fail:|FAIL|error|panic' $(U1)/u1/$$env/report.txt | head -40; exit 1; }; } && \
		$(TOOLS)/conftest test --policy $(ROOT)/platform/policies/rego $(U1)/u1/$$env/resources && \
		$(TOOLS)/conftest test --combine --namespace hpa --policy $(ROOT)/platform/policies/rego $(U1)/u1/$$env/resources || exit 1; \
	done

# La trazabilidad usa la lista «Diferido por la demo» de `evidence/cierre-demo.md` (P-4).
traceability:
	cd $(ROOT) && uv run python platform/tests/test_traceability.py --unit bias-monitoring --all

# Paso 5 (NFR-U9-53): simulacion estadistica, 10 000 repeticiones. El workflow nocturno esta diferido (T4).
simulation:
	cd $(ROOT) && uv run pytest bias-monitoring/tests/simulation -m simulation -q -p no:cacheprovider -s

# `mutmut` en stats y disparity esta diferido por la demo (T3).
check: lint imports test property coverage coverage-bias simulation policy-chart policy-chart-u1 traceability
