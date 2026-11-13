# Comandos de U10 `console` (`console-bff` y `console-spa`). Se ejecutan desde cualquier sitio; corren en la raiz del workspace `vectra-risk/`.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
UV := cd $(ROOT) && uv run
NPM := cd $(ROOT) && npm run -w console/spa

# Las politicas de U1 que se evaluan sin firmas ni consultas a la API (las mismas que `STATIC_POLICIES` de platform/Makefile).
STATIC_POLICIES := disallow-latest.yaml require-run-as-non-root.yaml disallow-privileged.yaml disallow-host-path.yaml require-ro-rootfs.yaml require-resources.yaml require-priority-class.yaml require-criticality-label.yaml disallow-plain-secrets.yaml disallow-rbac-wildcards.yaml restrict-loadbalancer.yaml restrict-registries.yaml
# `pass: 0` no aprueba: ninguna regla vio un recurso.
KYVERNO_OK := pass: [1-9][0-9]*, fail: 0, warn: 0, error: 0
TOOLS := $(ROOT)/platform/.tools/bin
# `kubeconform` toma el esquema de `ServiceMonitor` de U7 (C-10: no se copia `crd_to_schema.py`).
CRDS := $(ROOT)/scoring-explainability/tests/fixtures/crds
POLICIES := $(ROOT)/console/policies/conftest
ENVS := kind staging prod
CHARTS := bff:vectra-app spa:vectra-edge
U10 := $(ROOT)/platform/.tools/integration/u10
APPS := $(foreach e,$(ENVS),$(foreach n,console-bff console-spa,$(ROOT)/vectra-risk-gitops/apps/$(e)/$(n).yaml))
IMAGE_BFF := localhost:5001/vectra/console-bff:dev
IMAGE_SPA := localhost:5001/vectra/console-spa:dev

.PHONY: lint-bff lint-spa lint test-bff test-spa build-spa e2e-spa test image-bff image-spa image-test policy-chart policy-chart-u1 quota-flows gitops links traceability check

lint-bff:
	$(UV) ruff check console
	$(UV) ruff format --check console
	cd $(ROOT) && MYPYPATH=console/bff/src uv run mypy --strict console/bff/src console/bff/tools
	$(UV) lint-imports --config console/bff/.importlinter

# `npm ci` ya lo dejo hecho el `contracts check` o el desarrollador; aqui solo se invocan los scripts del workspace.
lint-spa:
	$(NPM) lint
	$(NPM) typecheck

lint: lint-bff lint-spa

# CA-7 (U10-T01): cobertura de ramas del 100 % en `object_rules` y `errors` (NFR-U10-60); `mutmut` diferido por la demo (T3).
# CA-7 (U10-T02): ademas, >= 90 % en todo `console_bff` con **toda** la suite (unit, property, integration y doubles).
COV_PURE := --cov=console_bff.object_rules --cov=console_bff.errors --cov-branch --cov-fail-under=100
COV_ALL := --cov=console_bff --cov-branch --cov-fail-under=90
# `console/bff/pytest.ini` apunta la cobertura a `console_bff` y no a la de U0 de la raiz. Las corridas son en serie (maquina compartida).
# U10-T05: `test_image.py` (necesita las imagenes: `image-test`) y `test_chart.py` (necesita las herramientas de U1: `policy-chart`) tienen su propio target, despues de construir y de rendir.
NOT_HERE := --ignore=console/bff/tests/integration/test_image.py --ignore=console/bff/tests/unit/test_chart.py
test-bff:
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests -q -p no:cacheprovider --rootdir=console/bff $(NOT_HERE) $(COV_ALL)
	cd $(ROOT) && HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests/unit console/bff/tests/property -q -p no:cacheprovider --rootdir=console/bff $(NOT_HERE) $(COV_PURE)
	cd $(ROOT) && uv run python console/bff/tools/role_matrix.py --check

# U10-T03 (CA-6) y U10-T04 (Paso 16): vitest con cobertura de ramas. Umbrales en `console/spa/vite.config.ts`: 100 % en `src/stepup/**` (NFR-U10-61) y en
# `src/views/cases/decision-validation.ts` (la validacion de la decision, PBT-U10-04), y >= 80 % en todo `src/`. Imprime la semilla de las PBT
# (NFR-U10-62); `VECTRA_PBT_PROFILE=nightly` elige el perfil nocturno.
# `chart-config.test.ts` (U10-T05) necesita el render del chart (`VECTRA_CHART_RENDER`): lo corre `policy-chart`, despues de rendir.
test-spa:
	$(NPM) test -- --coverage --exclude tests/unit/chart-config.test.ts

# U10-T04 (Paso 15): el build de la SPA y su presupuesto (NFR-U10-03: el JavaScript inicial <= 250 KiB con gzip; lee el manifiesto de Vite).
build-spa:
	$(NPM) build
	cd $(ROOT) && npm exec -w console/spa -- size-limit

# U10-T03 (CA-1, la puerta del Paso 10) y U10-T04 (Paso 15): Playwright en Chromium y Firefox contra el emisor OIDC de prueba y el BFF con dobles:
# la PoC del step-up (`tests/poc`), el recorrido de las vistas (`tests/e2e`), la CSP de U2 con Trusted Types (`tests/csp`) y `axe` (`tests/a11y`),
# sobre el BUILD servido con `vite preview` (P-3 (a)). Los navegadores no vienen con `npm ci`: si faltan, falla diciendo como instalarlos. En serie.
e2e-spa: build-spa
	cd $(ROOT) && node console/spa/scripts/check-browsers.mjs
	cd $(ROOT) && npx playwright test -c console/spa/playwright.config.ts tests/poc tests/e2e tests/csp tests/a11y --project=chromium --project=firefox

test: test-bff test-spa e2e-spa

# --- Pasos 17, 18, 21, 23 y 24 (U10-T05) --------------------------------------------------------------------------------------------------

# Paso 17: imagenes locales, con el contexto en la raiz de vectra-risk/. El `docker push` a `kind-registry` y el digest real los hace el operador en la verificacion consolidada de
# U12 Paso 18 (README.md, seccion «Imagenes»). `hadolint` va antes (falla si falta).
image-bff:
	$(TOOLS)/hadolint $(ROOT)/console/bff/Dockerfile
	cd $(ROOT) && docker build -t $(IMAGE_BFF) -f console/bff/Dockerfile .

image-spa:
	$(TOOLS)/hadolint $(ROOT)/console/spa/Dockerfile
	cd $(ROOT) && docker build -t $(IMAGE_SPA) -f console/spa/Dockerfile .

# CA-4: los dos contenedores reales arrancan con lo que pone el chart. Corre **despues** de `image-bff` e `image-spa` (en `check` va asi), para no probar una imagen vieja (candidata de U09-T04, F-03).
image-test:
	$(UV) pytest console/bff/tests/integration/test_image.py -p no:cacheprovider --rootdir=console/bff -v

# Paso 18: el render de cada entorno con lo que usa Argo CD (`components.yaml`), `kubeconform -strict`, `conftest` por documento y con todo el render junto (con los datos del realm de U2 por
# `--data`, que genera `bff/tools/chart_data.py`), el `config.json` por el `parseConfig` real de la SPA (`chart-config`) y `test_chart.py`, que tiene un caso por regla. **Falla** si falta una herramienta.
policy-chart:
	rm -rf $(U10)/bff $(U10)/spa
	mkdir -p $(U10)
	for env in $(ENVS); do \
		cd $(ROOT) && uv run python console/bff/tools/chart_data.py --env $$env --out $(U10)/data-$$env.json || exit 1; \
	done
	for c in $(CHARTS); do \
		for env in $(ENVS); do \
			cd $(ROOT) && uv run python platform/tests/integration.py --chart console/chart/$${c%%:*} --namespace $${c##*:} --env $$env --out $(U10)/$${c%%:*}/$$env && \
			$(TOOLS)/kubeconform -strict -summary -schema-location default -schema-location '$(CRDS)/{{.ResourceKind}}.json' $(U10)/$${c%%:*}/$$env/*.yaml && \
			$(TOOLS)/conftest test --policy $(POLICIES) --data $(U10)/data-$$env.json $(U10)/$${c%%:*}/$$env/*.yaml && \
			$(TOOLS)/conftest test --combine --namespace console_set --policy $(POLICIES) --data $(U10)/data-$$env.json $(U10)/$${c%%:*}/$$env/*.yaml || exit 1; \
		done; \
	done
	cd $(ROOT) && VECTRA_CHART_RENDER=$(U10)/spa npm run -w console/spa test -- chart-config
	$(UV) pytest console/bff/tests/unit/test_chart.py -p no:cacheprovider --rootdir=console/bff -q

# Las politicas de U1 (Kyverno y rego) sobre el render de cada entorno y de cada chart, y las pruebas de Kyverno de U1 (`require-hpa-bounds` con y sin la exencion; los casos `console-spa`).
# `platform check-chart` rinde los tres entornos en un mismo directorio y Kyverno aborta con recursos repetidos (`panic`; C-8) y ademas borra `platform/.tools/integration/chart`:
# aqui se rinde un chart y un entorno por directorio, dentro de `platform/.tools/integration/u10/`.
policy-chart-u1:
	rm -rf $(U10)/u1
	mkdir -p $(U10)/u1
	for c in $(CHARTS); do \
		for env in $(ENVS); do \
			d=$(U10)/u1/$${c%%:*}/$$env; mkdir -p $$d/policies && \
			cd $(ROOT) && uv run python platform/tests/integration.py --chart console/chart/$${c%%:*} --namespace $${c##*:} --env $$env --out $$d/resources && \
			cd $(ROOT)/platform/policies/kyverno && cp $(STATIC_POLICIES) $$d/policies/ && \
			{ $(TOOLS)/kyverno apply $$d/policies --resource $$d/resources > $$d/report.txt 2>&1 || true; } && \
			{ grep -E '$(KYVERNO_OK)' $$d/report.txt || { grep -E 'fail:|FAIL|error|panic' $$d/report.txt | head -40; exit 1; }; } && \
			$(TOOLS)/conftest test --policy $(ROOT)/platform/policies/rego $$d/resources && \
			$(TOOLS)/conftest test --combine --namespace hpa --policy $(ROOT)/platform/policies/rego $$d/resources || exit 1; \
		done; \
	done
	cd $(ROOT) && $(TOOLS)/kyverno test platform/policies/kyverno

# Paso 18 (INF-U10-01, 04): cuota y flujos. El plan dice `conftest test platform/policies/quotas/`; en el repositorio esa comprobacion es `quotas/render.py --check` y
# `test_every_workload_declares_requests_and_limits_and_fits_the_quota`. Mas la deriva de las politicas de red de U1 y las pruebas de `test_chart.py` de cuota y flujos.
quota-flows:
	$(UV) python platform/policies/quotas/render.py --check
	$(UV) pytest "platform/tests/test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota" -p no:cacheprovider -q
	$(UV) python platform/network/generate.py --check
	$(UV) pytest platform/network/tests -p no:cacheprovider -q
	$(UV) pytest console/bff/tests/unit/test_chart.py -p no:cacheprovider --rootdir=console/bff -q -k "quota or flows or forbidden"

# Paso 21: las dos Applications por entorno (sin auto-sync, wave 5) y las olas.
gitops:
	$(UV) python vectra-risk-gitops/generate.py --check
	$(UV) python platform/tests/test_waves.py
	for app in $(APPS); do $(TOOLS)/kyverno apply $(ROOT)/platform/policies/kyverno/disallow-argocd-auto-sync.yaml --resource $$app || exit 1; done

# Paso 23: enlaces relativos del Markdown de la unidad.
links:
	$(UV) python platform/tests/test_links.py --root console

# La trazabilidad usa la lista «Diferido por la demo» de `evidence/cierre-demo.md` (P-4; `DECISIONES-LOOP.md` §6).
traceability:
	$(UV) python platform/tests/test_traceability.py --unit console --all

# Paso 24 (cierre acotado a la demo): las verificaciones estaticas, las pruebas del BFF y de la SPA, Playwright con dobles, las dos imagenes (construidas **antes** de `image-test`), el chart y su
# admision, la cuota y los flujos, las Applications, los enlaces y la trazabilidad de los Pasos 1 a 21. Falla si falta una herramienta (`helm`, `kubeconform`, `conftest`, `kyverno`, `hadolint`,
# Docker, los navegadores de Playwright): no se salta con rc 0. Diferidos por la demo: los workflows (Paso 20, T4), las alertas y runbooks (Paso 19, T2), k6, Lighthouse CI, `mutmut` y Stryker (T3)
# y la verificacion en kind (Paso 22, consolidada en U12).
check: lint test-bff test-spa e2e-spa image-bff image-spa image-test policy-chart policy-chart-u1 quota-flows gitops links traceability
