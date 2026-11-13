# `bias-monitoring` — resumen del CronJob y del servicio (U9, Pasos 8 a 10)

Una sola imagen con dos puntos de entrada (P-U9-05): `python -m vectra_bias.run` (CronJob) y `python -m vectra_bias.app` (servicio).
La librería `vectra_disparity` está resumida en `library.md`. Código en `bias-monitoring/src/vectra_bias/`.

## Módulos

| Módulo | Proceso | Qué hace | Diseño |
|---|---|---|---|
| `config` | los dos | Constantes (timeouts, caché, razón de inválidas) y `load_policy` (los cinco parámetros del `ConfigMap`) | INF-U9-03; P-U9-02 |
| `window` | los dos | Ventana de cada versión: inicio tras la última `reactivar` (puro) | BR-U9-08, 15 |
| `freeze_rule` | CronJob | Regla R4 sobre todos los atributos (puro) | BR-U9-11 |
| `context` | los dos | Resultado de disparidad de U0, tasa de apartamiento y paquete de contexto (puro) | BR-U9-14, 15; P-U9-04 |
| `registry_client` | los dos | `GET monitoring/freezes` y `POST monitoring/daily:query` de U3; `route_path` toma las rutas de `REGISTRY` de U0 | BR-U9-07, 09 |
| `freeze_client` | **solo CronJob** | `POST /v1/models/{id}/freeze` con reintentos | BR-U9-12; P-U9-02 |
| `publish` | CronJob | Métricas al Pushgateway (grupos `run`, `success` y `freeze-<v>`) | BR-U9-20 |
| `run` | CronJob | Una corrida completa (`python -m vectra_bias.run`) | P-U9-01, 07 |
| `dashboard` | servicio | `get_disparity`: versión, ventana, `model` y `human` separadas, `disclaimer` | BR-U9-18; US-307 |
| `freezes` | servicio | `list_freezes` (`FreezeSummary`) y `get_freeze` (`FreezeRecord`) | BR-U9-19; US-304 |
| `compare` | servicio | `compare_source`: `PrePostReport` con `delta` y recorte a 48 KiB | BR-U9-17; US-306 |
| `cache` | servicio | LRU de 64 entradas y 15 min con *single-flight* | P-U9-03; NFR-U9-02 |
| `app` | servicio | `config_from_env`, `build_app` y `main` (`python -m vectra_bias.app`) | P-U9-05 |

El servicio no importa `freeze_client` ni `run`: lo exigen el contrato `servicio-no-congela` de `.importlinter` y
`tests/integration/test_entrypoint.py` (`python -X importtime -m vectra_bias.app` no nombra esos dos módulos).

## Rutas y roles del servicio (`bias-monitoring-service`, puerto 8080)

Las rutas y sus roles y scopes salen de `REGISTRY["bias-monitoring-service"]` de U0 (`create_app` los aplica); ningún módulo de
`vectra_bias` escribe una ruta del contrato o un scope como literal. Los handlers se registran con las llaves `(método, ruta)` del contrato.

| Ruta | Quién | Respuesta |
|---|---|---|
| `GET /v1/disparity` (`version`, `attribute`, `window` = 7, 30 o 90) | `cro`, `cumplimiento` | `DisparityView` con `disclaimer = "mide y alerta, no certifica"` |
| `GET /v1/freezes` | `cro`, `cumplimiento` | `list[FreezeSummary]` con la resolución **más reciente** |
| `GET /v1/freezes/{id}` | `cumplimiento` | `FreezeRecord` de U0 tal como lo guardó el registro (404 `not_found` si no existe) |
| `POST /v1/source-comparisons` (≤ 64 KiB) | scope `bias:compare` (`governance-service`) | `PrePostReport` (≤ 48 KiB canónico, `truncated`), con `disclaimer` |

Con el registro caído o el circuito abierto, el dashboard y los congelamientos responden 503 `dependency_unavailable`, sin datos parciales.
`/healthz` y `/readyz` (8081) solo miran el proceso (NFR-U9-12): los pods quedan `Ready` aunque el registro esté caído.

## Variables de entorno de los dos puntos de entrada

El chart del Paso 12 (U09-T04) debe poner en el `Deployment` las variables del servicio y montar el `ConfigMap` en `config.POLICY_PATH`; conviene que
su criterio compare los nombres con `app.REQUIRED`, como el de `governance` (U04-T08).

| Variable | `run` (CronJob) | `app` (servicio) |
|---|---|---|
| `VECTRA_REGISTRY_URL` | obligatoria | obligatoria |
| `VECTRA_TOKEN_URL`, `VECTRA_ASSERTION_AUDIENCE` (emisor público, `keycloak.issuer`; U00-T04), `VECTRA_CLIENT_ID`, `VECTRA_CLIENT_KEY_PATH` | obligatorias (cliente `bias-monitoring-job`) | obligatorias (cliente `bias-monitoring-service`) |
| `VECTRA_CLIENT_KEY_ID` | opcional | opcional |
| `VECTRA_GOVERNANCE_URL`, `VECTRA_PUSHGATEWAY_URL` | obligatorias | no las usa |
| `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL` | no las usa | obligatorias (validación de tokens de entrada, U0) |
| `VECTRA_CA_BUNDLE` | con `https` | obligatoria si alguna URL es `https`; el arranque falla nombrándola |
| `VECTRA_POLICY_PATH` | opcional (por omisión `config.POLICY_PATH`) | opcional (ídem) |

Si falta una obligatoria, `app` termina con código 2 y un mensaje que la nombra (sin sus valores); una política fuera de rango detiene el arranque
(`config.load_policy`). El servicio no tiene parámetros de puerto: 8080 (contrato) y 8081 (`/metrics`, `/healthz`, `/readyz`) vienen de U0, y el apagado
espera ≤ 10 s (`GRACEFUL_SHUTDOWN`). El `preStop` de 5 s es un campo del `Deployment` (Paso 12).

## Caché del dashboard (P-U9-03; NFR-U9-02)

- LRU de `config.CACHE_ENTRIES` (64) y `config.CACHE_TTL_S` (15 min), por réplica; solo guarda la respuesta ya suprimida (P-U9-04).
- Llave `(versión, atributo, ventana)`. **Sin `version` la llave lleva `None`** («sin versión»): resolver la versión más reciente exige leer el registro,
  que es lo que el *single-flight* evita repetir. La respuesta cacheada ya resolvió la versión y dura a lo más 15 min.
- *Single-flight*: con la misma llave y sin entrada, una sola lectura del registro; las demás esperan su resultado o su error. Un error no se guarda.
- Cada consulta, también la servida desde la caché, emite `disparity.viewed` con el `principal_subject` del que consulta (NFR-U9-32).
- Métricas en el registro de U0 (`vectra_common.metrics.REGISTRY`), sin identificadores en las etiquetas (NFR-U9-41):
  `vectra_bias_cache_lookups_total{result="hit|miss|coalesced"}` y `vectra_bias_cache_entries` (sin etiquetas). Las etiquetas del servicio son las de U0
  (`service`, `route_template`, `method`, `status`, `code`, `dependency`, `event`) más `result` de la caché; ninguna lleva `model_version_id`, `freeze_id`, `source_id` ni `principal_*`.
- NFR-U9-02 (p95 ≤ 500 ms con la caché) se traza en `cache.py`; su **medición con k6** sigue en el Paso 14 (T3, `demo-recorte-funcional.md` §3 U9, fila «14»), así que no va en «Diferido por la demo».

## Lo que el servicio interpreta (U09-T03)

- «Toda respuesta lleva `disclaimer`» se lee como en la BLM §3: va en `DisparityView` y en `PrePostReport`; `FreezeSummary` y `FreezeRecord` de U0 no tienen el campo. El lint de frases prohibidas cubre las cuatro respuestas.
- El dashboard aplica el inicio de ventana de BR-U9-08 y por eso lee también `monitoring/freezes`; sin `window` usa `window_days` de la política.
- `invalid_entries` = suma de `RangeTotals.invalid_entries` de los rangos de la consulta, sin `unattributable_range`.
- `compare` rechaza además una celda repetida (`duplicate_cell`) con 422; `PrePostReport.pre` y `.post` llevan `model_version_id` «pre» y «post» y una ventana de 1970 porque `DisparityResult` los exige y una fuente no tiene versión ni ventana.

## Cobertura (NFR-U9-50)

Ramas, con `pytest-cov --cov-branch` (`make -C bias-monitoring coverage-bias`: los dos comandos de CA-5). Exigido: 100 % en `freeze_rule`, `context` y `window`, y ≥ 95 % en el resto de `vectra_bias`.

| Módulo | Sentencias | Ramas | Cobertura de partida (`main`, perfil `dev`) | Cobertura final (perfil `ci`) |
|---|---|---|---|---|
| `app` | 91 | 4 | sin código | 100 % |
| `cache` | 61 | 14 | sin código | 100 % |
| `compare` | 58 | 20 | sin código | 100 % |
| `dashboard` | 59 | 6 | sin código | 100 % |
| `freezes` | 22 | 4 | sin código | 100 % |
| `config` | 106 | 26 | 98 % | 100 % |
| `context` | 54 | 14 | 93 % | **100 %** |
| `freeze_client` | 49 | 10 | 98 % | 100 % |
| `freeze_rule` | 32 | 6 | 100 % | **100 %** |
| `publish` | 165 | 52 | 98 % | 100 % |
| `registry_client` | 45 | 4 | 90 % | 100 % |
| `run` | 233 | 54 | 88 % | 99 % (queda la rama `141->138`: el bucle de reintentos del token siempre sale por `break` o `raise`) |
| `window` | 43 | 10 | 98 % | **100 %** |
| **Total `vectra_bias`** | 1 018 | 224 | 94 % | **99,92 %** (exigido ≥ 95 %) |

Las ramas que faltaban en los módulos del Bloque C (`context`, `window`, `config`, `registry_client`, `freeze_client`, `publish`, `run`) se cubren con pruebas nuevas
(`tests/unit/test_pure_gaps.py`, `tests/integration/test_gaps.py`); ningún módulo cambió de comportamiento por ellas. El `if __name__ == "__main__":` de los dos puntos de entrada se
excluye de la medición en `coveragerc` (lo recorren las pruebas de subproceso, que `pytest-cov` no mide).

`coverage-bias` repite las pruebas de `test` y `property` (la cobertura de ramas se mide sobre una sola corrida de todas ellas) y excluye la simulación, que tiene su objetivo.
La librería `vectra_disparity` se mide aparte (`coverage`, 100 %).

## Semillas

Las PBT corren con el perfil `ci` (500 ejemplos) y la semilla de la corrida: `tests/conftest.py` la imprime en la cabecera (`hypothesis seed: N`) y se repite con `HYPOTHESIS_SEED=N`
o `--hypothesis-seed=N`. La simulación estadística usa semilla fija (`library.md`).

## Diferido por la demo

- `mutmut` en `freeze_rule`: T3 (`demo-recorte-funcional.md` §3 U9, fila «5 · 10 Resúmenes»: «Sin `mutmut`»; §2 regla 3). La dependencia está instalada, no se corre.
- k6 y la medición de NFR-U9-02: Paso 14, T3 (§3 U9, fila «14»).
- Dockerfile, chart, `ConfigMap`, `preStop`, `ServiceMonitor` y Application (Pasos 11, 12 y 14): U09-T04. Alertas y workflow (Pasos 13 y 15): D.
