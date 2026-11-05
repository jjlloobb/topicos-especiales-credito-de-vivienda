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

.PHONY: collect-e2e e2e policy-ratelimit render-valkey check-valkey-rendered policy-valkey policy-valkey-u1 lint test check route-gen check-route-gen schemas-gateway kubeconform-gateway policy-gateway xds-gateway render-envoy-gateway render-keycloak policy-keycloak policy-keycloak-u1 check-keycloak-rendered render-jobs policy-jobs policy-jobs-u1 check-jobs-rendered

lint:
	$(UV) ruff check identity-edge

# Sin las e2e: necesitan un clúster (U02-T14, H3). Se ejecutan con `e2e` en el Paso 16.
test:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests --ignore=identity-edge/tests/e2e -q

# La suite e2e solo se colecta: lista todos los casos sin ninguna variable de entorno del clúster (U02-T14, H3).
collect-e2e:
	cd $(ROOT) && uv run pytest identity-edge/tests/e2e --collect-only -q

# Ejecuta la suite e2e contra kind (Paso 16, con aprobación del operador y las variables `VECTRA_E2E_*` y `SYNTH_*`). El perfil de Hypothesis `kind-e2e` lo registra el conftest de e2e. NO entra en `check`.
e2e:
	cd $(ROOT) && uv run pytest identity-edge/tests/e2e -q

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
# sin tocarlo (`--set-file`) y va al ConfigMap que lee `realm-drift`, en su propio archivo (decision T1).
render-jobs:
	for env in $(ENVS); do \
	  mkdir -p $(JOBS_OUT)/$$env && \
	  for file in identity-jobs realm-configmap; do \
	    $(HELM) template identity-jobs $(JOBS)/chart --namespace vectra-identity --show-only templates/$$file.yaml \
	      -f $(JOBS)/values/$$env.yaml --set-file realm=$(KEYCLOAK)/realm/realm.$$env.yaml > $(JOBS_OUT)/$$env/$$file.yaml || exit 1; \
	  done; \
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

GATEWAY := $(ROOT)/identity-edge/gateway
KUBECONFORM := $(TOOLS)/kubeconform
# Los esquemas de los CRDs de gateway-helm que `crd_schemas.py` deja en `.tools` (no se versiona).
SCHEMAS := $(ROOT)/identity-edge/.tools/schemas
# Sin `-ignore-missing-schemas`: un documento sin esquema es un error.
KUBECONFORM_OK := Valid: [1-9][0-9]*, Invalid: 0, Errors: 0, Skipped: 0

# Genera `gateway/generated/<env>/` desde `gateway/routes.yaml` y `gateway/values/<env>.yaml` (U02-T09, Paso 7).
route-gen:
	$(UV) python identity-edge/tools/route_gen.py

# Lo versionado coincide con lo generado (sin tocar lo versionado).
check-route-gen:
	$(UV) python identity-edge/tools/route_gen.py --check

# Convierte los CRDs de `platform/.charts/envoy-gateway/gateway-helm` (Envoy Gateway y Gateway API v1.6.1) a esquemas JSON.
schemas-gateway:
	rm -rf $(SCHEMAS)
	$(UV) python identity-edge/tools/crd_schemas.py

kubeconform-gateway: schemas-gateway
	for env in $(ENVS); do \
	  out="$$($(KUBECONFORM) -strict -summary -schema-location '$(SCHEMAS)/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' $(GATEWAY)/generated/$$env 2>&1)"; code=$$?; \
	  echo "$$out"; \
	  { [ $$code -eq 0 ] && echo "$$out" | grep -qE '$(KUBECONFORM_OK)'; } || exit 1; \
	done

# Las reglas por documento sobre todo lo generado, y las que ven el entorno entero (`--combine`) una vez por entorno.
policy-gateway:
	$(CONFTEST) test --policy $(GATEWAY)/policy $(GATEWAY)/generated/
	for env in $(ENVS); do \
	  $(CONFTEST) test --combine --namespace gateway_set --policy $(GATEWAY)/policy $(GATEWAY)/generated/$$env/ || exit 1; \
	done

# Verificaciones estaticas (AUTONOMIA-01). Crece con los pasos del plan.
check: lint check-keycloak-rendered policy-keycloak policy-keycloak-u1 check-jobs-rendered policy-jobs policy-jobs-u1 check-route-gen kubeconform-gateway policy-gateway xds-gateway render-envoy-gateway policy-ratelimit check-valkey-rendered policy-valkey policy-valkey-u1 collect-e2e test

# `helm template` del chart gateway-helm v1.9.3 con los values del controlador (U02-T10, Paso 8). Lo renderizado no se versiona.
EG_RENDER := $(ROOT)/identity-edge/.tools/envoy-gateway/render.yaml
render-envoy-gateway:
	mkdir -p $(dir $(EG_RENDER)) && \
	$(HELM) template envoy-gateway $(ROOT)/platform/.charts/envoy-gateway/gateway-helm --namespace envoy-gateway-system --skip-crds \
	  -f $(ROOT)/platform/operators/envoy-gateway.yaml > $(EG_RENDER) && test -s $(EG_RENDER)

# Traduccion offline de `gateway/generated/<env>/` a xDS con `egctl` (U02-T10, Paso 8): sin clúster, con un Secret TLS desechable.
xds-gateway:
	$(UV) python identity-edge/tools/xds_gateway.py

# --- U02-T11 (Paso 9): envoy-ratelimit y Valkey --------------------------------------------------------------------------

RATELIMIT := $(ROOT)/identity-edge/ratelimit
VALKEY := $(ROOT)/identity-edge/charts/valkey
# Destino del render de Valkey. Por defecto, el versionado; `check-valkey-rendered` lo cambia por un directorio temporal.
VALKEY_OUT ?= $(VALKEY)/rendered
CONTROLLER_VALUES := $(ROOT)/platform/operators/envoy-gateway.yaml
CONTROLLER_KIND_VALUES := $(ROOT)/platform/operators/envoy-gateway-kind.yaml
GATEWAY_HELM := $(ROOT)/platform/.charts/envoy-gateway/gateway-helm

# Las reglas de conftest sobre el render de `gateway-helm` con los values del controlador, en el banco (staging y prod comparten
# values) y en kind (que suma `envoy-gateway-kind.yaml`), y sobre el `ExternalSecret` de `envoy-gateway-system`. Kyverno no alcanza
# ese namespace: estas reglas exigen lo mismo que exigirian sus politicas (R2).
policy-ratelimit:
	tmp="$$(mktemp -d)" && trap 'rm -rf "$$tmp"' EXIT && mkdir "$$tmp/bank" "$$tmp/kind" && \
	$(HELM) template envoy-gateway $(GATEWAY_HELM) --namespace envoy-gateway-system --skip-crds -f $(CONTROLLER_VALUES) > "$$tmp/bank/render.yaml" && \
	$(HELM) template envoy-gateway $(GATEWAY_HELM) --namespace envoy-gateway-system --skip-crds -f $(CONTROLLER_VALUES) -f $(CONTROLLER_KIND_VALUES) > "$$tmp/kind/render.yaml" && \
	$(CONFTEST) test --policy $(RATELIMIT)/policy "$$tmp/bank/render.yaml" "$$tmp/kind/render.yaml" $(RATELIMIT)/external-secret.yaml && \
	$(CONFTEST) test --combine --namespace ratelimit_set --policy $(RATELIMIT)/policy "$$tmp/bank/render.yaml" "$$tmp/kind/render.yaml"

# `helm template` del chart propio de Valkey con los values comunes y los de cada entorno.
render-valkey:
	for env in $(ENVS); do \
	  mkdir -p $(VALKEY_OUT)/$$env && \
	  $(HELM) template valkey $(VALKEY) --namespace vectra-edge -f $(VALKEY)/values/$$env.yaml > $(VALKEY_OUT)/$$env/valkey.yaml || exit 1; \
	done

# Lo versionado coincide con el render de ahora (sin tocar lo versionado).
check-valkey-rendered:
	tmp="$$(mktemp -d)" && trap 'rm -rf "$$tmp"' EXIT && \
	$(MAKE) -f $(lastword $(MAKEFILE_LIST)) render-valkey VALKEY_OUT="$$tmp" && \
	diff -r "$$tmp" $(VALKEY)/rendered

policy-valkey:
	$(CONFTEST) test --policy $(VALKEY)/policy $(VALKEY)/rendered/
	for env in $(ENVS); do \
	  $(CONFTEST) test --combine --namespace valkey_set --policy $(VALKEY)/policy $(VALKEY)/rendered/$$env/ || exit 1; \
	done

# Las politicas de U1 (Kyverno y Rego) sobre lo renderizado, en los tres entornos (mismo metodo que `policy-keycloak-u1`).
policy-valkey-u1:
	tmp="$$(mktemp -d)" && trap 'rm -rf "$$tmp"' EXIT && mkdir "$$tmp/policies" && \
	cp $(foreach p,$(STATIC_POLICIES),$(U1_POLICIES)/kyverno/$(p)) "$$tmp/policies/" && \
	for env in $(ENVS); do \
	  $(KYVERNO) apply "$$tmp/policies" --resource $(VALKEY)/rendered/$$env/ > "$$tmp/report-$$env.txt" 2>&1; \
	  grep -E '$(KYVERNO_OK)' "$$tmp/report-$$env.txt" || { grep -E 'fail:|FAIL|error' "$$tmp/report-$$env.txt" | head -40; exit 1; }; \
	  $(CONFTEST) test --policy $(U1_POLICIES)/rego $(VALKEY)/rendered/$$env/ || exit 1; \
	  $(CONFTEST) test --combine --namespace hpa --policy $(U1_POLICIES)/rego $(VALKEY)/rendered/$$env/ || exit 1; \
	done
