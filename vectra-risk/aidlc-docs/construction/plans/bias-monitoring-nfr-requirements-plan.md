# Plan de NFR Requirements — U9 `bias-monitoring`

**Alcance:** requisitos no funcionales y stack de los tres procesos de U9 y de su librería,
sobre el Functional Design aprobado (BR-U9-01..22, PBT-U9-01..08):
- el CronJob de cálculo (cliente `bias-monitoring-job`), que es el único que congela;
- el servicio HTTP `bias-monitoring-service` (dashboard, congelamientos y `compare_source`);
- la librería `vectra_disparity`, que también usan U4 y U5.

**Ya decidido** (no se pregunta):
- **Stack común:** Python 3.12, FastAPI, Pydantic v2, `vectra_common` (`create_app`, `deps.call` con timeout obligatorio y circuit breaker), `vectra_contracts` (tipos de U0 §9.4), Hypothesis (U0).
- **Funcionamiento:**
  - una corrida cada 15 min, todo o nada, con ventana de 30 días por versión;
  - congela si la agregada supera 5 pp y el límite inferior es > 0;
  - 3 reintentos de `freeze` y `BiasFreezeFailed`;
  - W = 1 h (SEV2) y 2W (SEV1) (FD).
- **Lecturas del registro:** solo conteos agregados (`POST /v1/monitoring/daily:query` y `GET /v1/monitoring/freezes`, F26). U3 los responde con p95 ≤ 200 ms y 12 rangos (NFR-U3-24).
- **Métricas:** al Pushgateway (F106), en los grupos `success` y `run`.
- **Criticidad:** High para el monitoreo (NFR-RES-01). El modelo sigue sirviendo si el monitoreo se detiene (BR-U4-16).
- **Pendientes del FD para etapas siguientes** (§8b): `backoffLimit: 0`, `Forbid`, `vectra-high`, sidecar nativo y el `ExternalSecret` de `bias-monitoring-job`. Se fijan en el Infrastructure Design.
- **Sin egress (X02):** bias solo llama a `freeze` (X04).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Duración de una corrida y latencia de detección (Performance)
La detección depende del agregador de U3 (cada 5 min), de la corrida (cada 15 min) y de la
propagación del congelamiento (≤ 6 s, BR-U4-14).

A) **Corrida p95 ≤ 2 min y detección p95 ≤ 25 min**:
   - corrida (lectura, cálculo de todas las versiones evaluadas, `freeze` y push) p95 ≤ 2 min y máximo 10 min, por debajo del intervalo de 15 min;
   - latencia de detección: desde el `recorded_at` de las entradas que llevan la agregada sobre el umbral hasta `congelado`, p95 ≤ 25 min (5 min del agregador + 15 de la corrida + 2 de cálculo + 6 s de propagación, con margen);
   - se mide en la demostración RT-2 de U12, que ya debe medir esa latencia (§8b).

   (Recomendado)

B) Corrida cada 5 min y detección p95 ≤ 12 min. Triplica la carga sobre el registro

X) Other (please describe after [Answer]: tag below)

[Answer]: X

A, con un ajuste: detección p95 ≤ 30 min, porque el atraso p95 del agregador de U3 es ≤ 10 min (NFR-U3-24), no 5: 10 (agregador) + 15 (corrida) + 2 (cálculo) + 6 s (propagación) ≈ 27 min, con margen. Corrida p95 ≤ 2 min y máximo 10 min, con `activeDeadlineSeconds: 600` en el CronJob y timeouts explícitos de `deps.call` para F26 y F27 (se fijan en NFR Design e Infrastructure Design). Se alinea el «≈ 20 min» del §8b de U9 y de U12 a «≈ 27 min medido en RT-2».

## Question 2 — Latencia de la API (Performance; F14, F25)

A)
   | Operación | Objetivo |
   |---|---|
   | `GET /v1/disparity` con caché caliente | p95 ≤ 200 ms |
   | `GET /v1/disparity` sin caché (ventana de 90 días, una versión) | p95 ≤ 2 s |
   | `GET /v1/freezes` y `GET /v1/freezes/{id}` | p95 ≤ 500 ms |
   | `POST /v1/source-comparisons` (`compare_source`, dos tablas) | p95 ≤ 1 s |

   Medidas con 10 usuarios de consola concurrentes (cumplimiento y CRO son pocos). (Recomendado)

B) Un solo objetivo: p95 ≤ 2 s para todo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Criticidad y disponibilidad por proceso (Availability; NFR-RES-01)
El monitoreo es High, pero su camino crítico es el CronJob. El servicio HTTP solo sirve el
dashboard, los paquetes y `compare_source`.

A) **CronJob High; servicio HTTP Medium**:
   - CronJob: `vectra-high`, una sola corrida a la vez; si un nodo cae a mitad de corrida, la siguiente (15 min) la reemplaza y `MonitoreoSesgoDetenido` cubre una caída prolongada;
   - servicio HTTP: 2 réplicas repartidas por zona, PDB y `vectra-normal`; su caída deja sin dashboard ni `compare_source`, pero no detiene el monitoreo ni el congelamiento;
   - readiness del servicio: solo el proceso (no tiene base propia; el registro caído da 503 en la consulta, P-U1-04).

   (Recomendado)

B) Los dos High (`vectra-high`, HPA en el servicio)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Precisión: la criticidad del componente C11 pasa a «CronJob High, servicio HTTP Medium» en `application-design.md` §2 y `components.md`; P-U1-09 ya los separa por prioridad.

## Question 4 — Escalado del servicio HTTP (Scalability)

A) **2 réplicas fijas, sin HPA**: carga baja (unos pocos usuarios de cumplimiento y CRO, y `compare_source` ocasional); la caché de 15 min absorbe las consultas repetidas. Una prueba de carga con 10 usuarios confirma que 2 réplicas sobran. (Recomendado)

B) HPA de 2 a 4 por CPU al 70 %, como los demás servicios

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Precisión: se verifica que `require-hpa-bounds` de U1 admita un Deployment de réplicas fijas (o se exime con anotación justificada), y la tabla de cumplimiento cita RESILIENCY-09 con esta justificación.

## Question 5 — Librería estadística en tiempo de ejecución (Tech Stack)
Wilson, Newcombe y la combinación de varianzas son pocas fórmulas. Fairlearn es el oráculo
de PBT-U9-01.

A) **Python puro en runtime; Fairlearn solo en pruebas**:
   - `vectra_disparity` usa solo la biblioteca estándar (`math`, `decimal` para la salida como `Decimal4`); sin numpy, scipy ni pandas en las imágenes de runtime;
   - Fairlearn, pandas y numpy son dependencias de desarrollo, solo para el oráculo (PBT-U9-01) y la simulación estadística;
   - U4 (`model-validation-job`) y U5 la importan igual, sin arrastrar dependencias numéricas.

   (Recomendado: imagen más chica, menos superficie para el escaneo y la misma librería en los tres consumidores)

B) numpy y scipy en runtime (`scipy.stats` para los intervalos)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Calidad de la librería y de la regla (Maintainability; PBT-01..10)

A)
   - cobertura de ramas **100 %** en `stats`, `disparity`, `freeze_rule`, `context` y `window`, y ≥ 95 % en el resto;
   - `mutmut` en `stats`, `disparity` y `freeze_rule`, con 0 sobrevivientes sin justificar;
   - PBT-U9-01..08 con el perfil `ci` (500 ejemplos, semilla impresa);
   - la **simulación estadística** de la cobertura del intervalo y de los congelamientos falsos (BLM §3) corre **cada noche** en CI (tarda minutos con 10 000 repeticiones), no en cada PR; un PR que cambie `stats` o `freeze_rule` la ejecuta también;
   - la librería se versiona con SemVer y su versión viaja en cada paquete de contexto (BR-U9-15).

   (Recomendado)

B) Igual que A, pero la simulación en cada PR

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Seguridad y privacidad del dashboard (Security; SECURITY-03, 08, 14)

A)
   - identidades: el CronJob con `bias-monitoring-job` (`governance:freeze`, `registry:read:monitoring`) y el servicio con `bias-monitoring-service` (`registry:read:monitoring`); llaves `private_key_jwt` distintas desde ESO;
   - las respuestas del dashboard y del paquete nunca muestran la tasa de una celda con menos de `n_min` casos (BR-U9-03, 20), y tampoco la tasa de una celda que se pudiera deducir restando de la banda (si solo una celda de la banda es insuficiente y la banda tiene 2 o más grupos suficientes, se oculta también el total de la banda);
   - log `disparity.viewed` y `freeze_context.viewed` con `principal_subject` y `principal_role` (allowlist de U0), retenidos ≥ 90 días como los demás logs de auditoría;
   - logs y métricas sin datos del solicitante; las inválidas solo con `seq`.

   (Recomendado: la regla de la resta cierra una inferencia simple sobre celdas chicas)

B) Igual que A, sin la regla de la resta ni los logs de consulta

X) Other (please describe after [Answer]: tag below)

[Answer]: X

A, con un ajuste: la regla de la resta se aplica a la diferencia **sin bandas** (BR-U9-06, `population_difference` y la métrica `sin_bandas`), no al total de la banda. El total de banda `n_band` ya suma solo celdas suficientes, así que no filtra nada. Si algún grupo del atributo tiene al menos una celda insuficiente en alguna banda, la tasa de ese grupo sin bandas no se publica y `population_difference` se calcula solo con las celdas suficientes, marcada como parcial. Se registra como cambio al FD de U9 (BR-U9-06, 18, 20) y a los tipos de U0 §9.4. Los logs `disparity.viewed` y `freeze_context.viewed` llevan `principal_subject` y `principal_role`; si `principal_role` no está en la allowlist de `LogRecord` de U0 §8, se agrega allí.

## Question 8 — Escenarios de resiliencia de U9 (Resilience; RESILIENCY-14 = C, P-U0-08)
Se documentan en NFR Design y se ejecutan en Operations.

A)
   | # | Escenario | Resultado esperado |
   |---|---|---|
   | E1 | Registro caído | Corridas fallidas; `MonitoreoSesgoDetenido` a 1 h; el modelo sigue sirviendo; dashboard 503 |
   | E2 | Agregador de U3 atrasado más de 30 min | Corridas fallidas por atraso; `MonitoringAggregatorStale` (U3) y luego `MonitoreoSesgoDetenido` |
   | E3 | governance caído durante un congelamiento | 4 intentos, `BiasFreezeFailed` (SEV1); la corrida siguiente vuelve a intentar |
   | E4 | Pushgateway caído | La corrida termina con error y el `freeze` ya aplicado se mantiene; `PushgatewayDown` |
   | E5 | El pod del CronJob muere a mitad de corrida | Sin `freeze` parcial; la corrida siguiente lo reemplaza |
   | E6 | Modelo proxy (RT-2) | Congelado dentro de la latencia de Q1, con el paquete completo |

   E1, E3, E4 y E5 también tienen prueba de integración en CI; E2 y E6 se ejecutan en kind.

   (Recomendado)

B) Solo E1, E3 y E6

X) Other (please describe after [Answer]: tag below)

[Answer]: X

A, con dos ajustes: (1) E5 dice «sin `freeze` con datos parciales»: un `freeze` ya aplicado a una versión antes de morir el pod se mantiene y la corrida siguiente evalúa las demás; (2) se agrega E7: Keycloak caído, el CronJob no obtiene token (F50), la corrida falla antes de congelar, `MonitoreoSesgoDetenido` a 1 h y el modelo sigue sirviendo; tiene prueba de integración en CI. E1, E3, E4, E5 y E7 con prueba de integración en CI; E2 y E6 en kind.

## Question 9 — Recursos del CronJob (Performance / Cost)
Con conteos agregados, una corrida lee unos miles de filas y calcula unas decenas de
agregadas por versión.

A) **Requests 100m / 128 MiB y limits 500m / 256 MiB**, con una prueba que mida el pico de memoria y el tiempo de una corrida con 3 versiones y celdas densas; si el pico supera el 70 % del límite, se ajusta en el Infrastructure Design. (Recomendado)

B) Requests 250m / 256 MiB y limits 1 CPU / 512 MiB, sin medir

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `nfr-requirements.md`: rendimiento (corrida, detección, API), disponibilidad y criticidad por proceso, escalado, seguridad y privacidad, resiliencia, observabilidad, calidad y pruebas (NFR-U9-xx), cada uno con su verificación
- [x] `tech-stack-decisions.md`: runtime, librería, dependencias de desarrollo, pruebas
- [x] Cambios a otras unidades, si los hay, registrados
- [x] Tabla de cumplimiento de extensiones (SECURITY, RESILIENCY, PBT, AUTONOMIA)
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
