# Comandos de U4 `governance`. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run

.PHONY: lint test rules image image-validation check render-chart policy-chart policy-chart-u1 policy-runbook shellcheck coverage

lint:
	$(UV) ruff check governance
	cd $(ROOT) && MYPYPATH=governance/src:governance/validation_job:governance/promotion_tool:bias-monitoring/disparity/src uv run mypy --strict governance/src governance/validation_job governance/promotion_tool
	$(UV) lint-imports --config governance/.importlinter

# Las pruebas de integracion levantan PostgreSQL con Testcontainers (Docker local, sin cluster; AUTONOMIA-01).
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest governance/tests -q

# Reglas de alerta con `promtool` (P-3: `CompensationEventPending`). Usa el del PATH o `platform/.tools/bin/promtool`; si ninguno
# existe (un worktree sin `make -C platform tools`), lo dice y lo omite: la prueba `test_observability.py` lee la regla y el CI
# corre `check-tools` de U1.
PROMTOOL := $(firstword $(shell command -v promtool) $(wildcard $(ROOT)/platform/.tools/bin/promtool))
rules:
	@if [ -z "$(PROMTOOL)" ]; then echo "promtool no disponible: se omite (lo corre el CI)"; else \
	  cd $(ROOT) && $(PROMTOOL) check rules governance/observability/*.yaml && $(PROMTOOL) test rules governance/observability/tests/*.yaml; fi

# Imagen local de `governance-service` (Paso 16, agregado por el usuario). Contexto: la raiz de vectra-risk/. El `docker push` a `kind-registry` y el
# digest real los hace el operador en U04-T07 (AUTONOMIA-01).
image:
	cd $(ROOT) && docker build -t localhost:5001/vectra/governance:dev -f governance/Dockerfile .

# Imagen local del `model-validation-job` (Paso 13). Contexto: la raiz de vectra-risk/. El `docker push` a `kind-registry` y el digest real
# los hace el operador en U04-T07 (AUTONOMIA-01).
image-validation:
	cd $(ROOT) && docker build -t localhost:5001/vectra/model-validation-job:dev -f governance/validation_job/Dockerfile .

# Chart de U4 (Paso 16 acotado a la demo): `helm template` + `conftest` con las reglas de `chart/policy/` (HPA, spread, PDB, `vectra-high`, DSN sin
# clave, hook de migracion, RBAC de K01, sin `model-archive`). `test_chart.py` tiene un caso que falla por cada regla. Necesita platform/install-tools.sh.
TOOLS := $(ROOT)/platform/.tools/bin
CHART := $(ROOT)/governance/chart

render-chart:
	$(TOOLS)/helm template governance $(CHART)

policy-chart:
	$(TOOLS)/helm template governance $(CHART) | $(TOOLS)/conftest test --policy $(CHART)/policy -
	$(TOOLS)/helm template governance $(CHART) | $(TOOLS)/conftest test --combine --namespace chart_set --policy $(CHART)/policy -

# Las politicas de U1 (Kyverno y rego) sobre el render de cada entorno, con los values que usa Argo CD (`components.yaml`).
# `platform check-chart` rinde los tres entornos en un mismo directorio y Kyverno aborta con recursos repetidos (`panic`; candidata de U1):
# aqui se rinde un entorno por directorio, como U3 y U6.
STATIC_POLICIES := disallow-latest.yaml require-run-as-non-root.yaml disallow-privileged.yaml disallow-host-path.yaml require-ro-rootfs.yaml require-resources.yaml require-priority-class.yaml require-criticality-label.yaml disallow-plain-secrets.yaml disallow-rbac-wildcards.yaml restrict-loadbalancer.yaml restrict-registries.yaml
# `pass: 0` no aprueba: ninguna regla vio un recurso.
KYVERNO_OK := pass: [1-9][0-9]*, fail: 0, warn: 0, error: 0
ENVS := kind staging prod
U1 := $(ROOT)/platform/.tools/integration/u4

policy-chart-u1:
	cd $(ROOT) && rm -rf $(U1) && mkdir -p $(U1)
	for env in $(ENVS); do \
		mkdir -p $(U1)/$$env/policies && \
		cd $(ROOT) && uv run python platform/tests/integration.py --chart governance/chart --namespace vectra-app --env $$env --out $(U1)/$$env/resources && \
		cd $(ROOT)/platform/policies/kyverno && cp $(STATIC_POLICIES) $(U1)/$$env/policies/ && \
		{ $(TOOLS)/kyverno apply $(U1)/$$env/policies --resource $(U1)/$$env/resources > $(U1)/$$env/report.txt 2>&1 || true; } && \
		{ grep -E '$(KYVERNO_OK)' $(U1)/$$env/report.txt || { grep -E 'fail:|FAIL|error|panic' $(U1)/$$env/report.txt | head -40; exit 1; }; } && \
		$(TOOLS)/conftest test --policy $(ROOT)/platform/policies/rego $(U1)/$$env/resources && \
		$(TOOLS)/conftest test --combine --namespace hpa --policy $(ROOT)/platform/policies/rego $(U1)/$$env/resources || exit 1; \
	done

# CA-7 de U04-T07: lo que crea el runbook de la politica en kind (el pod efimero de `llamar.sh` y la ServiceAccount `console-bff`) pasa las
# politicas de kind de U1 (las mismas de arriba, sin `verify-images`, que Kyverno solo aplica al clúster). `llamar.sh --dry-run` rinde el Pod
# con `kubectl run --dry-run=client` (sin servidor). Sin `kubectl` en el PATH se omite (lo corre el CI).
RB := $(ROOT)/platform/.tools/integration/u4-runbook

policy-runbook:
	@if ! command -v kubectl >/dev/null; then echo "kubectl no disponible: se omite policy-runbook (lo corre el CI)"; else \
	  cd $(ROOT) && rm -rf $(RB) && mkdir -p $(RB)/policies $(RB)/resources && \
	  cd $(ROOT)/platform/policies/kyverno && cp $(STATIC_POLICIES) $(RB)/policies/ && \
	  cd $(ROOT) && governance/docs/kind/llamar.sh --dry-run politica-lee GET /v1/policies > $(RB)/resources/pod.yaml && \
	  printf 'apiVersion: v1\nkind: ServiceAccount\nmetadata:\n  name: console-bff\n  namespace: vectra-app\n' > $(RB)/resources/serviceaccount.yaml && \
	  { $(TOOLS)/kyverno apply $(RB)/policies --resource $(RB)/resources > $(RB)/report.txt 2>&1 || true; } && \
	  { grep -E '$(KYVERNO_OK)' $(RB)/report.txt || { grep -E 'fail:|FAIL|error|panic' $(RB)/report.txt | head -40; exit 1; }; }; fi

# `shellcheck` de los scripts del operador (`docs/kind/*.sh`): el del PATH o `uvx --from shellcheck-py shellcheck`.
shellcheck:
	@cd $(ROOT) && if command -v shellcheck >/dev/null; then shellcheck governance/docs/kind/*.sh; \
	  elif command -v uvx >/dev/null; then uvx --from shellcheck-py shellcheck governance/docs/kind/*.sh; \
	  else echo "shellcheck no disponible: se omite (lo corre el CI)"; fi

# Cobertura de ramas (NFR-U4-41): >= 95 % en `vectra_governance` y 100 % en `model_fsm`, `policy` y `evidence`. El `--cov` sin argumento mide el
# `source` de la raiz (solo U0), por eso se nombra el paquete. `mutmut` en `model_fsm` esta diferido (T3; cierre-demo.md).
coverage:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest governance/tests -q --cov=vectra_governance --cov-branch --cov-fail-under=95
	cd $(ROOT) && uv run coverage report --include="*/vectra_governance/model_fsm.py,*/vectra_governance/policy.py,*/vectra_governance/evidence.py" --fail-under=100

# Verificaciones estaticas (AUTONOMIA-01). `coverage` corre las pruebas de `test` con la medicion (NFR-U4-41); la trazabilidad usa la lista
# «Diferido por la demo» de evidence/cierre-demo.md (P-4).
check: lint rules shellcheck coverage policy-chart policy-chart-u1 policy-runbook
	cd $(ROOT) && uv run python platform/tests/test_traceability.py --unit governance --all
