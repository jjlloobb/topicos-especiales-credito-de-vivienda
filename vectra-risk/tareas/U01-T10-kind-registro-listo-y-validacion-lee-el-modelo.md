# U01-T10 — kind: el registro queda listo, la validación lee el modelo, hay métricas para los HPA y la bóveda reserva memoria

**Unidad:** U1 — `platform-foundation`
**Historias que implementa:** ninguna nueva; cierra cuatro defectos de integración que impiden la demo en kind (auditoría entre unidades del 2026-11-14).
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> Cinco cambios en `platform/`, todos para que el sistema completo arranque en kind:
>
> 1. **`registry-db` con réplica síncrona en kind.** El `/readyz` de `decision-registry-service` exige al menos un standby síncrono transmitiendo (`decision-registry/src/vectra_registry/health.py:31-33,57-66`) y su pool `projections` lee de `registry-db-ro` (`decision-registry/chart/values.yaml:17`). En kind todos los clusters tienen `instances: 1` (`platform/data/chart/values-kind.yaml:6`), así que el registro nunca queda listo. Decisión del usuario (2026-11-14): **`registry-db` pasa a 2 instancias con `minSyncReplicas: 1` solo en kind**; `case-db`, `governance-db` y `keycloak-db` siguen en 1. Staging y prod no cambian.
> 2. **`validation-readonly` puede leer `model-store`.** El Job de validación de U4 lee del `model-store` el manifiesto, el explicador, el spec, la envolvente y el artefacto (`governance/validation_job/vectra_validation/run.py:58-63`) con el usuario `validation-readonly`, cuya política `validation-read` solo cubre `validation-datasets` (`platform/data/minio/values.yaml:41,52` y `values-kind.yaml:22,41`). La política pasa a cubrir también lectura (`s3:GetObject`, `s3:ListBucket`) de `model-store`, en los dos archivos.
> 3. **metrics-server en kind.** No hay ninguno (`components.yaml`, `install.md`) y hay HPA en nueve workloads. Se añade como Application de kind en la wave que corresponda, por digest, con lo que kind necesite para hablar con el kubelet, cumpliendo las políticas de Kyverno. Si exige descargar una imagen que no está en la máquina, **para y pregunta** (las descargas las autoriza el usuario).
> 4. **La bóveda de kind reserva memoria.** `platform/operators/vault-kind.yaml` no declara `resources`: es BestEffort y lo primero que mata el OOM, y al reiniciarse pierde todo. Requests y limits de memoria y CPU medidos o justificados.
> 5. **Runbook «Vault reiniciado» completo** (`platform/runbooks/install.md`), con lo medido el 2026-11-14 (ver «Notas») y un apartado «Tras reiniciar la máquina».
>
> `BUDGET_GIB` y `platform/tests/test_kind_profile.py` se ponen al día con la instancia nueva, y la prueba deja de contar de menos (ver CA-5).

**Fuera** (recházalo aunque lo veas roto):

- Los recortes de memoria y CPU de kind (quitar Tempo, Loki y Alloy; Keycloak en una réplica; CPU de los proxies): son otra tarea.
- La entrada por el gateway desde la máquina (`vectra.localtest.me`, `cloud-provider-kind`) y las imágenes de `envoy-gateway` y `ratelimit`: otra tarea.
- Cualquier cambio en `decision-registry/`, `governance/` o `reference-model/` (U3, U4, U5). El `datasetRef` de U4 lo arregla U04-T10.
- Cambiar la bóveda de kind a almacenamiento en archivo: va a `CANDIDATAS.md`.
- Staging y prod, salvo el punto 2 (la política de MinIO es la misma en los tres).

---

## Archivos de contexto

- `platform/data/chart/` (`values.yaml`, `values-kind.yaml`, `templates/clusters.yaml`), `platform/data/minio/values.yaml` y `values-kind.yaml`
- `platform/operators/vault-kind.yaml`, `platform/runbooks/install.md`, `platform/kind/seed-vault.sh`, `platform/kind/vault_paths.py`
- `platform/tests/test_kind_profile.py`, `platform/tests/test_upstream_charts.py`, `platform/Makefile`
- `vectra-risk-gitops/` (`components.yaml`, `generate.py`, `apps/kind`, `values/kind`), `platform/policies/kyverno/`
- `DECISIONES-LOOP.md` §7 (presupuesto de memoria), `CANDIDATAS.md`
- `decision-registry/src/vectra_registry/health.py` y `governance/validation_job/vectra_validation/run.py` (solo lectura: son la razón del cambio)

---

## Criterios de aceptación

- [ ] **CA-1** — En kind, `registry-db` renderiza con 2 instancias y `minSyncReplicas: 1`; los otros tres clusters, con 1 y sin `minSyncReplicas`; staging y prod, igual que antes.
  ```bash
  cd vectra-risk && uv run pytest platform/tests/test_kind_profile.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib
  helm template data platform/data/chart -f vectra-risk-gitops/envs/kind/values.yaml -f platform/data/chart/values-kind.yaml | grep -E 'name: (registry|case|governance|keycloak)-db$|instances:|minSyncReplicas'
  ```
  Esperado: las pruebas pasan, con una prueba nueva que fija ese reparto; el `grep` lo muestra. El Service `registry-db-ro` tiene una instancia detrás (dilo con la evidencia que el render permita).

- [ ] **CA-2** — La política que usa `validation-readonly` permite `s3:GetObject` y `s3:ListBucket` sobre `model-store` y sobre `validation-datasets`, en base y en kind, y no permite escribir en ninguno.
  ```bash
  cd vectra-risk && uv run pytest platform/tests/test_upstream_charts.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib -k minio
  ```
  Esperado: pasa, con una prueba nueva que lee la política del render (base y kind) y falla si se quita `model-store` o si aparece una acción de escritura.

- [ ] **CA-3** — metrics-server existe como Application de kind, por digest, y su render cumple las políticas de Kyverno; `generate.py --check` y `test_waves.py` pasan.
  ```bash
  cd vectra-risk && uv run python vectra-risk-gitops/generate.py --check && uv run python platform/tests/test_waves.py
  ```
  Esperado: rc 0 y `kind: <n+1> Applications en orden`. La bitácora trae el resultado de las políticas de Kyverno sobre su render.

- [ ] **CA-4** — La bóveda de kind declara requests y limits.
  ```bash
  cd vectra-risk && grep -n -A6 'resources' platform/operators/vault-kind.yaml
  ```
  Esperado: memoria y CPU en requests y limits; la bitácora dice de dónde salen las cifras (el pod usa ≈ 150 MiB medidos el 2026-11-14).

- [ ] **CA-5** — El presupuesto de memoria de kind cuenta la instancia nueva, las réplicas mínimas de los HPA de los StatefulSet (hoy Keycloak cuenta 1 y su HPA pide 2), metrics-server y la bóveda; `BUDGET_GIB` es la cifra medida.
  ```bash
  cd vectra-risk && uv run pytest platform/tests/test_kind_profile.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib -k budget
  ```
  Esperado: pasa. Si la cifra real supera lo que cabe en la máquina (15 GiB, con ≈ 7,6 GiB ya usados por la plataforma), **no la disimules**: fija `BUDGET_GIB` en lo medido, anótalo en la bitácora y devuélvelo como pregunta; los recortes son otra tarea.

- [ ] **CA-6** — El runbook cubre el reinicio de la bóveda y el de la máquina con lo medido, y pasa sus comprobadores.
  ```bash
  cd vectra-risk && uv run python platform/tests/test_runbooks.py --operational && uv run python platform/tests/test_links.py
  ```
  Esperado: rc 0. El runbook dice, en orden: límites de inotify; recrear los pods con malla; resiembra; claves de MinIO (el Job del chart no cambia la clave de un usuario existente); Tempo y Loki; Grafana (clave de `admin`, token, `grafana-config`); identidad (Keycloak), marcado como **no medido**.

- [ ] **CA-7** — Todo `platform` sigue en verde.
  ```bash
  cd vectra-risk && make -C platform check-local
  ```
  Esperado: rc 0.

---

## Plan de pruebas

- Prueba del reparto de instancias por cluster y entorno (CA-1).
- Prueba de la política de MinIO de la validación, positiva y negativa (CA-2).
- Prueba del presupuesto que cuenta las réplicas mínimas de los HPA (CA-5).

**Rojo primero:** cada prueba nueva se ve fallar contra `main` antes del cambio; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`**, ni con `kubectl` ni con `argocd`. No levantes contenedores salvo que una prueba existente de `platform` lo haga. La máquina tiene poca memoria libre.
- Se modifican en su sitio los archivos citados; nada de duplicados con sufijo.
- Lo medido el 2026-11-14 en `kind-vectra`, para el runbook (no lo amplíes con suposiciones):
  1. `fs.inotify.max_user_instances` era 128; `linkerd-cni` fallaba en los workers con `couldn't initialize inotify: too many open files`. Con 1024 (y `max_user_watches` 1048576, persistente en `/etc/sysctl.d/`) arrancó.
  2. Los pods con malla creados antes no se recuperan solos (`linkerd-network-validator`: «Failed to validate networking configuration»): hubo que borrarlos, primero `linkerd`, luego `vectra-data`, luego `vectra-observability`.
  3. `seed-vault.sh` y `seed-vault.sh identity` devolvieron los `ExternalSecret` a sincronizados, con claves nuevas.
  4. `argocd app sync minio` terminó bien y no cambió nada: el Job `minio-post-job` solo crea un usuario si no existe («User already exists»). Tempo siguió en `CrashLoopBackOff` («signature does not match») y Loki con 403. Se arregló con un Job de una sola vez que corre el script `add-user` del chart forzando `mc admin user add` para los 12 usuarios, con `priorityClassName: vectra-normal`; después, reiniciar los pods de Tempo. Decide si el runbook lleva ese Job como manifiesto versionado o como procedimiento, y dilo.
  5. Grafana: la clave de `admin` del Secret daba 401; `grafana cli admin reset-admin-password`, luego `seed-vault.sh grafana-token` y `argocd app sync grafana-config`. (El límite de 256 MiB que lo impedía ya se corrigió en `main`.)
  6. `cloud-provider-kind` se lanza con `--rm` y no sobrevive al reinicio de la máquina: el runbook debe decir que hay que volver a lanzarlo.
  7. Keycloak no estaba instalado: lo que haga falta tras `seed-vault.sh identity` (clave de `keycloak-admin`, llaves de cliente, `keycloak-config-cli`) **no está medido**; el runbook lo dice así.
- Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
