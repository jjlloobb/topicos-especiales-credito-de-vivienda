# Ronda 1 — U04-T08

VEREDICTO: VERDE (con un bloqueo de las demos fuera del cercado de la tarea)

Revisor, 2026-11-10, punta `3e63cdd`, base `2598732`. El revisor entregó el informe en su respuesta; el orquestador lo transcribe.

## Criterios (corridos por el revisor)

| # | Resultado |
|---|---|
| CA-1 | pasa: la imagen corre con usuario 65532, raíz de solo lectura, `cap_drop=ALL`, `no-new-privileges` y las 14 variables; Postgres migrado, MinIO con un paquete de U5 y JWKS en una red de Docker; `/healthz`, `/readyz` y `/metrics` en 200; `serving-config` con token 503 `dependency_unavailable`, sin token 401; sin `Traceback`. Rojo: `service.py` no existe en la base; sin variables, la imagen nueva falla con un `ConfigError` que nombra las 14 |
| CA-2 | 37 passed; los nombres coinciden con el `service.yaml` renderizado |
| CA-3 | 3 passed: registra un paquete real de U5 leído de MinIO; hilos de `Background` arrancan y se detienen; `pg_stat_activity` en 0 |
| CA-4 | 11 passed contra MinIO real; fuera del bucket → `FileNotFoundError`; caído → 503 `problem+json` |
| CA-5 | `make -C governance check` rc 0 (532 passed, cobertura 97,08 %); `make -C platform check` rc 0; `uv lock --check` rc 0; `--all` idéntico a la base |
| CA-6 | Paso 10 `[x]` con la nota |

Cobertura de los módulos nuevos: `s3_store.py` 98 %, `service.py` 95 %.

## Juicios

1. 503 en `serving-config` sin política activa es correcto (BR-U4-14, NFR-U4-04); `/readyz` en 200 con la copia cargada es coherente con NFR-U4-03 y P-U4-03.
2. **Falta en el chart la identidad del servicio (bloquea las cuatro demos):** el realm tiene el cliente `governance-service` (`client-jwt`, ES256, scopes `bias:compare` y `registry:append:governance`) y la bóveda lo siembra (`platform/kind/vault_paths.py:100-112`), pero `governance/chart` no monta la llave ni pone `VECTRA_CLIENT_ID`, `VECTRA_CLIENT_KEY_PATH`, `GOVERNANCE_REGISTRY_URL` ni `GOVERNANCE_BIAS_URL`. Sin la llave, toda transición queda `pendiente_registro`. Precedente en el mismo chart: el `ExternalSecret` del Job (`validation-job.yaml`).
3. Fallar al arrancar por falta de la llave tumbaría `serving-config`; el modo degradado es defendible pero hoy es silencioso.
4. Cliente S3 correcto (timeouts 1/5 s, CA solo con `https`).
5. Cambios en `api.py` y `k8s_jobs.py` legítimos.

## Hallazgos

- **F-01 · NARANJA** · `service.py:79-81,131-132`: `DEFAULT_REGISTRY_URL`, `DEFAULT_BIAS_URL`, `DEFAULT_CLIENT_KEY_PATH` y `client_id` por omisión: la misma clase de valores incrustados que la tarea cierra.
- **F-02 · NARANJA** · `service.py:146-153,201-205`: el modo degradado sin llave no tiene log ni prueba; la traducción `DependencyUnavailable` → `RegistryUnavailable` está sin cubrir.
- **F-03 · AMARILLO** · `service.py:134`: el token propio usa `GOVERNANCE_JOB_TOKEN_URL`, no el `VECTRA_TOKEN_URL` de U0 (`provider_from_env`).
- **F-04 · AMARILLO** · `s3_store.py:103-104`: `S3PackageStore.close()` no se llama en el `lifespan`.
