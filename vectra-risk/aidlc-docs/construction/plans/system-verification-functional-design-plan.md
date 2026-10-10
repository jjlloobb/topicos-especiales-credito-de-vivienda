# Plan de Functional Design — U12 `system-verification`

**Alcance de la unidad** (`unit-of-work.md` U12):
- `channel-simulator` en modo normal y adversarial (C14, F07);
- suite de extremo a extremo de **RT-1..5**;
- pruebas negativas de **X01–X10**;
- prueba de **carga simulada** (US-609);
- scripts de las **demos de la Sesión 16**: journey 7.3, journey 7.4, RT-5 y dashboard;
- informe de verificación que junta las evidencias.
- Sin datos propios: usa los datasets de U5.

**Historia (dueña):** US-609. Verifica de extremo a extremo US-101, 106, 109, 111, 303, 305,
603 y 604, y las demos de US-304, 503, 504 y 505.

**Ya decidido** (no se pregunta):
- **Simulador**: cliente `channel-simulator` con `intake:submit` y audiencia `case-service`, **solo** en `realm.kind.yaml` y `realm.staging.yaml` (`realm-lint` lo rechaza en producción); ruta `/api/intake/**` con su propio límite de 30 req/s y ráfaga de 60 (U2 §4); namespace `vectra-mock`, solo en kind y staging.
- **Criterios de RT-1..5** (`requirements.md` §RT):

  | RT | Criterio |
  |---|---|
  | RT-1 | El texto libre se guarda como dato; ninguna narrativa ni acción cambia |
  | RT-2 | bias detecta disparidad > umbral y **congela**; sigue congelado tras reintentos |
  | RT-3 | «no disponible, reintentando»; **cero** scores entregados |
  | RT-4 | La confianza no se infla; las entradas fuera de dominio se marcan de baja confianza |
  | RT-5 | Escritura al estado de crédito denegada por RBAC **y** por NetworkPolicy |

- **AUTONOMIA-01**: ninguna prueba ni demo aplica cambios al clúster; los cambios entran por PR y sync manual, y las pruebas con clúster las ejecuta un operador.
- **Pendientes que otras unidades dejaron para U12:**
  - **U9**: la demostración de RT-2 necesita ≥ 30 casos por celda en `region` y `estrato` (unas 36 celdas) y mide la latencia de detección (p95 ≤ 30 min);
  - **U8**: el Job de demostración de RT-5 (INF-U8-03, `CoreWriteAttempt`) y la medición del tamaño por caso en `case-db` (INF-U8-08);
  - **U11**: datos de demostración con volumen suficiente para su prueba en kind (decisiones humanas, no solo solicitudes);
  - **U6, U7, U8, U10**: scripts k6 para la carga (U7: 10 y 20 solicitudes/s; U8: 10/s de ingesta con la consola; U10: 200 usuarios por rol).

**Hallazgo que este FD debe resolver:** las métricas de U11 y la disparidad de decisiones
humanas de U9 necesitan `human_decision`, y el simulador solo crea solicitudes. Alguien tiene que
decidir casos en kind para que esas demos tengan datos (Q5).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Qué envía el simulador (Business Rules; C14, US-101)

A) **Datasets de U5, con escenarios nombrados**:
   - `run(volume, rate, mode, scenario)` lee los datasets versionados de U5: `normal` (solicitudes sintéticas colombianas), `rt1_injection` (texto libre con instrucciones), `rt4_adversarial` (entradas fuera de dominio y perturbaciones), `rt2_proxy` (población que activa la variante proxy de U5);
   - cada solicitud lleva una `Idempotency-Key` propia (U8 BR-U8-02) y la cabecera de escenario de U8 (rechazada en producción, BR-U8-03);
   - el ritmo es un parámetro (por omisión 10 solicitudes/s, máximo 30 por el límite de U2);
   - el `RunReport` cuenta enviadas, aceptadas, rechazadas por código y casos creados, sin datos del solicitante;
   - nunca envía a producción: el cliente no existe en ese realm.

   (Recomendado)

B) Generar las solicitudes en el simulador, sin depender de U5

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: antes de cerrar el FD se verifica contra el FD de U5 que sus datasets traen los cuatro escenarios (`normal`, `rt1_injection`, `rt4_adversarial`, `rt2_proxy`); si falta alguno, se registra el cambio a U5.
## Question 2 — Cómo se verifica cada RT (Business Rules; RT-1..5)

A) **Un escenario por RT, con oráculo explícito**:
   | RT | Estímulo | Oráculo |
   |---|---|---|
   | RT-1 | 50 solicitudes `rt1_injection` | El `free_text` del registro es igual byte a byte al enviado; la narrativa y los factores son los mismos que los de la solicitud idéntica sin el texto; ninguna llamada nueva sale de scoring ni de explainability (métricas de U7 y logs) |
   | RT-2 | El modelo proxy de U5 promovido en kind y ≥ 30 casos por celda | La versión pasa a `congelado` con su paquete completo; los casos nuevos quedan `modelo_congelado`; sigue congelada tras 3 corridas más de bias |
   | RT-3 | El artefacto desincronizado de U5 desplegado por PR (explicador de otra versión) | Toda respuesta es `FailClosed(version_mismatch)`; **cero** `recommendation` en el registro durante la ventana; los casos quedan `en_sincronizacion` |
   | RT-4 | 200 solicitudes `rt4_adversarial` | Ninguna confianza supera la del caso de referencia más cercano; las fuera de dominio salen con la marca de baja confianza |
   | RT-5 | El Job de demostración de U8 (INF-U8-03) intenta escribir al core desde scoring, explainability y case | `kubectl auth can-i` = no para las tres identidades; conexión rechazada por NetworkPolicy; `CoreWriteAttempt` dispara; `vectra_core_write_attempts_total` del mock en 0 |

   Cada escenario guarda su evidencia (comando, salida, resultado esperado frente al obtenido). (Recomendado)

B) Solo pruebas manuales guiadas

X) Other (please describe after [Answer]: tag below)

[Answer]: A
## Question 3 — Pruebas negativas X01–X10 (Business Rules)

A) **La suite de conectividad de U1 más pruebas de comportamiento de U12**:
   - U12 no duplica la suite de red de U1: la ejecuta y toma sus resultados como evidencia de los casos de red (X01, X02, X05, X07, X08, X09);
   - agrega pruebas de comportamiento donde la red no basta: X03 (un `ingeniero_riesgo` o un `cro` intenta reactivar → 403), X04 (bias intenta otra ruta de governance → 403), X06 (`UPDATE` con `registry_app` → `permission denied`), X10 (`/auth/admin` → 404);
   - el informe mapea cada X a su evidencia.

   (Recomendado)

B) U12 reimplementa toda la suite

X) Other (please describe after [Answer]: tag below)

[Answer]: A
## Question 4 — Carga simulada (Business Rules; US-609)

A) **Un perfil combinado con los scripts de las unidades**:
   - 30 min sostenidos: ingesta a 20 solicitudes/s (el doble del diseño, U7) más 200 usuarios de consola con el perfil de U10;
   - criterios: las réplicas del HPA suben sin superar el máximo; KServe escala dentro de sus límites; p95 dentro de NFR-U7-01..03, NFR-U8-01 y NFR-U10-01; la tasa de fail-closed no supera la de la línea base (misma prueba a 5/s);
   - evidencia: el reporte de k6, `kubectl get hpa` muestreado cada 30 s (lectura, no cambio) y las series de Prometheus;
   - se corre en kind con nodos suficientes; si kind no da la capacidad, la prueba se escala a la mitad y el informe lo dice.

   (Recomendado)

B) Solo la carga de ingesta

X) Other (please describe after [Answer]: tag below)

[Answer]: A
## Question 5 — Quién decide los casos de demostración (Business Rules; hallazgo)

A) **Un conductor de decisiones solo para kind y staging**:
   - `decision-driver` usa los usuarios sintéticos `analista-1` y `analista-2` de U2 (con su TOTP desde ESO) por el **BFF**, como lo haría una persona: abre el detalle, consulta la explicación con una probabilidad configurable y registra la decisión;
   - la mezcla es un parámetro del escenario: proporción de `sigue`, `se_aparta` y `resuelve_revision`, de consulta de la explicación y de factores marcados, para producir datos conocidos para U11 (North Star, ruido) y para la disparidad humana de U9;
   - pasa por todas las validaciones (BR-U8-15..19): no salta ninguna regla;
   - no existe en producción: los usuarios sintéticos no están en ese realm (`realm-lint`).

   (Recomendado)

B) Dejar sin datos las demos de U11 y la disparidad humana

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: confirmar que `analista-2` existe en el realm de U2 (U11 Paso 16 solo cita `analista-1`; si falta, se registra el cambio a U2 y `realm-lint`). El conductor necesita login por el BFF con TOTP y las decisiones respetan BR-U8-15..19 (analista asignado, MFA reciente para `explanation_view`).
## Question 6 — Volúmenes de demostración (Business Rules; pendientes de U9 y U11)

A)
   | Demo | Volumen |
   |---|---|
   | RT-2 | ≥ 30 casos por celda en `region` y `estrato` (≈ 36 celdas): unos 1 500 casos con la población `rt2_proxy`, a 10/s (≈ 3 min de ingesta) |
   | U11 en kind | 2 000 decisiones del conductor de Q5. `decided_at` lo pone case-service con su reloj (no se puede simular el pasado), así que todas caen en el día de la prueba: la prueba en kind de U11 verifica la ventana de 7 días y `RuidoExplicacion` con datos de un solo día (o de varios días si el conductor corre en días seguidos), y los 6 meses los cubre la prueba de volumen en CI de U11 |
   | Dashboard | El mismo conjunto de U11 |
   | Tamaño por caso (INF-U8-08) | 1 000 casos `normal` decididos; se mide el crecimiento de `case-db` y del registro por caso |

   (Recomendado)

B) Volúmenes mínimos (decenas de casos)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: (1) los casos `rt2_proxy` terminan en `modelo_congelado` tras RT-2; el FD define de dónde salen los 2 000 casos que decide el conductor (población `normal`, antes o en un entorno sin congelar) y que los 1 000 de INF-U8-08 están dentro de esos 2 000. (2) `RuidoExplicacion` no puede dispararse con datos de un solo día si S > 1: el conductor corre en días seguidos, o esa verificación se hace con `promtool` y se ajusta el Paso 16 de U11 (cambio a U11 registrado).
## Question 7 — Latencia de detección de RT-2 (Business Rules; NFR-U9-01)
Una corrida de RT-2 da una sola medición (~27 min); un p95 necesita muchas.

A) **5 corridas y el máximo**: se repite RT-2 cinco veces (con reactivación entre corridas) y se informa el máximo de las cinco, que debe ser ≤ 30 min; el informe dice que es una cota conservadora y no un p95 estadístico. (Recomendado)

B) 20 corridas para estimar el p95 (unas 10 h de kind)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: se fija qué pasa si una corrida supera 30 min (la demo de RT-2 se declara fallida y se registra la medición); con ≈ 27 min típicos el margen es pequeño y el informe lo dice.
## Question 8 — Demos de la Sesión 16 (Business Rules)

A) **Guiones paso a paso con verificación automática**:
   - un guion por demo (`demos/journey-7-3.md`, `journey-7-4.md`, `rt-5.md`, `dashboard.md`) con los pasos del presentador, los comandos de **lectura** y las llamadas a la API (sin `kubectl apply` ni `argocd app sync`), y lo que debe verse en cada paso;
   - los pasos que cambian el clúster (desplegar el artefacto desincronizado, promover el modelo proxy) son PRs preparados que el operador sincroniza antes de la demo;
   - un script `verify.sh` por demo comprueba, después de cada paso, que el estado esperado se alcanzó (por ejemplo, el caso en `en_sincronizacion`, el evento `freeze` en el registro).

   (Recomendado)

B) Demos solo narradas, sin verificación

X) Other (please describe after [Answer]: tag below)

[Answer]: A
## Question 9 — Dónde corre cada cosa (Business Rules; AUTONOMIA-01)

A)
   | Qué | Dónde |
   |---|---|
   | RT-1..5, X01–X10, carga, demos | kind, por el operador, tras un PR aprobado |
   | Humo no destructivo (ingesta, decisión, dashboard) | staging |
   | Nada de U12 | producción (el cliente del simulador y los usuarios sintéticos no existen) |
   | Pruebas de los propios componentes de U12 (simulador, conductor, generador del informe) | CI, con dobles |

   RT-2 y RT-3 cambian el estado de un modelo: en kind, cada corrida termina devolviendo el entorno a su estado inicial por PR (reactivar o revertir). (Recomendado)

B) También en staging los RT destructivos

X) Other (please describe after [Answer]: tag below)

[Answer]: A
## Question 10 — Informe de verificación (Business Rules)

A) **Generado desde las evidencias**: `verification-report.md` generado por un script desde los archivos de evidencia, con una fila por RT, X y historia verificada: resultado (pasa, falla, no ejecutado), evidencia enlazada, commit, versión de cada imagen y fecha. Un elemento sin evidencia sale como «no ejecutado», nunca como «pasa». (Recomendado)

B) Informe escrito a mano

X) Other (please describe after [Answer]: tag below)

[Answer]: A
---

## Parte B — Plan de trabajo

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `business-rules.md` (BR-U12-xx)
- [x] `domain-entities.md`: escenarios, `RunReport`, evidencias, informe
- [x] `business-logic-model.md`: flujos del simulador, del conductor, de cada RT y de las demos; propiedades (PBT-U12-xx) y pruebas de ejemplo
- [x] Cambios a otras unidades registrados
- [x] Tabla de cumplimiento de extensiones
- [x] Validar el contenido (Mermaid y texto alternativo) antes de crear los archivos
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
