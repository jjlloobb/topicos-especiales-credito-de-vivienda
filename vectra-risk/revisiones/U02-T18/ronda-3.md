# Ronda 3 (primera revisión): U02-T18

VEREDICTO: VERDE

Revisé `tarea/U02-T18` en d8a1f3b contra la base 0e3a1f3. El hash de la tarea coincide: `a82e413b…`. El worktree quedó limpio antes y después de la revisión, y no escribí nada en él. `generate.py` sin `--check` lo corrí sobre una copia en el scratchpad. El informe no lo dejé en `revisiones/U02-T18/ronda-3.md` porque no tengo herramientas de escritura: lo tiene que guardar el orquestador.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Applications generadas, 7×3 | `generate.py --check` + bucle `test -f` | pasa: exit 0, ninguna línea `falta` |
| 2 | Waves y dependencias | `uv run python platform/tests/test_waves.py` | pasa: kind 48, prod 45 y staging 47 «en orden», exit 0. Tarda 0,67 s porque es estático y lee los YAML del repo; no depende de estado externo |
| 3 | Sin auto-sync | `kyverno apply disallow-argocd-auto-sync` en los 3 entornos + `kyverno test platform/policies/kyverno` | pasa: kind 48/0, staging 47/0, prod 45/0 (pass/fail); 79 tests, 0 fallos |
| 4 | Manifiestos reales y ningún recurso repetido | `uv run pytest platform/tests/test_platform.py platform/tests/test_integration.py -q -rs` | pasa: 140 passed en 103 s, 0 skipped |
| 7 | El perfil de kind cabe; staging y prod no cambian | `pytest test_kind_profile.py` + `git diff 0cf1238 -- <renders de staging y prod> --stat` | pasa: 4 passed y diff vacío. Total calculado por mí: 4,9727 GiB, margen 0,0273 GiB, igual que la tabla de la bitácora |
| 5 | U2 en verde (en serie, después de CA-7) | `uv sync --frozen && make -C identity-edge check` | pasa: exit 0, 2649 passed en 1031 s, 0 skipped. kubeconform: 32 válidos ×3 |
| 6 | U1 en verde (en serie, después de CA-5) | `make -C platform check-local` | pasa: exit 0, 749 passed en 184 s, helm lint 2/0 |

## Mutaciones propias
- **Pares de waves.** Llamé a `problems_in` con `expected={}`, para que `FIXED_WAVES` no tape el resultado. Por cada uno de los 14 pares nuevos (10 en `STRICT`, 4 en `SAME_WAVE_OK`) y en los 3 entornos (42 casos), invertí la wave del consumidor. En todos sale la línea del par, y desaparece al quitar el par del set. Ningún par sobra.
- **Los dos pares descartados.** El codificador tenía razón en los dos:
  - `identity-jobs` solo trae CronJob, ServiceAccount y ConfigMap, sin ningún CR de Prometheus, así que no depende de `kube-prometheus-stack`.
  - `monitors.yaml` son 4 PodMonitor (keycloak, envoy-data-plane, envoy-ratelimit, valkey) y ninguno toca el Pushgateway.
- **Pares sostenidos con el código.** Comprobé en los fuentes:
  - `secretStoreRef vectra-store` en los ExternalSecret de valkey, keycloak y rate-limit;
  - `keycloak-db-rw.vectra-data.svc` como base de datos de Keycloak;
  - `PUSHGATEWAY_URL` en los dos CronJob.
- **Recurso repetido.** En una copia del árbol (scratchpad, ya borrada) probé dos duplicados reales:
  - el PodMonitor `keycloak/vectra-identity` repetido en el render de Keycloak lo detecta como `['identity-monitors','keycloak']`;
  - un ServiceMonitor puesto a la vez en el render de Valkey y en `monitors.yaml` también lo detecta.
  - Sin mutaciones, el resultado es `{}`.
- **`test_integration.py`.** Neutralicé las dos excepciones con monkeypatch y fallan las dos pruebas: `{'banco-ca'}` y `Sin CRD para gateway.networking.k8s.io/v1 HTTPRoute`. Las dos las exige el diff.
  - `banco-ca` solo lo usan `keycloak-tls` y `api-gateway` en staging y prod; kind no tiene ninguna referencia sin emisor.
  - La omisión del grupo solo salta los 7 HTTPRoute de U2, porque ningún documento de U1 es de ese grupo. Esos HTTPRoute los valida `kubeconform -strict` en `kubeconform-gateway`, que forma parte de `make -C identity-edge check`. No esconde ningún defecto.
- **`keycloak.rego` (M4).** Hice cuatro versiones flojas de la política: 512 Mi en todos los entornos, 768 Mi en kind, kind sin control y la política sin M4. Las cargué con un plugin de pytest que redirige `kd.POLICY`. Cada una pone en rojo los casos que le corresponden; con la política real, 15/15 pasan.
  - Render de staging o prod con 512 Mi: falla `resources`.
  - Render de staging o prod con 512 Mi y el hostname de kind: falla `issuer-per-environment`.
  - Ver F-01 para el caso que sí pasa la política.
- **Sin `syncPolicy.automated` y sin el eco de e2e.** `grep` sobre `apps/` y `components.yaml`: ninguna coincidencia de `automated`, `echo` ni `e2e`.
- **`generate.py` sin `--check`.** Lo corrí sobre una copia por `git archive`. `diff -r` sale vacío contra `envs/` y contra `apps/`. Quitar el `include` de `rate-limit` en la copia hace que `--check` dé exit 1.
- **Alcance.** En `identity-edge/` solo cambian los archivos de M4: values de kind, render de kind, `keycloak.rego` y `test_keycloak_deploy.py`. Plan, `audit.md` y `CANDIDATAS.md` vienen de commits del orquestador.

## Hallazgos
### F-01 · AMARILLO · identity-edge/keycloak/policy/keycloak.rego:345-349 · kind se reconoce por el hostname, no por el directorio
Un render de staging o prod que lleve a la vez el hostname de kind y `vectra-internal-ca` pasa los dos pases de conftest con 512 Mi: 806/806 y 9/9. Hoy lo frena `test_design_hostnames[env]`, que forma parte de `make check` y compara cada directorio con INF-U2-01. Es el mismo criterio que ya usa `set.rego` (`issuer-per-environment`), y el codificador lo dejó escrito en la bitácora. Si se quiere cerrar en la propia política, `policy-keycloak` puede pasarle el entorno a conftest con `--data`.

### F-02 · AMARILLO · platform/tests/test_waves.py:56-66 · faltan pares que el código sostiene
Hoy el orden es correcto, y `EXPECTED_WAVES` fija cada wave, así que no bloquea. Pero `STRICT` documenta «el CRD o el operador antes de quien lo usa», y estos pares no están:
- `keycloak→identity-jobs`: los CronJob montan los Secret `keycloak-reader-client` e `identity-ca`, que crean ExternalSecret de la Application `keycloak`, y llaman a `keycloak-admin`.
- `envoy-gateway→keycloak`: el render de Keycloak trae un `BackendTLSPolicy` `gateway.networking.k8s.io/v1`.
- `cert-manager→keycloak` y `cert-manager→api-gateway`: los dos traen un `Certificate`.
- `namespaces→identity-jobs`: los CronJob van en `vectra-identity`.

### F-03 · AMARILLO · platform/tests/test_platform.py:349 · la clave usa el namespace del manifiesto
Un recurso con namespace que no declare `metadata.namespace` toma `None`, cuando Argo CD le pondría el destino de su Application. Lo comprobé: el mismo PodMonitor sin namespace en `keycloak/rendered` no se detecta como duplicado. Hoy no hay ningún caso real, porque todos los manifiestos sin namespace son de cluster (Bundle, ClusterIssuer, GatewayClass y similares). El arreglo es usar `metadata.namespace` y, si falta, `destination.namespace` para los tipos con namespace.

### F-04 · AMARILLO · keycloak.rego:345 frente a set.rego:63 · el hostname de kind está escrito dos veces
`kind_public_hostname` repite `kind_hostname` de `set.rego` y una entrada de `public_hostnames`. Si cambia el hostname de kind, hay que tocarlo en tres sitios.

## Tareas candidatas (defectos reales fuera de alcance)
- `test_every_issuer_reference_exists` solo mira prod (`documents()`), y `EXTERNAL_ISSUERS` vale en cualquier entorno. Podría comprobarse por entorno, con `banco-ca` aceptado solo en staging y prod.
- `test_own_custom_resources_match_the_real_crds` podría cargar `gatewayapi-crds.yaml` de `.charts/envoy-gateway`, en lugar de omitir el grupo entero.
- El presupuesto de kind para U3 a U12 ya está en `CANDIDATAS.md`, con un margen de 0,027 GiB.

## Rutas de transcripciones
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/3934c8af-e6f2-4277-8f10-d98bb85d8e35/scratchpad/U02-T18-r3-rev/`:
- `U02-T18-r3-rev-ca1-3.log`
- `U02-T18-r3-rev-ca4-7.log`
- `U02-T18-r3-rev-ca5-6.log`
- `U02-T18-r3-rev-waves-mut.log`
- `U02-T18-r3-rev-dup.log`

Las copias (repo, gen, pol, kc, plug) ya están borradas. Solo quedan los logs y los scripts `dup.py`, `integ.py` y `waves_mut.py`.

```
VEREDICTO: VERDE
AMARILLO|identity-edge/keycloak/policy/keycloak.rego:345-349|kind se reconoce por el hostname, no por el directorio
AMARILLO|platform/tests/test_waves.py:56-66|faltan pares que el código sostiene
AMARILLO|platform/tests/test_platform.py:349|la clave usa el namespace del manifiesto
AMARILLO|keycloak.rego:345 frente a set.rego:63|el hostname de kind está escrito dos veces
INFORME: revisiones/U02-T18/ronda-3.md
```
