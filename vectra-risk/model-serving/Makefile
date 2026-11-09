# Comandos de U6 `model-serving`. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
SRC := model-serving/common/src:model-serving/predictor/src:model-serving/explainer/src
REGISTRY ?= localhost:5001
TAG ?= dev

.PHONY: lint test check image-predictor image-explainer render-chart policy-chart policy-chart-u1 coverage

lint:
	$(UV) ruff check model-serving
	$(UV) ruff format --check model-serving
	cd $(ROOT) && MYPYPATH=$(SRC) uv run mypy --strict model-serving/common/src model-serving/predictor/src model-serving/explainer/src
	$(UV) lint-imports --config model-serving/.importlinter

# Los artefactos RT-3 y el modelo base salen de la entrega real de U5 (una vez por sesion, ~1 min).
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest model-serving/tests -q -p no:cacheprovider

# Las imagenes se construyen en local con el contexto en `vectra-risk/`; el push y el digest real son del Paso 11 (operador).
image-predictor:
	docker build -f $(ROOT)/model-serving/predictor/Dockerfile -t $(REGISTRY)/vectra/model-predictor:$(TAG) $(ROOT)

image-explainer:
	docker build -f $(ROOT)/model-serving/explainer/Dockerfile -t $(REGISTRY)/vectra/model-explainer:$(TAG) $(ROOT)

# El chart de U6 (Pasos 6 y 7): `helm template` de cada perfil + `kubeconform -strict` con el CRD de `InferenceService` de KServe v0.21.0
# (tests/fixtures/crds/) + `conftest` de `policies/conftest/` (por documento y con todo el render junto). `test_chart.py` tiene un caso que
# falla por cada regla. Necesita platform/install-tools.sh.
TOOLS := $(ROOT)/platform/.tools/bin
CHART := $(ROOT)/model-serving/chart
FIXTURES := $(ROOT)/model-serving/tests/fixtures
PROFILES := prod inactive staging
RENDER := $(ROOT)/platform/.tools/integration/u6-profiles

render-chart:
	$(TOOLS)/helm template ms $(CHART)

policy-chart:
	rm -rf $(RENDER) && mkdir -p $(RENDER)
	for p in $(PROFILES); do \
		$(TOOLS)/helm template ms $(CHART) -f $(FIXTURES)/values-$$p.yaml > $(RENDER)/$$p.yaml && \
		$(TOOLS)/kubeconform -strict -summary -schema-location default -schema-location '$(FIXTURES)/crds/{{.ResourceKind}}.json' $(RENDER)/$$p.yaml && \
		$(TOOLS)/conftest test --policy $(ROOT)/model-serving/policies/conftest $(RENDER)/$$p.yaml && \
		$(TOOLS)/conftest test --combine --namespace chart_set --policy $(ROOT)/model-serving/policies/conftest $(RENDER)/$$p.yaml || exit 1; \
	done

# Las politicas de U1 sobre lo que Argo CD renderiza en cada entorno (`envs/<env>/values.yaml` + `values/<env>/model-serving.yaml`) y sobre ese
# mismo render con cada perfil encima (lo que dejaria un PR de `promotion-tool`). Un entorno por directorio: `platform check-chart` rinde los
# tres juntos y Kyverno aborta con recursos repetidos (`panic`; candidata de U04-T05).
# Las politicas estaticas de `platform check-chart` (`pass` > 0) evaluan Pod y Deployment, que este chart no renderiza (los crea KServe), asi que
# no se usan aqui: se evalua `require-hpa-bounds`, la de U1 que si mira el InferenceService (activo >= 2 replicas, inactivo con hpa-exempt), y
# el rego de `platform/policies/rego` (main y hpa).
ENVS := kind staging prod
U1 := $(ROOT)/platform/.tools/integration/u6
GITOPS := $(ROOT)/vectra-risk-gitops
KYVERNO_BOUNDS := $(ROOT)/platform/policies/kyverno/require-hpa-bounds.yaml

policy-chart-u1:
	rm -rf $(U1) && mkdir -p $(U1)
	for env in $(ENVS); do \
		mkdir -p $(U1)/$$env && \
		$(TOOLS)/helm template ms $(CHART) -f $(GITOPS)/envs/$$env/values.yaml -f $(GITOPS)/values/$$env/model-serving.yaml > $(U1)/$$env/argocd.yaml && \
		for p in $(PROFILES); do \
			$(TOOLS)/helm template ms $(CHART) -f $(GITOPS)/envs/$$env/values.yaml -f $(GITOPS)/values/$$env/model-serving.yaml -f $(FIXTURES)/values-$$p.yaml > $(U1)/$$env/$$p.yaml || exit 1; \
		done && \
		for f in $(U1)/$$env/*.yaml; do \
			$(TOOLS)/kubeconform -strict -summary -schema-location default -schema-location '$(FIXTURES)/crds/{{.ResourceKind}}.json' $$f && \
			$(TOOLS)/conftest test --policy $(ROOT)/platform/policies/rego $$f && \
			$(TOOLS)/conftest test --combine --namespace hpa --policy $(ROOT)/platform/policies/rego $$f && \
			{ $(TOOLS)/kyverno apply $(KYVERNO_BOUNDS) --resource $$f > $$f.report 2>&1 || true; } && \
			{ grep -E 'fail: 0, warn: 0, error: 0' $$f.report || { cat $$f.report; exit 1; }; } || exit 1; \
		done; \
	done
	grep -q 'pass: 1,' $(U1)/kind/prod.yaml.report && grep -q 'pass: 1,' $(U1)/prod/inactive.yaml.report

# Cobertura de ramas (plan, Paso 10): >= 90 % en los tres paquetes y 100 % en `package_loader`. El `--cov` sin argumento mide el `source`
# de la raiz (solo U0), por eso se nombran los paquetes.
coverage:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest model-serving/tests -q -p no:cacheprovider --cov=vectra_predictor --cov=vectra_explainer --cov=vectra_serving_common --cov-branch --cov-fail-under=90
	cd $(ROOT) && uv run coverage report --include="*/vectra_serving_common/package_loader.py" --fail-under=100

# Verificaciones estaticas y pruebas (AUTONOMIA-01). `coverage` corre las pruebas de `test` con la medicion; la trazabilidad usa la lista
# «Diferido por la demo» de evidence/cierre-demo.md. Crece con los pasos del plan.
check: lint coverage policy-chart policy-chart-u1
	cd $(ROOT) && uv run python platform/tests/test_traceability.py --unit model-serving --all
