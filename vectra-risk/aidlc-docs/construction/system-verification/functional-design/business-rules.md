# Reglas de negocio — U12 `system-verification`

Decisiones del plan (`system-verification-functional-design-plan.md`, Q1–Q10 = A, con las notas
del usuario). Los IDs `BR-U12-xx` se referencian en los planes de tareas. U12 no tiene datos
propios ni corre en producción.

**Comprobaciones hechas al cerrar el FD** (notas de Q1 y Q5):
- **U5** (domain-entities §2 y §5, BR-U5-16..18) trae las particiones `train`, `validation` y `test` (filas `ApplicationIn` válidas) y un manifiesto adversarial con los casos **RT-1** (pares que difieren solo en `free_text`), **RT-4** (18 casos fuera de la envolvente) y **RT-3** (4 paquetes alterados). **No** hay una población «`rt2_proxy`»: la variante proxy de RT-2 es un **modelo** que produce disparidad sobre una población normal (BR-U5-14). U12 la usa así y no hace falta cambiar U5.
- **U2** (domain-entities §3) ya tiene `analista-1` y `analista-2` en kind y staging.
- **U8 BR-U8-15** no exige un analista asignado (la bandeja es común) y la consulta de la explicación no exige MFA (C03). El conductor solo necesita el login normal con TOTP y respetar BR-U8-15..19.

---

## 1. Simulador (Q1; C14, US-101)

**BR-U12-01 — Qué envía.** `run(volume, rate, scenario)` toma las solicitudes de U5:

| Escenario | Origen | Para qué |
|---|---|---|
| `normal` | Partición `test` de U5 (no la usa U4, así que no repite el dataset de validación), muestreada al azar con semilla | Ingesta, carga, decisiones de demostración |
| `stratified` | `test` muestreada por `region` × `estrato` hasta ≥ 30 casos por celda | RT-2 (BR-U12-06) |
| `rt1` | Los pares RT-1 del manifiesto adversarial | RT-1 |
| `rt4` | Los 18 casos RT-4 del manifiesto | RT-4 |

**BR-U12-02 — Cómo envía.**
- `POST` a `/api/intake/v1/intake/applications` con el cliente `channel-simulator` (solo en kind y staging).
- Una `Idempotency-Key` nueva por solicitud (U8 BR-U8-02) y la cabecera de escenario de U8, que producción rechaza (BR-U8-03).
- Ritmo por parámetro: 10 solicitudes/s por omisión y máximo 30/s, el límite de U2 para `channel-simulator`.
- **`RunReport`**: enviadas, aceptadas, rechazadas por código, `case_id` creados (para que la verificación los siga) y duración. Sin datos del solicitante.

## 2. Conductor de decisiones (Q5; hallazgo del FD)

**BR-U12-03 — `decision-driver`.**
- Usa `analista-1` y `analista-2` por el **BFF**, con login OIDC y TOTP, como lo haría una persona. La contraseña y la semilla TOTP se leen del Vault de kind (o la bóveda de staging) con la sesión del operador, en las mismas rutas donde ESO las lee para el realm (NFR-U12-04; revisión del NFR Requirements de U12, 2026-10-10).
- Para cada caso `listo`:
  1. abre el detalle;
  2. con probabilidad `p_view`, abre la explicación (`record_explanation_view`);
  3. registra la decisión según la mezcla del escenario.
- La mezcla incluye la proporción de `sigue`, `se_aparta` y `resuelve_revision` (esta solo si el `outcome` es `revision_requerida`), de factores marcados frente a «Ninguno», y la justificación cuando hace falta (20..2000 caracteres).
- Respeta BR-U8-15..19: no salta ninguna validación, y un 409 o un 422 se cuentan en su informe, nunca se reintentan con otro contenido.
- No existe en producción: los usuarios sintéticos no están en ese realm (`realm-lint`).

## 3. Escenarios RT (Q2)

**BR-U12-04 — Un escenario por RT, con oráculo.**

| RT | Estímulo | Oráculo |
|---|---|---|
| RT-1 | Todos los pares RT-1 de U5 | Leído **por el BFF con `analista-1`**: el `free_text` del detalle del caso es igual byte a byte al enviado, y la recomendación y la narrativa del detalle son **idénticas** a las de su par sin el texto (`expected` del manifiesto); scoring y explainability no hacen ninguna llamada distinta de las del par (métricas y logs). El registro no guarda `free_text` (BR-U0-95), así que no se lee de ahí (Infrastructure Design de U12, 2026-10-10) |
| RT-2 | Modelo proxy de U5 promovido en kind por PR; ~1 500 casos `stratified` (BR-U12-06) | La versión pasa a `congelado` con su paquete completo (un `FreezeContext` válido según U0 §9.4, más `data_sources` e `initial_disparity` no vacíos; revisión del plan de tareas de U12, 2026-10-10); los casos nuevos quedan `modelo_congelado`; sigue congelada tras 3 corridas más de bias; latencia según BR-U12-07 |
| RT-3 | Cada uno de los 4 paquetes alterados de U5, desplegado por PR | Toda respuesta es `FailClosed(version_mismatch)`; **cero** `recommendation` en el registro durante la ventana; los casos quedan `en_sincronizacion` |
| RT-4 | Los 18 casos RT-4 | `confidence` por debajo del umbral de baja confianza, `revision_requerida` y la marca `baja_confianza` (`expected` del manifiesto) |
| RT-5 | El Job `rt5-demo-<runId>` de U8 (INF-U8-03, solo kind) intenta escribir al core con la identidad de `case-service` | El Job termina con éxito y su log tiene el 403 del proxy de Linkerd (cabecera `l5d-proxy-error`); `CoreWriteAttempt` dispara; `vectra_core_write_attempts_total` del mock en 0. Las identidades de scoring y explainability no tienen ruta al core: las cubre X01 (suite de conectividad de U1). Sin `kubectl auth can-i` de otras identidades, que exigiría impersonación y K16 no la da (pendientes consolidados, 2026-10-10) |

Cada escenario guarda su evidencia: comando, salida y resultado esperado frente al obtenido.

## 4. Negativas X01–X10 (Q3)

**BR-U12-05 — Red de U1 más comportamiento de U12.**
- Los casos de red (X01, X02, X05, X07, X08 y X09) salen de la suite de conectividad de U1, que U12 ejecuta y toma como evidencia.
- U12 agrega pruebas de comportamiento:
  - **X03**: `ingeniero_riesgo` y `cro` intentan reactivar → 403;
  - **X04**: `bias-monitoring-job` llama a otra ruta de governance → 403 de Linkerd, leído del Job `x04-probe` de U9;
  - **X06**: `UPDATE` con `registry_app` → `permission denied`, leído del Job `x06-probe` de U3 (los dos Jobs solo en kind, lanzados por PR; U12 solo lee su estado y su log; INF-U12-02, Infrastructure Design de U12, 2026-10-10). Un Job de prueba solo cuenta si su `runId` es el del manifiesto de la verificación en curso y su `completionTime` es posterior al inicio de la verificación; si no, `no ejecutado` (segunda revisión del Infrastructure Design de U12, 2026-10-10);
  - **X10**: `/auth/admin` → 404.
- El informe mapea cada X a su evidencia.

## 5. Volúmenes y latencia de RT-2 (Q6, Q7)

**BR-U12-06 — Volúmenes de demostración.**

| Demo | Volumen | Origen y orden |
|---|---|---|
| Decisiones para U11 y la disparidad humana de U9 | 2 000 casos `normal` decididos por el conductor | Se corren **antes** de RT-2, con el modelo de referencia activo (sin congelar), para que los casos lleguen a `listo` |
| Tamaño por caso (INF-U8-08) | Los primeros 1 000 de esos 2 000 | Se mide el crecimiento de `case-db` y del registro antes y después |
| RT-2 | ~1 500 casos `stratified` (≥ 30 por celda en `region` y `estrato`, ≈ 36 celdas) | Después de las decisiones, con el modelo proxy promovido |
| Dashboard de producto | Las 2 000 decisiones | El mismo conjunto de U11 |

- **Días** (nota 2 de Q6): `decided_at` lo pone case-service con su reloj, así que no se puede simular el pasado. `day` de U11 es «ayer completo» y `RuidoExplicacion` necesita **S** días seguidos bajo el piso.
- En kind, el conductor corre el día D y la verificación de U11 se hace el día D + 1 (North Star, sostenida, tasa de consulta y `ProductMetricsStale`).
- `RuidoExplicacion` se verifica con `promtool` y con la prueba con reloj simulado de U11, no en kind. Se registra como cambio al Paso 16 del plan de U11.

**BR-U12-07 — Latencia de detección de RT-2.**
- Desde el **menor** `recorded_at` de las `recommendation` del lote `stratified` hasta el `recorded_at` de la entrada `freeze` (Infrastructure Design de U12, 2026-10-10). El cruce real del umbral ocurre entre la primera y la última entrada del lote, así que medir desde la primera nunca subestima la latencia; puede sobrestimarla hasta ≈ 3 min, lo que dejan los ≈ 27 min típicos con un margen de ≈ 0 a 3 min frente a 30, y el informe lo dice.
- Se repite RT-2 **5 veces**, con reactivación por cumplimiento entre corridas, y se informa el máximo, que debe ser ≤ 30 min. El informe dice que es una cota conservadora y no un p95 estadístico.
- **Si una corrida supera 30 min** (nota de Q7): RT-2 se declara **fallida** y se registra la medición. Según NFR-U9-01, el plan es bajar el intervalo de bias a 10 min antes que subir el objetivo. Con ≈ 27 min típicos el margen es pequeño, y el informe lo dice.

## 6. Carga (Q4; US-609)

**BR-U12-08 — Perfil combinado.**
- **Perfil**: 30 min sostenidos con ingesta a 20 solicitudes/s y 200 usuarios de consola con el perfil de U10.
- **Línea base**: la misma prueba a 5 solicitudes/s.
- **Criterios**:
  - las réplicas del HPA suben sin superar el máximo;
  - KServe escala dentro de sus límites;
  - p95 dentro de NFR-U7-01..03, NFR-U8-01 y NFR-U10-01;
  - la tasa de fail-closed no supera la de la línea base.
- **Evidencia**: el reporte de k6, `kubectl get hpa` cada 30 s (solo lectura) y las series de Prometheus.
- **Sin capacidad suficiente en kind**: la prueba se escala a la mitad y el informe lo dice.

## 7. Demos y entornos (Q8, Q9)

**BR-U12-09 — Guiones de demo.**
- Un guion por demo: `journey-7-3.md` (RT-3), `journey-7-4.md` (RT-2, paquete y resolución), `rt-5.md` y `dashboard.md`.
- Cada guion tiene los pasos del presentador, comandos de **lectura** y llamadas a la API; nunca `kubectl apply` ni `argocd app sync`.
- Los cambios al clúster (artefacto alterado, modelo proxy) son **PRs preparados** que el operador sincroniza antes.
- `verify.sh` comprueba el estado esperado después de cada paso.

**BR-U12-10 — Dónde corre.**

| Qué | Dónde |
|---|---|
| RT-1..5, X01–X10, carga, demos | kind, por el operador, tras un PR aprobado |
| Humo no destructivo (ingesta, decisión, dashboard) | staging |
| Nada de U12 | producción |
| Pruebas de los componentes de U12 | CI, con dobles |

RT-2 y RT-3 devuelven el entorno a su estado inicial al terminar, por PR: reactivar el modelo y revertir el artefacto.

## 8. Informe (Q10)

**BR-U12-11 — `verification-report.md` generado.**
- Un script lo genera desde los archivos de evidencia, con una fila por RT, X e historia verificada: resultado (`pasa`, `falla`, `no ejecutado`), evidencia enlazada, commit, digest de cada imagen y fecha.
- Un elemento sin evidencia sale como `no ejecutado`, **nunca** como `pasa`.
- Una evidencia con un resultado obtenido distinto del esperado sale como `falla`.

**BR-U12-12 — Logs sin datos del solicitante** (revisión del FD de U12, 2026-10-10). Al terminar las corridas en kind, una
consulta a Loki busca, en todos los logs del periodo, los identificadores (`SYN-…`) y los nombres
del catálogo ficticio de U5 de las solicitudes enviadas. Debe devolver 0 resultados. Es la
evidencia `LOGS-NO-PII` de US-604, junto con `X02`.

**BR-U12-13 — Cuándo pasa una historia** (revisión del FD de U12, 2026-10-10). Según el mapa de domain-entities §4.2: pasa
solo si todas sus evidencias pasan; falla si alguna falla; si no, queda `no ejecutado`.

## 9. Cambios a otras unidades (registrados en `audit.md`)

| Unidad | Cambio | Motivo |
|---|---|---|
| U11 plan (Paso 16) | `RuidoExplicacion` se verifica con `promtool` y con la prueba con reloj simulado, no en kind; la verificación en kind de las demás métricas se hace el día siguiente a las decisiones | Q6, nota 2 |
| U5 | Sin cambios: el manifiesto adversarial y la partición `test` cubren los escenarios; RT-2 usa el modelo proxy sobre una muestra estratificada | Q1, nota |
| U2 | Sin cambios: `analista-1` y `analista-2` ya existen en kind y staging | Q5, nota |
