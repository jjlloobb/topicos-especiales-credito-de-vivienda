# Verificaciones estaticas de U1 (Paso 23). Ninguna toca un cluster.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
TOOLS := $(ROOT)/platform/.tools/bin
# La version fijada de helm, si install-tools.sh la dejo ahi.
export PATH := $(TOOLS):$(PATH)
WORK := $(ROOT)/platform/.tools/integration
# Las politicas que se evaluan sin firmas (Paso 20) ni consultas a la API.
STATIC_POLICIES := disallow-latest.yaml require-run-as-non-root.yaml disallow-privileged.yaml disallow-host-path.yaml require-ro-rootfs.yaml require-resources.yaml require-priority-class.yaml require-criticality-label.yaml disallow-plain-secrets.yaml disallow-rbac-wildcards.yaml restrict-loadbalancer.yaml restrict-registries.yaml
# `pass: 0` no aprueba: ninguna regla vio un recurso.
KYVERNO_OK := pass: [1-9][0-9]*, fail: 0, warn: 0, error: 0
NAMESPACE ?= vectra-app
.PHONY: generate charts render check-local check-tools check-integration check-rendered check-chart check

generate:
	cd $(ROOT) && uv run python platform/network/generate.py
	cd $(ROOT) && uv run python platform/policies/quotas/render.py
	cd $(ROOT) && uv run python vectra-risk-gitops/generate.py

charts:
	cd $(ROOT) && PATH="$$(pwd)/.venv/bin:$$PATH" platform/charts.sh

render:
	cd $(ROOT) && PATH="$$(pwd)/.venv/bin:$$PATH" platform/render.sh

# Todo lo que corre sin kyverno, conftest ni promtool. La prueba de Grafana necesita una API de Docker
# en DOCKER_HOST (ver platform/tests/test_grafana_folder_permissions.py).
check-local: charts render
	cd $(ROOT) && uv run ruff check platform vectra-risk-gitops
	cd $(ROOT) && uv run python platform/network/generate.py --check
	cd $(ROOT) && uv run python vectra-risk-gitops/generate.py --check
	cd $(ROOT) && uv run python platform/policies/quotas/render.py --check
	cd $(ROOT) && uv run pytest platform -q -p no:cacheprovider --rootdir=platform --import-mode=importlib
	cd $(ROOT) && helm lint platform/namespaces platform/data/chart
	cd $(ROOT) && uv run python platform/tests/test_traceability.py
	cd $(ROOT) && uv run python platform/tests/test_runbooks.py
	cd $(ROOT) && uv run python platform/tests/test_runbooks.py --operational
	cd $(ROOT) && uv run python platform/tests/test_waves.py
	cd $(ROOT) && uv run python platform/tests/test_links.py

# Falla si faltan las herramientas: nunca parece aprobado lo que no se ejecuto.
check-tools:
	test -x $(TOOLS)/kyverno && test -x $(TOOLS)/conftest && test -x $(TOOLS)/promtool && test -x $(TOOLS)/actionlint && test -x $(TOOLS)/hadolint && test -x $(TOOLS)/kubeconform
	. $(ROOT)/platform/tools.env && helm version --short | grep -q "^$$HELM_VERSION+\|^$$HELM_VERSION$$"
	$(TOOLS)/kyverno test $(ROOT)/platform/policies/kyverno
	cd $(ROOT)/platform/observability/rules/tests && $(TOOLS)/promtool test rules *.yaml
	$(TOOLS)/promtool check rules $(ROOT)/platform/observability/rules/platform-rules.yaml
	cd $(ROOT) && uv run python platform/tests/rego_fixtures.py
	$(TOOLS)/conftest test --policy $(ROOT)/platform/policies/rego $(ROOT)/platform/rendered/prod
	$(TOOLS)/conftest test --combine --namespace hpa --policy $(ROOT)/platform/policies/rego $(ROOT)/platform/rendered/prod
	$(TOOLS)/conftest test --policy $(ROOT)/platform/policies/rego $(ROOT)/vectra-risk-gitops/apps/prod
	$(TOOLS)/kyverno apply $(ROOT)/platform/policies/kyverno/disallow-argocd-auto-sync.yaml --resource $(ROOT)/vectra-risk-gitops/apps/prod
	cd $(ROOT)/.. && $(TOOLS)/actionlint .github/workflows/*.yml
	$(MAKE) -f $(ROOT)/platform/Makefile check-integration

# Las politicas contra todo lo que se instalaria en vectra-*, y el RBAC de todo el cluster.
check-integration:
	rm -rf $(WORK) && mkdir -p $(WORK)/policies
	cd $(ROOT) && uv run python platform/tests/integration.py --out $(WORK)/resources
	cd $(ROOT)/platform/policies/kyverno && cp $(STATIC_POLICIES) $(WORK)/policies/
	$(TOOLS)/kyverno apply $(WORK)/policies --resource $(WORK)/resources > $(WORK)/report.txt 2>&1 || true
	grep -E '$(KYVERNO_OK)' $(WORK)/report.txt || { grep -E 'failed:|-> resource|fail:|^[0-9]+\.' $(WORK)/report.txt | head -60; exit 1; }

# Solo en CI: localmente rendered/ esta sin versionar y esto siempre falla. `git status` ve tambien lo que es nuevo.
check-rendered: render
	cd $(ROOT) && git diff --exit-code -- platform/rendered/
	cd $(ROOT) && test -z "$$(git status --porcelain -- platform/rendered/)" || { git status --short -- platform/rendered/; echo "platform/rendered/ difiere de lo versionado: corre make render"; exit 1; }

# El chart de una unidad: helm template + kyverno apply + conftest. CHART es relativo a vectra-risk/.
check-chart:
	@test -n "$(CHART)" || { echo "Falta CHART=<chart relativo a vectra-risk/>"; exit 1; }
	rm -rf $(WORK)/chart && mkdir -p $(WORK)/chart/policies
	cd $(ROOT) && uv run python platform/tests/integration.py --chart "$(CHART)" --namespace "$(NAMESPACE)" --out $(WORK)/chart/resources
	cd $(ROOT)/platform/policies/kyverno && cp $(STATIC_POLICIES) $(WORK)/chart/policies/
	$(TOOLS)/kyverno apply $(WORK)/chart/policies --resource $(WORK)/chart/resources > $(WORK)/chart/report.txt 2>&1 || true
	grep -E '$(KYVERNO_OK)' $(WORK)/chart/report.txt || { grep -E 'failed:|-> resource|fail:|^[0-9]+\.' $(WORK)/chart/report.txt | head -60; exit 1; }
	$(TOOLS)/conftest test --policy $(ROOT)/platform/policies/rego $(WORK)/chart/resources
	$(TOOLS)/conftest test --combine --namespace hpa --policy $(ROOT)/platform/policies/rego $(WORK)/chart/resources

check: check-local check-tools
