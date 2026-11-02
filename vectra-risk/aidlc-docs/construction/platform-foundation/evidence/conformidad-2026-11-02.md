# Conformidad de U1 con su diseño (2026-11-02)

Informe del revisor de conformidad (`opus`, solo lectura), guardado tal cual por el orquestador. El orquestador reprodujo N1. Pedido del usuario: «revisa la implementacion hasta ahora este de acuerdo al diseno».

---

# Revisión de conformidad de U1 `platform-foundation` con su diseño (rama `main`, 7bfb7ec)

No modifiqué nada: ni el repositorio, ni el clúster, ni Docker, y no usé red. Trabajé en un worktree desacoplado bajo el scratch, con copias de `platform/.tools/bin` y `platform/.charts`, y `UV_OFFLINE=1`. Ya lo eliminé (`git worktree list | grep -c design-u1` → 0). Entre `main` y `HEAD` no hay diferencias en los archivos de U1.

**Resumen:** todas las aceptaciones estáticas de los pasos `[x]` que se pueden correr sin clúster ni Docker pasan. Hay 1 hallazgo NARANJA y 4 AMARILLO. No hay ninguno ROJO.

## 1. Pasos del plan

| Paso | Artefactos | Aceptación (corrida aquí) | Resultado |
|---|---|---|---|
| 1 Esqueleto | Makefile, `.github/pull_request_template.md` (sección `## Rollback`), `apps/kind/root.yaml` | `test -f …root.yaml` y `make check` desglosado | OK |
| 2 kind | `kind/cluster.yaml` (2 workers), `cluster-ha.yaml` (4), `encryption-config.example.yaml` | `test_kind_config` en `test_platform.py` | OK. Ver A4: el texto del paso dice que `cluster.yaml` tiene 4 workers |
| 3 Flujos | `flows.yaml`, `generate.py`, `generated/{kind,staging,prod}` | `generate.py --check` → 0; `pytest platform/network/tests` (dentro de los 610) | OK. Los 16 archivos de NetworkPolicy de prod tienen `deny-all`; el 17.º es `connectivity-suite.yaml` |
| 4 Linkerd y cert-manager | `mesh/*.yaml` | pytest (`test_mesh_and_certificates`, `test_upstream_charts`) | OK: `controllerReplicas: 3`, `cniEnabled: true` |
| 5 Kyverno y PSA | `policies/kyverno/*`, `namespaces/`, `rbac/verification-operator/k16.yaml` | `kyverno test platform/policies/kyverno` → 67 pasaron, 0 fallaron; `rego_fixtures.py` → 10 reglas, cada una con su caso bueno y su caso malo | OK |
| 6 Cuotas y prioridades | `policies/quotas/*`, `priority-classes.yaml` | `quotas/render.py --check` → 0; pytest | OK |
| 7 CloudNativePG | `data/chart` | `helm lint` y pytest `test_postgres_clusters` | OK, salvo `sslmode` (N1) |
| 8 MinIO | `data/minio/*` | pytest `test_upstream_charts` | OK. `tests/ilm_idempotente.sh` **requiere Docker**: no lo corrí |
| 9 ESO y Vault | `secrets/*` | pytest RBAC de ESO; ningún `kind: Secret` en gitops ni en `rendered/` | OK |
| 10 Observabilidad | `observability/*` | pytest; `test_grafana_folder_permissions.py` **requiere Docker** (Testcontainers): no lo corrí | OK, sin esa prueba |
| 11 Reglas y runbooks | `rules/*`, `runbooks/*` | `promtool test rules` → SUCCESS; `promtool check rules` → 33 reglas; `test_runbooks.py` → 56 alertas en regla | OK |
| 12 Dashboards | `dashboards/*.json` | pytest | OK |
| 13 restore-drill | `restore-drill/*` | pytest `restore-drill/tests` | OK |
| 14 Runbooks de operación | `install.md`, `zone-failover.md`, `site-restore.md`, `trust-anchor-rotation.md` | `test_runbooks.py --operational` → 4 | OK |
| 15 GitOps | `vectra-risk-gitops/apps/*` | `test_waves.py` (kind 41, staging 40, prod 38, en orden); `conftest apps/prod` → 273 de 273; `kyverno apply disallow-argocd-auto-sync` → kind 41, staging 40 y prod 38 pass, 0 fail | OK. `automated` solo aparece en el README |
| 16 Render | `rendered/*` | `render.sh` y luego `git status --porcelain rendered/` vacío; `conftest rendered/prod` → 700 de 700; `--namespace hpa` → 3 de 3 | OK |
| 17 CI | `.github/workflows/*` | `actionlint` → 0; `grep -l secrets.KUBECONFIG` → nada; los 5 reutilizables tienen `runs-on: ${{ inputs.runner }}` | OK |
| 18 Trazabilidad | `code/README.md` | `test_traceability.py` → 54 identificadores | OK |
| 19 y 20 kind | evidencia | **Requiere clúster.** Acotados en `cierre-acotado.md` | No re-verificados |
| 21 Carga | — | `grep NFR-U1-11 system-verification…plan.md` → OK | OK, diferido a U12 |
| 22 N/A | — | `test ! -d migrations && test ! -d frontend` | OK |
| 23 Cierre | — | Lo de `make check` desglosado: ruff OK, `generate.py --check` de red y gitops OK, pytest **610 pasaron** (sin la prueba de Grafana con Docker), `test_links.py` (111 archivos sin enlaces rotos), `check-integration` → pass 239, fail 0 | OK sin Docker |

## 2. Muestreo de requisitos de alto riesgo (verificado en manifiestos)

- **NFR-U1-02 y 05 (PostgreSQL):** en `rendered/prod/data.yaml`, los 4 `Cluster` cumplen: 3 instancias, sync 1/2, `syncReplicaElectionConstraint` por zona, `archive_timeout: 60s`, `retentionPolicy: 30d` y 8 `ScheduledBackup`.
- **NFR-U1-23 (cifrado de backups):** `encryption: AES256` en el WAL y en los datos.
- **NFR-U1-20 (red):** `deny-all` en todos los namespaces generados.
- **NFR-U1-34 (salida de observabilidad):** los únicos `ipBlock` de `vectra-observability` son F72, F119 (kubelet) y K02, K03 y K13 (API).
- **NFR-U1-30 y 31 (retención):** Loki con `retention_enabled: false`; Prometheus `30d` y `remoteWrite: []`; Tempo `168h`; MinIO con lock de 90 días en `loki` y lifecycle de 7 días en `tempo`.
- **P-U1-13 (Pushgateway):** un `HTTPRoute` por identidad y método (`restore-drill`, `realm-drift`, `signing-key-age`, `grafana-folder-check`, `bias-monitoring-job`, Prometheus) y sin `--web.enable-admin-api`.
- **P-U1-06 (Kyverno en HA):** el admission controller tiene 3 réplicas.
- **P-U1-07 (Watchdog):** la ruta de Alertmanager hacia `banco` repite cada `5m`.
- **NFR-U1-41, 43 y 44 (cambios y CI):** verificados con las aceptaciones de los Pasos 15 y 17 y con la plantilla de PR.

## 3. Los seis cambios del loop (U01-T01 a T06) frente al diseño

- **T01 (`GF_PLUGINS_PREINSTALL_DISABLED`):** es coherente con NFR-U1-34; no contradice nada.
- **T02 (`ilm rule rm --all --force … || true` antes de cada `add`, en `values.yaml` y `values-kind.yaml`):** es coherente con INF-U1-03 y NFR-U1-30 (90 días en `loki`, 7 en `tempo`). `cierre-acotado.md` quedó desactualizado (A3).
- **T03 (F130):** está en `component-dependency.md` (línea 154) y en `flows.yaml`. Se generaron la NetworkPolicy de entrada y de salida y el `Server` más `AuthorizationPolicy` mTLS de Linkerd, en 8080 y 3000, como pide P-U1-02. Las listas de flujos de U1 no lo recogen (A2).
- **T04 (prueba de `seed-vault.sh`):** el port-forward a Grafana es un arranque solo de kind y ya existía antes del PR 19. No choca con P-U1-10, que prohíbe el port-forward para crear silencios, no para esto.
- **T05 (`WalArchiveStale`):** la regla nueva contradice la definición del diseño (A1).
- **T06 (reintentos):** son 3 intentos (`ATTEMPTS = 3`) solo ante tiempo agotado; un 4xx no se reintenta. Los POST de carpeta y de equipo toleran 409, así que reintentar es seguro. No contradice INF-U1-07.

## 4. Hallazgos

### N1 — NARANJA: no se exige TLS de PostgreSQL ni hay prueba de `sslmode`
- **Archivos:** `vectra-risk/platform/data/chart/templates/clusters.yaml`, `vectra-risk/platform/tests/test_platform.py::test_postgres_clusters`, `vectra-risk/platform/restore-drill/drill.py:135`.
- **Diseño:** NFR-U1-22 pide `sslmode=verify-full`, y la aceptación del Paso 7 incluye «`sslmode` exigido». El Paso 7 está marcado `[x]`.
- **Evidencia:**
  - `grep -rn -i 'sslmode|hostssl|pg_hba' platform vectra-risk-gitops` solo encuentra `drill.py:135 sslmode="require"`, una aserción de `test_drill.py` (`== "require"`) y un comentario en `mesh/certificates.yaml`.
  - El render solo tiene `ssl_min_protocol_version: TLSv1.2` y `serverTLSSecret` y `serverCASecret`; no hay reglas `pg_hba`.
  - `test_postgres_clusters` no comprueba nada de SSL.
- **Verificado:** no hay manifiesto ni prueba que exijan `sslmode`. El simulacro usa `require`, que no verifica el certificado.
- **Inferido, sin comprobar:** el `pg_hba` por defecto de CloudNativePG admite `host` sin TLS. El mTLS de Linkerd en 5432 lo atenúa para los pods mallados, pero no cumple lo literal del NFR.

### A1 — AMARILLO: el diseño de `WalArchiveStale` quedó atrás del cambio U01-T05
- **Archivos:** `vectra-risk/platform/observability/rules/platform-rules.yaml:24` (y su `.prometheusrule.yaml`, que coincide).
- **Diseño:** `nfr-design/logical-components.md` §3 dice «(> 5 min con segmentos pendientes)», y NFR-U1-05 «si el último WAL archivado tiene más de 5 min».
- **Evidencia:** la regla es `… or (increase(cnpg_pg_stat_archiver_failed_count[5m]) > 0)` con SEV1. El runbook sí está al día.
- **Nota:** ya está en `CANDIDATAS.md` («…actualizar el diseño de U1»). Lo menciono solo porque el diseño todavía no lo refleja.

### A2 — AMARILLO: F130 (y F122 a F129) no aparecen en las listas de flujos de U1; los rangos del diseño dicen F01–F124
- **Archivos:** `vectra-risk/aidlc-docs/inception/application-design/unit-of-work.md:43`, `nfr-design/nfr-design-patterns.md` P-U1-01 («hoy F01–F124»), el plan (§1 y Paso 3) y `application-design.md:7`.
- **Evidencia:**
  - `unit-of-work.md:43` dice «F45, F60–F67, F70–F72, F74–F76, F80–F88 …, F113–F116, F118–F121».
  - `grep -rn 'F129|F130'` fuera de `component-dependency.md` no da resultados.
- **Impacto:** solo documental. La prueba de completitud extrae los identificadores del Markdown, así que F130 está cubierto en el código.

### A3 — AMARILLO: `cierre-acotado.md` quedó desactualizado tras U01-T01, T02 y T06
- **Archivo:** `vectra-risk/aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md`.
- **Evidencia:**
  - La fila «Regla `ilm` repetida | Se acumula, sin corregir» no refleja el `rm --all` previo que ya está en ambos `values`.
  - La fila de `grafana-folder-check` sigue diciendo «intenta instalar plugins de Internet» y no menciona los reintentos.
- **Matiz:** ninguno de los tres cambios está comprobado en kind. La imagen de `folder_permissions` no se ha republicado, algo que ya está en `CANDIDATAS.md`. Falta anotar que hay corrección en código pendiente de verificar, no marcarlo como cerrado.

### A4 — AMARILLO: INF-U1-01 e INF-U1-03 no reflejan el perfil liviano de kind
- **Archivos:** `vectra-risk/platform/kind/cluster.yaml` (2 workers), `vectra-risk/platform/data/minio/values-kind.yaml` (`replicas: 1`), `vectra-risk/platform/rendered/kind/data.yaml` (`instances: 1` ×4).
- **Diseño:**
  - INF-U1-01 dice «kind | workers | 4 (2 en zone-a, 2 en zone-b)».
  - INF-U1-03 dice «En kind, 4 pods sobre los 4 workers, con volúmenes local-path».
  - El Paso 2 pide que `cluster.yaml` tenga 4 workers, pero `test_kind_config` comprueba los 4 en `cluster-ha.yaml`.
- **Nota:** está documentado en el plan §6 (2026-11-01, anterior al loop), pero no en el Infrastructure Design.

### Ya registrado, no lo cuento como hallazgo
- El backup mensual no lleva el prefijo `monthly/` (plan §5, «Por confirmar»).
- K11 y ESO; MinIO archivado (issue 26).
- El failover de zona, X01–X10 y `Watchdog` (`cierre-acotado.md`).
- Las salidas a Internet que le quedan a Grafana, la falta de pruebas del contenido de `ilm` y los reintentos de `push_metric` (`CANDIDATAS.md`).

### Sin correr (requieren Docker o clúster)
- `platform/data/minio/tests/ilm_idempotente.sh` (Docker).
- `platform/tests/test_grafana_folder_permissions.py` (Docker).
- Pasos 19 y 20 (clúster).

## 5. Resumen por hallazgo

NARANJA|vectra-risk/platform/data/chart/templates/clusters.yaml|NFR-U1-22; Plan Paso 7 («sslmode exigido»)|Ningún pg_hba/hostssl ni prueba exige sslmode; restore-drill usa sslmode=require, no verify-full; Paso 7 marcado [x] sin esa comprobación
AMARILLO|vectra-risk/aidlc-docs/construction/platform-foundation/nfr-design/logical-components.md|NFR-U1-05; logical-components §3 WalArchiveStale|La regla ahora también dispara con increase(failed_count[5m])>0; el diseño sigue diciendo «>5 min con segmentos pendientes» (ya en CANDIDATAS)
AMARILLO|vectra-risk/aidlc-docs/inception/application-design/unit-of-work.md|P-U1-01 («hoy F01–F124»); unit-of-work U1 Flujos|F130 (U01-T03) y F122–F129 no figuran en las listas ni en los rangos de flujos de U1
AMARILLO|vectra-risk/aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md|Cierre acotado, filas «Regla ilm repetida» y «grafana-folder-check»|Siguen «sin corregir» tras U01-T01/T02/T06; deberían decir «corregido en código, sin verificar en kind»
AMARILLO|vectra-risk/aidlc-docs/construction/platform-foundation/infrastructure-design/infrastructure-design.md|INF-U1-01, INF-U1-03; Plan Paso 2|El diseño describe kind con 4 workers y 4 pods de MinIO; lo implementado es el perfil liviano (2 workers, PG y MinIO de 1 réplica)

CONFORMIDAD U1: CONFORME
