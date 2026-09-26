# Historias de usuario — Vectra Risk

**Enfoque (plan aprobado):** épicas por capacidad de negocio. Dentro de cada épica,
historias pequeñas escritas desde la persona humana a la que benefician o protegen.
Los criterios de aceptación van en Gherkin, con escenarios negativos o de abuso, y
cada historia cierra con una línea **Verificación** (AUTONOMIA-02).

**Convenciones**
- Prioridad: `M` Must · `S` Should · `C→` Could promovido (Q11). 🎯 = sostiene una demo de la Sesión 16 (PRD §13).
- Personas: P1 Analista · P2 Ingeniero de riesgo · P3 CRO · P4 Cumplimiento · P5 Comité · P6 Supervisor (ver `personas.md`).
- Requisitos: IDs de `inception/requirements/requirements.md`.
- "Recomendación usable" = objeto con score, confianza, recomendación y explicación, **todos con el mismo `model_version_id`**.

---

## Épicas

| Épica | Objetivo de negocio | Requisitos principales | Historias |
|---|---|---|---|
| **E1 Originación explicada** | El analista abre cada caso con score y explicación sincronizados, o con un "no disponible" explícito | FR-ING, FR-SCO, FR-EXP, FR-UI-01/02, RT-1/3/4 | 13 |
| **E2 Gobierno de modelos y política** | Ninguna versión de modelo ni de política llega a producción sin validación y aprobación del CRO | FR-MOD, FR-POL | 8 |
| **E3 Vigilancia de sesgo** | La disparidad se mide, alerta y congela; la decisión de reactivar es humana | FR-BIA, FR-UI-04/05, RT-2 | 8 |
| **E4 Registro y auditoría** | Cada decisión puede defenderse con un expediente íntegro y verificable | FR-REG | 4 |
| **E5 Adopción y métricas** | Detectar si la explicación cambia o sustenta decisiones, o si se ignora | FR-MET, FR-REG-03 | 5 |
| **E6 Seguridad, soberanía y plataforma** | El producto corre dentro del banco, sin fuga de datos, sin escritura de estado de crédito y sin cambios autónomos | FR-INT, FR-PLT, NFR-SEC, NFR-RES, RT-5 | 11 |
| | | **Total** | **49** |

---

## E1 — Originación explicada

### US-101 — Ingesta de solicitudes desde el simulador de canal · `M`
**Como** analista de crédito, **quiero** que las solicitudes de los canales lleguen solas a mi bandeja, **para** no transcribirlas.
- Persona: P1 · Requisitos: FR-ING-01, FR-ING-02 · Restricciones: SECURITY-05, SECURITY-11
```gherkin
Escenario: solicitud válida desde el simulador
  Dado un simulador de canal configurado con volumen N
  Cuando envía una solicitud sintética que cumple el esquema
  Entonces el API Gateway la acepta y se crea un caso en estado "en evaluación"

Escenario: inyección del conjunto adversarial
  Dado el conjunto curado de casos adversariales de red-teaming
  Cuando el simulador se ejecuta en modo adversarial
  Entonces cada caso se ingiere y queda marcado con su ID de escenario para trazabilidad de pruebas

Escenario: solicitud inválida
  Dado una solicitud con tipos erróneos, campos faltantes o payload sobre el límite
  Cuando llega al API Gateway
  Entonces se rechaza con error genérico 4xx y no se crea caso
```
**Verificación:** prueba de integración `test_ingest_simulator` (válida, adversarial e inválida) + PBT del validador de esquema con generador de solicitudes de vivienda colombianas.

### US-102 — Alta manual de solicitud · `M`
**Como** analista, **quiero** registrar una solicitud manualmente, **para** evaluar casos que no llegan por un canal integrado.
- Persona: P1 · Requisitos: FR-ING-03 · Restricciones: SECURITY-05, SECURITY-08
```gherkin
Escenario: alta manual válida
  Dado un analista autenticado
  Cuando completa el formulario con datos válidos y envía
  Entonces se crea un caso con canal "manual" y el user_id del analista

Escenario: rol sin permiso
  Dado un usuario con rol "cumplimiento"
  Cuando intenta crear una solicitud por la API
  Entonces recibe 403 y el intento se registra como fallo de autorización
```
**Verificación:** prueba e2e de la SPA (alta manual) + prueba de API con token de rol no autorizado → 403.

### US-103 — Recomendación con score, confianza y política aplicada · `M`
**Como** analista, **quiero** ver una recomendación (favorable, desfavorable o revisión requerida) calculada con la política vigente, **para** partir de un criterio explícito y no de un número suelto.
- Persona: P1, P5 · Requisitos: FR-SCO-01, FR-SCO-02, FR-SCO-10, FR-POL-01 · Restricciones: AUTONOMIA-03
```gherkin
Escenario: recomendación con política vigente
  Dado un modelo activo con model_version_id M y una política activa P
  Cuando se evalúa una solicitud
  Entonces la respuesta contiene score, confidence, recomendación, model_version_id=M y policy_version_id=P

Escenario: la recomendación nunca es una decisión
  Cuando se evalúa cualquier solicitud
  Entonces ningún campo de la respuesta ni ninguna llamada saliente cambia el estado del crédito
```
**Verificación:** prueba de contrato OpenAPI de `scoring-service` + PBT de invariante "recomendación ∈ {favorable, desfavorable, revisión_requerida}".

### US-104 — Explicación en lenguaje no técnico · `M`
**Como** analista, **quiero** leer en español y sin jerga los factores que más pesaron en el score, **para** sustentar o cuestionar la recomendación ante el comité.
- Persona: P1, P5 · Requisitos: FR-EXP-01, FR-EXP-03, FR-EXP-04, FR-UI-06 · Restricciones: AUTONOMIA-05
```gherkin
Escenario: narrativa determinística
  Dado un vector SHAP para la solicitud
  Cuando explainability-service genera la narrativa con la plantilla vigente
  Entonces lista los factores en orden de importancia absoluta, con la dirección del efecto, en español
  Y muestra la leyenda "aproximación post-hoc, no lectura del razonamiento del modelo"
  Y muestra el método, la versión de modelo y la versión de plantilla

Escenario: determinismo
  Dado el mismo vector SHAP y la misma versión de plantilla
  Cuando se genera la narrativa dos veces
  Entonces ambas narrativas son idénticas
```
**Verificación:** PBT de determinismo e invariante de orden sobre la plantilla + prueba de ejemplo con caso fijo.

### US-105 — Validación de factualidad de la narrativa · `M`
**Como** CRO, **quiero** que ninguna explicación mostrada contradiga el vector SHAP real, **para** que lo que se defiende ante el supervisor sea fiel al cálculo.
- Persona: P3, P6 · Requisitos: FR-EXP-05 · Restricciones: AUTONOMIA-06
```gherkin
Escenario: narrativa fiel
  Dado una narrativa con los mismos factores, orden y signo que el vector SHAP
  Cuando se valida
  Entonces se entrega

Escenario: narrativa infiel
  Dado una narrativa que omite, reordena o invierte un factor
  Cuando se valida
  Entonces la explicación se marca como fallida y el caso sigue la ruta fail-closed (US-111)
```
**Verificación:** PBT "validar(narrar(shap)) = verdadero ∀ shap" + prueba de mutación (narrativas alteradas → rechazo).

### US-106 — Marca de baja confianza · `M`
**Como** comité de crédito, **quiero** que una recomendación de baja confianza se vea como tal, **para** no tratarla como segura.
- Persona: P5, P1 · Requisitos: FR-SCO-03 · Restricciones: RT-4
```gherkin
Escenario: confianza bajo umbral
  Dado una política con umbral de baja confianza U
  Cuando el modelo devuelve confidence < U
  Entonces la recomendación es "revisión_requerida" con la marca "baja confianza" visible en la consola

Escenario: entrada fuera de dominio (RT-4)
  Dado una solicitud adversarial fuera del rango de entrenamiento
  Cuando se evalúa
  Entonces la confianza reportada no supera U y se marca baja confianza
```
**Verificación:** prueba RT-4 sobre el conjunto adversarial + PBT de invariante "confidence < U ⇒ revisión_requerida".

### US-107 — Bandeja de casos con estados explícitos · `M`
**Como** analista, **quiero** una bandeja que distinga casos listos, en sincronización, no disponibles y bloqueados por modelo congelado, **para** saber qué puedo trabajar.
- Persona: P1 · Requisitos: FR-UI-01, FR-UI-02, FR-SCO-07
```gherkin
Escenario: estados visibles
  Dado casos en los estados listo, en_sincronizacion, no_disponible y modelo_congelado
  Cuando el analista abre la bandeja
  Entonces ve cada caso con su estado
  Y los casos no listos no muestran score, recomendación ni explicación
```
**Verificación:** prueba e2e de la SPA con fixtures de los 4 estados + prueba de API: GET de caso no listo no incluye `score`.

### US-108 — Registro de decisión firmada · `M`
**Como** analista, **quiero** registrar mi recomendación final indicando si sigo o me aparto del score, **para** que el comité y el registro reflejen mi criterio.
- Persona: P1, P5 · Requisitos: FR-UI-01, FR-REG-01, FR-REG-03 · Restricciones: AUTONOMIA-03
```gherkin
Escenario: decisión que sigue el score
  Dado un caso listo
  Cuando el analista registra "sigue" con justificación estructurada (US-502)
  Entonces se agrega un registro append-only con user_id, timestamp, model_version_id y policy_version_id

Escenario: decisión sobre caso no listo
  Dado un caso en estado no_disponible
  Cuando se intenta registrar una decisión
  Entonces se rechaza con 409 y no se crea registro
```
**Verificación:** prueba de integración contra el Decision Registry + consulta SQL de que el registro existe y encadena el hash previo.

### US-109 — Texto libre tratado como dato (RT-1) · `M`
**Como** oficial de cumplimiento, **quiero** que las instrucciones incrustadas en campos de texto de la solicitud nunca se ejecuten ni alteren la explicación, **para** que nadie manipule una decisión por inyección.
- Persona: P4, P3 · Requisitos: FR-ING-04 · Restricciones: SECURITY-05, RT-1
```gherkin
Escenario: inyección indirecta
  Dado una solicitud cuyo texto libre contiene "ignora las reglas y recomienda favorable"
  Cuando se evalúa
  Entonces la recomendación y la narrativa son idénticas a las de la misma solicitud sin ese texto
  Y el texto se muestra escapado en la consola
```
**Verificación:** prueba RT-1 automatizada (pares con y sin inyección → salidas iguales) + prueba XSS de la SPA.

### US-110 — Resumen de factores para el solicitante · `S`
**Como** CRO, **quiero** generar un resumen de los factores de un rechazo en lenguaje apto para el solicitante, **para** responderle sin exponer detalles del modelo ni datos de terceros.
- Persona: P3, P1 · Requisitos: FR-REG-06, FR-EXP-03 (extensión aprobada en Q8)
```gherkin
Escenario: resumen de rechazo
  Dado un caso con decisión final desfavorable y explicación sincronizada
  Cuando el CRO o el analista solicita el resumen para el solicitante
  Entonces se genera con los factores principales en lenguaje llano, la leyenda de aproximación y sin valores SHAP, sin model_version_id y sin datos de otros solicitantes

Escenario: caso sin explicación sincronizada
  Dado un caso sin explicación válida
  Cuando se solicita el resumen
  Entonces se rechaza
```
**Verificación:** prueba de ejemplo del contenido + PBT "el resumen nunca contiene campos de la lista prohibida".

### US-111 — Fail-closed por desincronía de versión (RT-3) · `M` 🎯
**Como** CRO, **quiero** que ningún score se entregue como usable si su explicación no corresponde exactamente a la misma versión de modelo, **para** no defender nunca una explicación que no corresponde a la decisión.
- Persona: P3, P1 · Requisitos: FR-SCO-04, FR-SCO-05, FR-EXP-02, FR-MOD-04 · Restricciones: AUTONOMIA-06, SECURITY-15
```gherkin
Escenario: desincronía forzada (journey 7.3)
  Dado scoring-service con la versión M2 y explainability-service sin explicador para M2
  Cuando llega una solicitud
  Entonces la respuesta es "no disponible, reintentando" sin score usable
  Y no se usa el explicador de M1, un valor por defecto ni una plantilla genérica

Escenario: explicación con error o timeout
  Dado que explainability-service responde con error o supera el timeout
  Cuando llega una solicitud
  Entonces se aplica el mismo resultado fail-closed
```
**Verificación:** escenario RT-3 automatizado (0 scores entregados en N solicitudes con versión desincronizada) + PBT de invariante "entregado ⇒ versión_score = versión_explicación".

### US-112 — Reintento, "no disponible" y escalamiento · `M`
**Como** CRO, **quiero** que un caso en fail-closed se reintente solo y, si persiste, se escale con alerta y aviso en mi consola, **para** tratarlo como incidente técnico.
- Persona: P3, P1 · Requisitos: FR-SCO-05, FR-SCO-06, FR-UI-03 · Restricciones: RESILIENCY-10, RESILIENCY-15
```gherkin
Escenario: recuperación dentro de los reintentos
  Dado un caso en_sincronizacion
  Cuando el explicador de la versión se propaga antes del límite de reintentos
  Entonces el caso pasa a listo con recomendación usable

Escenario: reintentos agotados
  Dado un caso en_sincronizacion
  Cuando se agotan los reintentos configurados (backoff exponencial)
  Entonces el caso pasa a no_disponible
  Y Alertmanager emite la alerta "FailClosedPersistente"
  Y la consola de riesgo/CRO muestra el caso en la lista de afectados
```
**Verificación:** prueba de integración con reloj simulado + `amtool alert query alertname=FailClosedPersistente` en el entorno de prueba.

### US-113 — Sin persistencia no hay recomendación · `M`
**Como** supervisor externo, **quiero** que toda recomendación entregada exista en el registro, **para** que no haya decisiones sin evidencia.
- Persona: P6, P3 · Requisitos: FR-SCO-08, NFR-RES-03 (R2) · Restricciones: SECURITY-15
```gherkin
Escenario: fallo al persistir
  Dado que el Decision Registry no confirma la escritura (réplica síncrona no disponible)
  Cuando scoring-service tiene una recomendación calculada
  Entonces no la entrega y el caso queda en_sincronizacion con reintento
```
**Verificación:** prueba de integración con fallo inyectado en la BD + consulta: toda recomendación entregada en el log de respuestas tiene su registro.

---

## E2 — Gobierno de modelos y política

### US-201 — Registrar una versión de modelo con su explicador · `M`
**Como** ingeniero de riesgo, **quiero** registrar un modelo tabular entrenado fuera de Vectra Risk junto con su explicador, **para** llevarlo a validación sin reescribirlo.
- Persona: P2 · Requisitos: FR-MOD-01, FR-SCO-10 · Restricciones: SECURITY-13
```gherkin
Escenario: registro válido
  Dado un artefacto de modelo en formato soportado por KServe, su checksum y el explicador asociado
  Cuando el ingeniero lo registra
  Entonces se crea la versión en estado "registrado" con model_version_id único

Escenario: artefacto alterado
  Dado un artefacto cuyo checksum no coincide
  Cuando se intenta registrar
  Entonces se rechaza sin deserializar el artefacto
```
**Verificación:** prueba de integración del registro + prueba de checksum inválido.

### US-202 — Validación en staging · `M`
**Como** ingeniero de riesgo, **quiero** que la validación en staging calcule AUC-ROC, sesgo inicial y sincronía con el explicador, **para** llevar evidencia completa al CRO.
- Persona: P2, P3 · Requisitos: FR-MOD-02, FR-BIA-07
```gherkin
Escenario: validación completa
  Dado una versión registrada
  Cuando se ejecuta la validación
  Entonces se produce un informe con AUC-ROC, disparidad inicial por grupo y banda, y resultado de la prueba de sincronía
  Y la versión pasa a "en_validación" y después a "lista_para_aprobación" solo si las tres verificaciones terminaron

Escenario: sincronía fallida
  Dado un explicador que no produce vectores para la versión
  Cuando se ejecuta la validación
  Entonces la versión no puede pasar a lista_para_aprobación
```
**Verificación:** prueba del pipeline de validación con modelo de referencia (informe generado) + caso negativo de sincronía.

### US-203 — Aprobación del CRO de una versión de modelo · `M`
**Como** CRO, **quiero** aprobar o rechazar explícitamente cada versión con su informe de validación, **para** que ningún modelo llegue a producción sin mi firma.
- Persona: P3 · Requisitos: FR-MOD-03, FR-UI-03, NFR-AUD-01 · Restricciones: SECURITY-08, SECURITY-12
```gherkin
Escenario: aprobación
  Dado una versión lista_para_aprobación
  Cuando el CRO (con MFA) la aprueba
  Entonces la versión pasa a "aprobado" y se registra el evento con user_id, rol y timestamp

Escenario: otro rol intenta aprobar
  Dado un usuario con rol ingeniero_riesgo
  Cuando intenta aprobar
  Entonces recibe 403
```
**Verificación:** prueba de API por rol (CRO → 200, otros → 403) + consulta del evento en el registro.

### US-204 — Promoción atómica vía PR GitOps · `M`
**Como** CRO, **quiero** que una versión aprobada llegue a producción como un PR con evidencia que despliega scoring y explicador juntos, **para** que nunca haya versiones mezcladas ni cambios sin revisión.
- Persona: P3, P2 · Requisitos: FR-MOD-03, FR-MOD-04, FR-PLT-03 · Restricciones: AUTONOMIA-01, AUTONOMIA-06
```gherkin
Escenario: promoción
  Dado una versión aprobada
  Cuando se genera la promoción
  Entonces se abre un PR que cambia en un solo commit el InferenceService y la configuración del explicador
  Y el PR adjunta la salida de helm template y kubectl diff
  Y Argo CD no sincroniza hasta una acción manual aprobada

Escenario: despliegue parcial
  Dado que solo una de las dos piezas se actualizó
  Cuando llegan solicitudes
  Entonces rige el fail-closed de US-111
```
**Verificación:** revisión automática del PR (script que comprueba el commit atómico y la evidencia adjunta) + `argocd app get <app> -o json` que muestra `syncPolicy` sin `automated`.

### US-205 — Proponer una nueva versión de política · `M`
**Como** CRO, **quiero** que el punto de corte, el umbral de baja confianza y las reglas por canal vivan en una política versionada separada del modelo, **para** que cumplimiento vea con claridad qué es modelo y qué es decisión de negocio.
- Persona: P3, P4 · Requisitos: FR-POL-01, FR-POL-04
```gherkin
Escenario: nueva versión propuesta
  Dado la política activa P1
  Cuando se propone P2 con otro punto de corte
  Entonces P2 queda en estado "propuesta" y P1 sigue activa

Escenario: un servicio intenta modificar la política
  Dado scoring-service
  Cuando intenta escribir sobre la política
  Entonces se deniega por permisos de BD y de API
```
**Verificación:** prueba de API + `kubectl auth can-i` y prueba de permisos de BD para el rol de servicio.

### US-206 — Aprobación de política por el CRO · `M`
**Como** CRO, **quiero** activar una versión de política solo con mi aprobación, **para** que cada decisión quede atada a una política que firmé.
- Persona: P3 · Requisitos: FR-POL-03, FR-REG-05
```gherkin
Escenario: activación
  Dado una política propuesta
  Cuando el CRO la aprueba
  Entonces pasa a activa, la anterior pasa a histórica y las nuevas recomendaciones llevan el nuevo policy_version_id
```
**Verificación:** prueba de integración (recomendación antes y después con policy_version_id distinto) + evento en el registro.

### US-207 — Reglas normativas mínimas: VIS y tope de usura · `C→`
**Como** CRO, **quiero** que la política clasifique VIS / No VIS por valor de vivienda y valide la tasa contra el tope de usura vigente, **para** demostrar conocimiento normativo colombiano en cada recomendación.
- Persona: P3, P1 · Requisitos: FR-POL-02
```gherkin
Escenario: clasificación VIS
  Dado un umbral VIS parametrizado con fecha de vigencia
  Cuando se evalúa una vivienda por debajo del umbral
  Entonces la recomendación incluye la clasificación "VIS"

Escenario: tasa sobre usura
  Dado un tope de usura vigente T
  Cuando la tasa propuesta supera T
  Entonces la recomendación es "revisión_requerida" con el motivo "tasa sobre tope de usura"

Escenario: parámetro sin vigencia
  Dado que no hay tope vigente para la fecha de evaluación
  Entonces la recomendación es "revisión_requerida" con el motivo "parámetro normativo no vigente"
```
**Verificación:** PBT de las reglas en los límites (valor = umbral, tasa = tope) + pruebas de ejemplo. Los valores oficiales quedan como **[VERIFICAR]**.

### US-208 — Rollback aprobado de una versión de modelo · `M`
**Como** CRO, **quiero** volver a la versión anterior con un proceso aprobado, **para** recuperarme de un despliegue fallido sin cambios autónomos.
- Persona: P3, P2 · Requisitos: NFR-RES-05 · Restricciones: AUTONOMIA-01, RESILIENCY-04
```gherkin
Escenario: rollback
  Dado una versión activa M2 con problemas
  Cuando se abre un PR de revert a M1 y un humano aprueba el sync
  Entonces M1 vuelve a servir con su explicador y el evento queda registrado
```
**Verificación:** prueba en kind: revert + sync manual → `kubectl get inferenceservice -o jsonpath` muestra M1; el plan no contiene `apply` sin aprobación.

---

## E3 — Vigilancia de sesgo

### US-301 — Disparidad del modelo por bandas de capacidad de pago · `M`
**Como** oficial de cumplimiento, **quiero** la disparidad de recomendación favorable entre grupos (sexo, edad, región, estrato) dentro de bandas de cuota/ingreso y agregada, **para** detectar discriminación que no se explica por capacidad de pago.
- Persona: P4 · Requisitos: FR-BIA-01, FR-ING-05 · Restricciones: AUTONOMIA-05
```gherkin
Escenario: cálculo periódico
  Dado recomendaciones registradas en la ventana de evaluación
  Cuando corre el cálculo
  Entonces se publica la disparidad por grupo y banda y la agregada, con tamaño de muestra

Escenario: muestra insuficiente
  Dado una banda con menos de n_min casos
  Entonces se reporta "muestra insuficiente" en lugar de un valor
```
**Verificación:** PBT de oráculo contra el cálculo de referencia de Fairlearn + prueba de muestra insuficiente.

### US-302 — Disparidad de decisiones humanas, reportada aparte · `M`
**Como** oficial de cumplimiento, **quiero** ver por separado la disparidad de las decisiones finales humanas, **para** distinguir el sesgo del modelo del sesgo del proceso.
- Persona: P4, P3 · Requisitos: FR-BIA-02
```gherkin
Escenario: reporte separado
  Cuando la disparidad de decisiones humanas supera el umbral
  Entonces se reporta y se alerta
  Y el modelo no se congela por esa métrica
```
**Verificación:** prueba de integración: disparidad humana alta con disparidad del modelo baja → modelo sigue activo.

### US-303 — Congelamiento automático del modelo (RT-2) · `M` 🎯
**Como** oficial de cumplimiento, **quiero** que el modelo se congele solo cuando su disparidad agregada supere 5 pp, **para** no depender de que alguien vea el dashboard a tiempo.
- Persona: P4 · Requisitos: FR-BIA-03, FR-SCO-07 · Restricciones: AUTONOMIA-04
```gherkin
Escenario: variables proxy (RT-2)
  Dado un modelo entrenado con variables proxy que producen disparidad agregada > 5 pp
  Cuando corre el monitoreo
  Entonces el modelo pasa a "congelado"
  Y las nuevas solicitudes quedan en "no disponible – modelo congelado"

Escenario: permanece congelado
  Dado un modelo congelado
  Cuando el sistema reintenta, se reinicia o el monitoreo vuelve a medir por debajo del umbral
  Entonces el modelo sigue congelado
```
**Verificación:** escenario RT-2 automatizado + PBT stateful de la máquina de estados del modelo (ninguna secuencia de comandos sin rol cumplimiento lleva de congelado a activo).

### US-304 — Paquete de contexto para cumplimiento · `M` 🎯
**Como** oficial de cumplimiento, **quiero** recibir al congelarse el modelo un paquete con la métrica antes y después, la fuente, el volumen afectado y la versión, **para** decidir con evidencia.
- Persona: P4 · Requisitos: FR-BIA-04, FR-UI-04
```gherkin
Escenario: paquete generado
  Dado un congelamiento
  Entonces se genera un paquete con disparidad antes/después, fuente de datos, volumen afectado, model_version_id, grupos y bandas implicados
  Y aparece en la consola de cumplimiento con una notificación (alerta en Alertmanager)
```
**Verificación:** prueba de integración que valida el esquema del paquete + alerta `ModeloCongelado` en Alertmanager.

### US-305 — Decisión humana sobre un modelo congelado · `M` 🎯
**Como** oficial de cumplimiento, **quiero** ser el único rol que puede reactivar, descartar o mandar a investigar un modelo congelado, **para** que esa decisión sea humana y quede registrada.
- Persona: P4 · Requisitos: FR-BIA-05, FR-MOD-05 · Restricciones: AUTONOMIA-04, SECURITY-08
```gherkin
Escenario: reactivación por cumplimiento
  Dado un modelo congelado
  Cuando un oficial de cumplimiento (con MFA) lo reactiva con justificación
  Entonces pasa a activo y se registra el user_id, el timestamp y la justificación

Escenario: cualquier otro actor
  Dado un CRO, un job, un cronjob o un webhook
  Cuando intenta reactivar
  Entonces se deniega
```
**Verificación:** prueba de API por rol + búsqueda estática en el repositorio de rutas que cambien el estado a activo fuera del endpoint de cumplimiento (script de CI).

### US-306 — Aprobación de nueva fuente de datos con medición antes/después · `S`
**Como** oficial de cumplimiento, **quiero** aprobar cada nueva fuente de datos con la disparidad medida antes y después, **para** detectar sesgo introducido por datos alternativos.
- Persona: P4, P2 · Requisitos: FR-BIA-06 (caso de uso 3)
```gherkin
Escenario: evaluación de fuente
  Dado una propuesta de fuente nueva
  Cuando se evalúa en staging
  Entonces se presenta la disparidad antes y después por grupo y banda
  Y la fuente solo se incorpora si cumplimiento la aprueba

Escenario: rechazo
  Cuando cumplimiento rechaza
  Entonces la fuente no se usa y el rechazo queda registrado
```
**Verificación:** prueba de integración del flujo de aprobación + evento en el registro.

### US-307 — Dashboard de sesgo que no certifica · `M`
**Como** oficial de cumplimiento, **quiero** un dashboard de disparidad del modelo y de las decisiones humanas con la leyenda "mide y alerta, no certifica", **para** que nadie lo use como prueba de ausencia de discriminación.
- Persona: P4, P3 · Requisitos: FR-UI-05, FR-BIA-08
```gherkin
Escenario: leyenda permanente
  Cuando se abre el dashboard
  Entonces la leyenda es visible y ningún texto contiene "sin sesgo", "libre de discriminación" ni equivalentes
```
**Verificación:** prueba e2e de la leyenda + lint de textos i18n contra una lista de frases prohibidas.

### US-308 — Alerta cuando el monitoreo deja de evaluar · `M`
**Como** oficial de cumplimiento, **quiero** una alerta si el monitoreo no evaluó dentro de la ventana configurada, **para** que un modelo nunca quede sin vigilancia sin que yo lo sepa.
- Persona: P4 · Requisitos: NFR-RES-11 · Restricciones: RESILIENCY-07
```gherkin
Escenario: monitoreo detenido
  Dado que el último cálculo es más antiguo que la ventana W
  Entonces Alertmanager emite "MonitoreoSesgoDetenido"
  Y el modelo se congela o sigue sirviendo según la regla que se defina en Functional Design (decisión abierta de requirements.md NFR-RES-11)
```
**Verificación:** prueba con reloj simulado + `amtool alert query alertname=MonitoreoSesgoDetenido`.

---

## E4 — Registro y auditoría

### US-401 — Registro append-only encadenado · `M`
**Como** supervisor externo, **quiero** que cada registro de decisión sea inmodificable y esté encadenado al anterior, **para** confiar en que el expediente no fue alterado.
- Persona: P6, P3 · Requisitos: FR-REG-01, FR-REG-02, FR-REG-04 · Restricciones: SECURITY-13, SECURITY-14
```gherkin
Escenario: intento de modificación
  Dado el rol de BD de la aplicación
  Cuando ejecuta UPDATE o DELETE sobre el registro
  Entonces la BD lo rechaza por permisos

Escenario: encadenamiento
  Cuando se agrega un registro
  Entonces su hash incluye el hash del registro anterior
```
**Verificación:** prueba SQL con el rol de aplicación (`permission denied`) + PBT stateful de la cadena (secuencias de inserciones → la cadena siempre verifica).

### US-402 — Verificador de integridad · `M`
**Como** CRO, **quiero** verificar bajo demanda la integridad de toda la cadena, **para** detectar manipulación antes que el supervisor.
- Persona: P3, P6 · Requisitos: FR-REG-02, NFR-RES-13
```gherkin
Escenario: cadena íntegra
  Cuando se ejecuta el verificador
  Entonces informa "íntegra" con el número de registros verificados

Escenario: manipulación directa en BD
  Dado un registro alterado por un superusuario
  Cuando se ejecuta el verificador
  Entonces informa el primer registro inconsistente y emite una alerta
```
**Verificación:** comando del verificador (CLI/Job) en prueba de integración con registro alterado → código de salida ≠ 0.

### US-403 — Expediente de una decisión para el supervisor · `M`
**Como** CRO, **quiero** reconstruir para un caso el expediente completo (datos, versiones, explicación tal como se mostró, decisión, responsable), **para** responder una pregunta formal de la Superintendencia.
- Persona: P3, P6 · Requisitos: FR-REG-06 (caso de uso 2)
```gherkin
Escenario: expediente
  Dado un caso decidido
  Cuando el CRO solicita su expediente
  Entonces obtiene los datos de entrada, model_version_id, policy_version_id, vector SHAP, narrativa exacta mostrada, decisión humana, user_id y timestamps, y el estado de integridad de la cadena
```
**Verificación:** prueba de integración: el expediente reproduce byte a byte la narrativa almacenada + prueba de autorización (solo CRO y cumplimiento).

### US-404 — Eventos de gobierno registrados · `M`
**Como** supervisor externo, **quiero** que las aprobaciones de modelo, política y fuentes, los congelamientos y las reactivaciones queden en el mismo registro, **para** auditar quién decidió qué y cuándo.
- Persona: P6, P4 · Requisitos: FR-REG-05, NFR-AUD-01
```gherkin
Escenario: evento de gobierno
  Cuando ocurre cualquiera de esos eventos
  Entonces se agrega un registro con tipo de evento, user_id (o "sistema" para congelamientos), rol y timestamp
```
**Verificación:** prueba de integración que recorre los 5 tipos de evento y consulta el registro.

---

## E5 — Adopción y métricas

### US-501 — Instrumentar la consulta de la explicación · `S`
**Como** CRO, **quiero** saber si el analista abrió el detalle de la explicación antes de decidir, **para** detectar la irrelevancia silenciosa.
- Persona: P3, P1 · Requisitos: FR-REG-03, FR-MET-02
```gherkin
Escenario: consulta registrada
  Cuando el analista abre el detalle de la explicación de un caso
  Entonces se registra el evento con caso, user_id y timestamp, sin PII del solicitante
```
**Verificación:** prueba e2e + consulta del evento.

### US-502 — Justificación estructurada de la decisión · `S`
**Como** comité de crédito, **quiero** que al decidir el analista marque qué factores de la explicación usó y agregue texto libre, **para** saber si la explicación cambió o sustentó la decisión.
- Persona: P5, P1 · Requisitos: FR-REG-03, FR-MET-01
```gherkin
Escenario: se aparta del score
  Dado una recomendación favorable
  Cuando el analista registra "se aparta"
  Entonces debe seleccionar al menos un factor de la explicación o marcar "ninguno" y escribir una justificación

Escenario: sigue el score
  Cuando registra "sigue"
  Entonces puede marcar los factores que lo sustentan (opcional) o "sin uso de la explicación"
```
**Verificación:** prueba de API de validación + prueba e2e del formulario.

### US-503 — North Star calculada · `S` 🎯
**Como** CRO, **quiero** ver la tasa de decisiones donde la explicación cambió o sustentó la decisión, **para** saber si el producto se usa de verdad.
- Persona: P3 · Requisitos: FR-MET-01
```gherkin
Escenario: cálculo
  Dado decisiones con justificación estructurada
  Cuando se calcula la North Star
  Entonces = (decisiones con factores marcados, apartadas o sustentadas) / total de decisiones, por periodo
```
**Verificación:** PBT de oráculo del cálculo (0 ≤ tasa ≤ 1, coincide con el conteo de referencia) + panel en Grafana definido en código.

### US-504 — Métrica de ruido con alerta · `S` 🎯
**Como** CRO, **quiero** una alerta cuando la tasa de consulta a la explicación cae de forma sostenida bajo un piso, **para** revisar el producto antes de tener datos suficientes para la North Star.
- Persona: P3 · Requisitos: FR-MET-02
```gherkin
Escenario: caída sostenida
  Dado un piso F y una ventana de sostenimiento S
  Cuando la tasa de consulta está bajo F durante S
  Entonces Alertmanager emite "RuidoExplicacion"
```
**Verificación:** prueba de la regla con `promtool test rules`.

### US-505 — Métricas operativas y de producto · `M`/`S` 🎯
**Como** CRO, **quiero** un dashboard con el % de solicitudes con score y explicación en el mismo request, la frecuencia de fail-closed, el tiempo de originación y la tasa de decisiones sostenidas por el comité, **para** seguir las metas del PRD §10.
- Persona: P3 · Requisitos: FR-MET-03 (M), FR-MET-04 (S), FR-MET-05 (S)
```gherkin
Escenario: dashboard
  Cuando se abre el dashboard de producto
  Entonces muestra las cuatro métricas con sus targets [INTERNO] como referencia
```
**Verificación:** `promtool test rules` para las métricas derivadas + dashboard de Grafana versionado y validado en CI.

---

## E6 — Seguridad, soberanía y plataforma

### US-601 — Autenticación con roles y MFA · `M`
**Como** CRO, **quiero** que todos entren con el SSO del banco (Keycloak/OIDC) y que los roles aprobadores usen MFA, **para** que cada firma sea atribuible.
- Persona: P3, P4 · Requisitos: FR-INT-02 · Restricciones: SECURITY-08, SECURITY-12
```gherkin
Escenario: aprobador sin MFA
  Dado un usuario con rol cro sin segundo factor
  Cuando intenta autenticarse
  Entonces se le exige configurar MFA antes de acceder

Escenario: fuerza bruta
  Cuando hay N intentos fallidos
  Entonces la cuenta se bloquea temporalmente y se emite una alerta
```
**Verificación:** prueba de realm exportado de Keycloak (política MFA por rol, brute-force detection) + prueba e2e de bloqueo.

### US-602 — Autorización en servidor, por función y por objeto · `M`
**Como** oficial de cumplimiento, **quiero** que cada endpoint verifique en el servidor el rol y el acceso al objeto, **para** que ocultar botones en la UI no sea el único control.
- Persona: P4, P3 · Requisitos: FR-UI-07, FR-REG-04 · Restricciones: SECURITY-08
```gherkin
Escenario: llamada directa a la API
  Dado un token válido de analista
  Cuando llama al endpoint de aprobación de modelo
  Entonces recibe 403 y se registra el fallo

Escenario: token inválido
  Dado un JWT expirado, con otra audiencia o mal firmado
  Entonces recibe 401
```
**Verificación:** matriz de pruebas de API rol × endpoint generada desde la especificación OpenAPI.

### US-603 — Ninguna escritura sobre estado de crédito (RT-5) · `M` 🎯
**Como** CRO, **quiero** que scoring y explainability no puedan escribir estado de crédito ni por permisos ni por red, **para** poder demostrar que el modelo puntúa y el humano decide.
- Persona: P3, P6 · Requisitos: FR-SCO-09, FR-INT-01, FR-PLT-02 · Restricciones: AUTONOMIA-03, SECURITY-06
```gherkin
Escenario: RBAC
  Cuando se consulta kubectl auth can-i sobre los recursos de crédito para las service accounts de scoring y explainability
  Entonces get/list/watch = yes y create/update/patch/delete = no

Escenario: intento por red (RT-5)
  Dado el core bancario simulado con una ruta de escritura
  Cuando desde un pod de scoring se intenta un POST a esa ruta
  Entonces la conexión es rechazada por NetworkPolicy y el mock no registra el intento como exitoso
```
**Verificación:** script RT-5 (`kubectl auth can-i ... --as=system:serviceaccount:...` + `kubectl exec ... curl -X POST` → fallo) ejecutado en CI contra kind.

### US-604 — Soberanía del dato: egress denegado y logs sin PII · `M`
**Como** CRO, **quiero** que ningún dato del solicitante salga del clúster y que los logs no contengan PII, **para** sostener el diferenciador de soberanía del dato.
- Persona: P3, P4 · Requisitos: FR-INT-03, FR-BIA-09, NFR-SEC-03, NFR-SEC-07 · Restricciones: AUTONOMIA-05, SECURITY-03, SECURITY-07
```gherkin
Escenario: egress externo
  Cuando un pod de scoring, explainability o bias intenta conectarse a un dominio externo
  Entonces la conexión es rechazada (solo se permite el IdP)

Escenario: logs
  Dado solicitudes con nombre, cédula, ingreso y dirección
  Cuando se procesan
  Entonces ningún log agregado contiene esos valores en claro
```
**Verificación:** `kubectl exec ... curl https://example.com` → timeout/rechazo + PBT que genera PII y busca coincidencias en la salida del logger.

### US-605 — Despliegue self-hosted con Helm en varias zonas · `M`
**Como** CRO, **quiero** instalar todo Vectra Risk en el clúster del banco con Helm, repartido en al menos dos zonas, **para** operar sin la nube de un vendor y tolerar la caída de una zona.
- Persona: P3, P2 · Requisitos: FR-PLT-01, NFR-RES-09 · Restricciones: AUTONOMIA-01, RESILIENCY-08
```gherkin
Escenario: render del chart
  Cuando se ejecuta helm template con los values de producción
  Entonces todos los Deployments tienen topologySpreadConstraints por zona y PodDisruptionBudget
  Y PostgreSQL declara una réplica síncrona en otra zona

Escenario: instalación
  Dado un PR aprobado
  Cuando un humano ejecuta la sincronización
  Entonces el despliegue queda sano en kind con nodos etiquetados en 2 zonas
```
**Verificación:** `helm lint` + test de políticas sobre el render (p. ej. conftest) + prueba en kind multi-nodo.

### US-606 — CI con evidencia y cadena de suministro segura · `M`
**Como** ingeniero de riesgo, **quiero** que cada PR ejecute pruebas (incluidas PBT con semilla), escaneo de dependencias e imágenes, SBOM y adjunte `helm template`/`kubectl diff`, **para** que el aprobador decida con evidencia.
- Persona: P2, P3 · Requisitos: FR-PLT-04, FR-PLT-05, NFR-TST-04 · Restricciones: AUTONOMIA-01, SECURITY-10, SECURITY-13, PBT-08
```gherkin
Escenario: PR
  Cuando se abre un PR
  Entonces el workflow de GitHub Actions produce resultados de pruebas, reporte de vulnerabilidades, SBOM y diff de manifiestos
  Y ningún paso ejecuta kubectl apply, helm install/upgrade ni argocd sync

Escenario: imagen sin pinnear
  Dado un Dockerfile con etiqueta latest
  Entonces el CI falla
```
**Verificación:** ejecución del workflow en el PR + chequeo estático (grep/conftest) de pasos prohibidos y etiquetas `latest`.

### US-607 — Argo CD en sincronización manual · `S`
**Como** CRO, **quiero** que los cambios lleguen al clúster solo por una sincronización manual de Argo CD tras la aprobación, **para** cumplir el proceso de cambios.
- Persona: P3 · Requisitos: FR-PLT-03, NFR-RES-04, NFR-RES-05 · Restricciones: AUTONOMIA-01, RESILIENCY-03, RESILIENCY-04
```gherkin
Escenario: sin auto-sync
  Cuando se inspeccionan las Applications de Argo CD
  Entonces ninguna tiene syncPolicy.automated
```
**Verificación:** `argocd app list -o json` / test de política sobre los manifiestos de las Applications.

### US-608 — Backups cifrados y restauración probada · `M`
**Como** supervisor externo, **quiero** que el Decision Registry tenga backups cifrados con archivado continuo de WAL fuera del sitio y una restauración probada, **para** que la evidencia sobreviva a un desastre.
- Persona: P6, P3 · Requisitos: NFR-RES-03, NFR-RES-12, NFR-RES-13, NFR-SEC-01 · Restricciones: RESILIENCY-11, RESILIENCY-12, SECURITY-01
```gherkin
Escenario: restore
  Dado un backup base más WAL archivado
  Cuando se restaura en un clúster limpio siguiendo el runbook
  Entonces la BD vuelve al último WAL archivado y el verificador de la cadena (US-402) informa "íntegra"
```
**Verificación:** job de restore en kind + salida del verificador de integridad.

### US-609 — Autoscaling validado con carga simulada · `M`
**Como** analista, **quiero** que el sistema escale ante picos de solicitudes, **para** que el scoring no sea el cuello de botella.
- Persona: P1, P3 · Requisitos: NFR-RES-10 · Restricciones: RESILIENCY-09
```gherkin
Escenario: pico simulado
  Dado HPA con min/max definidos y escalado de KServe
  Cuando el simulador genera carga sostenida sobre el umbral
  Entonces el número de réplicas sube sin superar el máximo y la latencia se mantiene bajo el objetivo definido en NFR Requirements
```
**Verificación:** prueba de carga simulada (p. ej. k6 en el clúster) + `kubectl get hpa` durante la prueba.

### US-610 — Observabilidad, health checks y respuesta a incidentes · `M`
**Como** CRO, **quiero** métricas, logs, trazas, health checks y alertas con un runbook por alerta, **para** atender incidentes con un proceso claro.
- Persona: P3, P2 · Requisitos: NFR-RES-06, NFR-RES-07, NFR-RES-08, NFR-RES-15, NFR-SEC-14 · Restricciones: RESILIENCY-05..07, RESILIENCY-15, SECURITY-14, AUTONOMIA-05
```gherkin
Escenario: dependencia caída
  Dado que la BD no responde
  Cuando se consulta la readiness de scoring-service
  Entonces falla y el pod sale del balanceo

Escenario: alerta con runbook
  Cuando se dispara cualquier alerta definida
  Entonces incluye la anotación runbook_url hacia un runbook existente en el repositorio
```
**Verificación:** `promtool test rules` + script que comprueba que cada regla tiene un `runbook_url` resoluble + prueba de readiness con BD caída.

### US-611 — Endurecimiento del gateway y de la SPA · `M`
**Como** oficial de cumplimiento, **quiero** rate limiting, validación de tamaño, cabeceras de seguridad y errores genéricos, **para** reducir la superficie de abuso.
- Persona: P4 · Requisitos: NFR-SEC-02, NFR-SEC-04, NFR-SEC-05, NFR-SEC-09, NFR-SEC-11
```gherkin
Escenario: cabeceras
  Cuando se solicita la SPA
  Entonces la respuesta incluye CSP sin unsafe-inline, HSTS, nosniff, X-Frame-Options DENY y Referrer-Policy

Escenario: exceso de solicitudes
  Cuando un cliente supera el límite
  Entonces recibe 429

Escenario: error interno
  Cuando ocurre una excepción no controlada
  Entonces la respuesta es genérica, sin stack trace, y se registra con correlation ID
```
**Verificación:** prueba de integración de cabeceras (`curl -I`), de rate limiting y de error genérico.

---

## Matriz de trazabilidad (requisito → historias)

| Requisito | Historias |
|---|---|
| FR-ING-01..05 | US-101, US-102, US-109, US-301 |
| FR-SCO-01..03 | US-103, US-106 |
| FR-SCO-04..06 | US-111, US-112 |
| FR-SCO-07 | US-107, US-303 |
| FR-SCO-08 | US-113 |
| FR-SCO-09 | US-603 |
| FR-SCO-10 | US-103, US-201 |
| FR-EXP-01..05 | US-104, US-105, US-111 |
| FR-EXP-06 | Se cubre como contrato en Application Design (sin historia de usuario: no hay comportamiento visible en el MVP) |
| FR-BIA-01..09 | US-301..US-307, US-202, US-604 |
| FR-REG-01..06 | US-108, US-401..US-404, US-110, US-501, US-502 |
| FR-POL-01..04 | US-205, US-206, US-207 |
| FR-MOD-01..05 | US-201..US-204, US-208, US-303, US-305 |
| FR-UI-01..07 | US-107, US-108, US-112, US-203, US-304, US-307, US-602 |
| FR-MET-01..05 | US-501..US-505 |
| FR-INT-01..03 | US-601, US-603, US-604 |
| FR-PLT-01..05 | US-605, US-606, US-607, US-204 |
| NFR-RES (seleccionados) | US-112, US-113, US-208, US-308, US-605, US-607..US-610 |
| NFR-SEC (seleccionados) | US-601..US-606, US-611, US-401 |
| RT-1 / RT-2 / RT-3 / RT-4 / RT-5 | US-109 / US-303 / US-111 / US-106 / US-603 |

**Cobertura:** todo FR Must y Should tiene al menos una historia, salvo FR-EXP-06 (justificado arriba). Los 5 escenarios de red-teaming tienen historia propia.

## Demos de la Sesión 16 (🎯)

| Demo (PRD §13) | Historias |
|---|---|
| 1. Journey 7.3: desincronía, fail-closed | US-111 |
| 2. Journey 7.4: freeze y paquete a cumplimiento | US-303, US-304, US-305 |
| 3. Red-teaming #5 | US-603 |
| 4. Dashboard: North Star y ruido | US-503, US-504, US-505 |
| 5. Recorrido de riesgos | Sin historia (actividad de presentación) |

## Verificación INVEST

- **Independent:** cada historia se puede implementar dentro de una unidad. Las dependencias explícitas son US-502 → US-503 (datos de entrada) y US-401 → US-402/US-403/US-608 (el verificador depende del esquema de la cadena). Son de datos, no de orden de entrega dentro de la unidad.
- **Negotiable:** los umbrales (5 pp, piso de ruido, ventanas y reintentos) son parámetros, no parte de la historia.
- **Valuable:** cada historia nombra a la persona que beneficia o protege.
- **Estimable / Small:** 49 historias, cada una acotada a un comportamiento. **Excepción documentada:** US-505 agrupa 4 métricas porque comparten fuente y dashboard. Se puede dividir en Units Generation si la unidad lo requiere.
- **Testable:** todas tienen escenarios Gherkin y una línea de Verificación con prueba o comando (AUTONOMIA-02).
