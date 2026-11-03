# Comandos de U2. Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
TOOLS := $(ROOT)/platform/.tools/bin
HELM := $(TOOLS)/helm
CONFTEST := $(TOOLS)/conftest
ENVS := kind staging prod
KYVERNO := $(TOOLS)/kyverno
U1_POLICIES := $(ROOT)/platform/policies
# Las politicas de U1 que se evaluan sin firmas ni consultas a la API (las mismas que `STATIC_POLICIES` de platform/Makefile).
STATIC_POLICIES := disallow-latest.yaml require-run-as-non-root.yaml disallow-privileged.yaml disallow-host-path.yaml require-ro-rootfs.yaml require-resources.yaml require-priority-class.yaml require-criticality-label.yaml disallow-plain-secrets.yaml disallow-rbac-wildcards.yaml restrict-loadbalancer.yaml restrict-registries.yaml
# `pass: 0` no aprueba: ninguna regla vio un recurso.
KYVERNO_OK := pass: [1-9][0-9]*, fail: 0, warn: 0, error: 0
KEYCLOAK := $(ROOT)/identity-edge/keycloak
CHART := $(ROOT)/platform/.charts/keycloakx/keycloakx
# Destino del render de Keycloak. Por defecto, el versionado; `check-keycloak-rendered` lo cambia por un directorio temporal.
OUT ?= $(KEYCLOAK)/rendered

JOBS := $(ROOT)/identity-edge/jobs
# Destino del render de los jobs. Por defecto, el versionado; `check-jobs-rendered` lo cambia por un directorio temporal.
JOBS_OUT ?= $(JOBS)/rendered

.PHONY: lint test check render-keycloak policy-keycloak policy-keycloak-u1 check-keycloak-rendered render-jobs policy-jobs policy-jobs-u1 check-jobs-rendered

lint:
	$(UV) ruff check identity-edge

test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests -q

# `helm template` de `keycloakx` (platform/.charts) con los values comunes y los de cada entorno (U02-T07, Paso 5).
render-keycloak:
	for env in $(ENVS); do \
	  mkdir -p $(OUT)/$$env && \
	  $(HELM) template keycloak $(CHART) --namespace vectra-identity --skip-tests \
	    -f $(KEYCLOAK)/values/common.yaml -f $(KEYCLOAK)/values/$$env.yaml > $(OUT)/$$env/keycloak.yaml || exit 1; \
	done

# Las reglas por documento sobre todo el render, y las que ven el entorno entero (`--combine`) una vez por entorno.
policy-keycloak:
	$(CONFTEST) test --policy $(KEYCLOAK)/policy $(KEYCLOAK)/rendered/
	for env in $(ENVS); do \
	  $(CONFTEST) test --combine --namespace keycloak_set --policy $(KEYCLOAK)/policy $(KEYCLOAK)/rendered/$$env/ || exit 1; \
	done

# Las politicas de U1 (Kyverno y Rego) sobre lo renderizado, en los tres entornos. `kyverno apply` sobre el directorio entero
# de politicas aplica 0 reglas (pass: 0); por eso se copian las estaticas, como hace platform/Makefile.
policy-keycloak-u1:
	tmp="$$(mktemp -d)" && trap 'rm -rf "$$tmp"' EXIT && mkdir "$$tmp/policies" && \
	cp $(foreach p,$(STATIC_POLICIES),$(U1_POLICIES)/kyverno/$(p)) "$$tmp/policies/" && \
	for env in $(ENVS); do \
	  $(KYVERNO) apply "$$tmp/policies" --resource $(KEYCLOAK)/rendered/$$env/ > "$$tmp/report-$$env.txt" 2>&1; \
	  grep -E '$(KYVERNO_OK)' "$$tmp/report-$$env.txt" || { grep -E 'fail:|FAIL|error' "$$tmp/report-$$env.txt" | head -40; exit 1; }; \
	  $(CONFTEST) test --policy $(U1_POLICIES)/rego $(KEYCLOAK)/rendered/$$env/ || exit 1; \
	  $(CONFTEST) test --combine --namespace hpa --policy $(U1_POLICIES)/rego $(KEYCLOAK)/rendered/$$env/ || exit 1; \
	done

# Lo versionado coincide con el render de ahora (sin tocar lo versionado).
check-keycloak-rendered:
	tmp="$$(mktemp -d)" && trap 'rm -rf "$$tmp"' EXIT && \
	$(MAKE) -f $(lastword $(MAKEFILE_LIST)) render-keycloak OUT="$$tmp" && \
	diff -r "$$tmp" $(KEYCLOAK)/rendered

# `helm template` del chart propio de `realm-drift` y `signing-key-age` (U02-T08, Paso 6). El realm de Git del entorno entra
# sin tocarlo (`--set-file`) y va al ConfigMap que lee `realm-drift`.
render-jobs:
	for env in $(ENVS); do \
	  mkdir -p $(JOBS_OUT)/$$env && \
	  $(HELM) template identity-jobs $(JOBS)/chart --namespace vectra-identity \
	    -f $(JOBS)/values/$$env.yaml --set-file realm=$(KEYCLOAK)/realm/realm.$$env.yaml > $(JOBS_OUT)/$$env/identity-jobs.yaml || exit 1; \
	done

policy-jobs:
	$(CONFTEST) test --policy $(JOBS)/policy $(JOBS)/rendered/
	for env in $(ENVS); do \
	  $(CONFTEST) test --combine --namespace jobs_set --policy $(JOBS)/policy $(JOBS)/rendered/$$env/ || exit 1; \
	done

# Las politicas de U1 sobre los jobs, en los tres entornos (mismo metodo que `policy-keycloak-u1`).
policy-jobs-u1:
	tmp="$$(mktemp -d)" && trap 'rm -rf "$$tmp"' EXIT && mkdir "$$tmp/policies" && \
	cp $(foreach p,$(STATIC_POLICIES),$(U1_POLICIES)/kyverno/$(p)) "$$tmp/policies/" && \
	for env in $(ENVS); do \
	  $(KYVERNO) apply "$$tmp/policies" --resource $(JOBS)/rendered/$$env/ > "$$tmp/report-$$env.txt" 2>&1; \
	  grep -E '$(KYVERNO_OK)' "$$tmp/report-$$env.txt" || { grep -E 'fail:|FAIL|error' "$$tmp/report-$$env.txt" | head -40; exit 1; }; \
	  $(CONFTEST) test --policy $(U1_POLICIES)/rego $(JOBS)/rendered/$$env/ || exit 1; \
	  $(CONFTEST) test --combine --namespace hpa --policy $(U1_POLICIES)/rego $(JOBS)/rendered/$$env/ || exit 1; \
	done

# Lo versionado coincide con el render de ahora (sin tocar lo versionado).
check-jobs-rendered:
	tmp="$$(mktemp -d)" && trap 'rm -rf "$$tmp"' EXIT && \
	$(MAKE) -f $(lastword $(MAKEFILE_LIST)) render-jobs JOBS_OUT="$$tmp" && \
	diff -r "$$tmp" $(JOBS)/rendered

# Verificaciones estaticas (AUTONOMIA-01). Crece con los pasos del plan.
check: lint check-keycloak-rendered policy-keycloak policy-keycloak-u1 check-jobs-rendered policy-jobs policy-jobs-u1 test
