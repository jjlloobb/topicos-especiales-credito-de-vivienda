# Preguntas de seguimiento — Cuarta revisión de coherencia entre unidades

Resuelven lo que quedó abierto después de las correcciones del 2026-10-31. Escribe la letra de
tu elección después de cada `[Answer]:`; si eliges «Otro», describe tu respuesta ahí mismo.
Cuando termines, avísame y aplico las respuestas. Ninguna cambia nada hasta entonces.

Si quieres ir rápido, responde primero las marcadas con **Prioridad alta**: las demás pueden
esperar sin frenar a estas.

---

## Parte A — Confirmar decisiones que ya están aplicadas

La respuesta recomendada de estas preguntas deja los documentos como están.

## Pregunta 1 — Corridas de RT-2 · Prioridad alta

Aprobaste simular fechas UTC, pero no funciona: `evaluated_at` y `recorded_at` usan el reloj real.
Apliqué otra solución, una versión distinta del proxy por corrida, sin relajar BR-U9-08. Exige
registrar, validar y aprobar 5 versiones, y un PR de promoción por corrida. ¿Cómo debe quedar?

A) Mantener las 5 versiones del proxy, como está aplicado (Recomendado)

B) Una sola versión, con una corrida por día durante 5 días; misma medición, pero la verificación tarda casi una semana

C) Medir una sola corrida y cambiar `RT2-LATENCY`; es lo más barato, pero solo da una medición frente al objetivo de 30 min, con un margen que BR-U12-07 ya considera pequeño

D) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 2 — `version_mismatch` en ejecución · Prioridad alta

Los paquetes alterados se detienen en U4 o U6, así que la evidencia en kind de `journey-7-3` es
el explicador en 0 réplicas, que da `explainer_unavailable`. `version_mismatch` en ejecución queda
cubierto solo por pruebas de U7 con dobles. US-111 trata justamente de la desincronía de versión.
¿Es suficiente?

A) Sí: las barreras impiden la desincronía y las pruebas de U7 cubren la reacción (Recomendado)

B) No: agregar un escenario en kind que produzca `version_mismatch` real; exige un componente de prueba que responda con otra versión, solo en kind y con `conftest` que lo rechace en los demás entornos

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 3 — Alta disponibilidad de Grafana

Grafana quedó en 1 réplica con PVC, para no perder los permisos de carpeta. Mientras reinicia no
hay dashboards, pero Prometheus y las alertas siguen funcionando. ¿Es aceptable?

A) Sí: 1 réplica con PVC, como está aplicado (Recomendado)

B) No: 2 réplicas con una base PostgreSQL compartida; agrega un rol, un flujo y más operación

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 4 — Capacidad del pool de nodos · Prioridad alta

Con la cuota corregida de `vectra-serving`, las cuentas quedan justas. El pool `general` inicial
tiene 3 nodos por zona de 8 vCPU: 48 vCPU con 2 zonas. `vectra-serving` declara ≈ 17,16 CPU de
requests y `vectra-app` ≈ 26,4 sumando U3, U4, U7, U8 y U10, sin contar U9, U11, observabilidad ni
controladores. Son peores casos con margen, que no suelen coincidir, pero ya suman ≈ 43,6 de 48.
¿Cómo se resuelve?

A) Subir el mínimo de `general` a 4 nodos por zona (64 vCPU) y ajustar con la prueba de carga de U12 (Recomendado)

B) Crear un pool dedicado para `vectra-serving`; aísla mejor la inferencia, pero cuesta más nodos

C) Dejar 3 nodos por zona y decidir con la prueba de carga de U12; hay riesgo de pods sin programar durante una promoción

D) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 5 — Operador de CloudNativePG y mTLS

El operador está fuera de la malla, así que apliqué una excepción: `skip-inbound-ports` en el 8000
y `NetworkAuthentication` en el 5432. Ese tráfico queda protegido por NetworkPolicy y por el TLS
propio de CloudNativePG, no por la identidad de Linkerd. ¿La aceptas?

A) Sí: mantener la excepción y probarla con una conmutación por error en kind (Recomendado)

B) No: meter `cnpg-system` en la malla para que tenga identidad; hay que resolver su webhook (F81), porque el API server no pasa por la malla

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 6 — `data_sources` en RT-2

El oráculo ahora acepta `data_sources` vacía, porque el proxy no declara fuentes. Con eso, RT-2 no
demuestra que el paquete de congelamiento muestre fuentes reales. ¿Es suficiente?

A) Sí: el campo debe existir y puede ir vacío; una prueba de U9 cubre el caso con fuentes (Recomendado)

B) No: que el proxy declare una fuente sintética aprobada; exige hacer su ciclo completo antes de RT-2

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 7 — Código de una decisión incoherente

Dejé 409 `conflict_state` para BR-U0-35, porque U0 es la fuente autoritativa. El analista ve un
error general, no un error en el campo. El formulario ya evita este caso, así que solo debería
ocurrir si la recomendación cambió o con un cliente distinto. ¿Lo mantengo?

A) Sí: 409 `conflict_state`, como está aplicado (Recomendado)

B) No: cambiar BR-U0-35 a 422 con `invalid_params`, para mostrarlo en el campo

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

---

## Parte B — Puntos dudosos sin resolver

## Pregunta 8 — North Star: US-503 frente a BR-U11-03 · Prioridad alta

Es la métrica principal del producto y las dos definiciones no coinciden. US-503 cuenta decisiones
con factores marcados. BR-U11-03 exige además `explanation_viewed_before = true`. Según la visión,
se mide si la explicación cambia o sustenta materialmente la decisión. ¿Cuál vale?

A) BR-U11-03, con consulta previa, y actualizar US-503: un factor marcado sin ver la explicación no demuestra que esta influyera (Recomendado)

B) US-503, sin exigir consulta previa, y actualizar BR-U11-03; la tasa sale más alta, pero menos defendible

C) Publicar las dos: BR-U11-03 como North Star y la otra como métrica auxiliar

D) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 9 — Reactivación automatizada en RT-2 y FR-BIA-05 · Prioridad alta

FR-BIA-05 dice que ninguna ruta automática reactiva un modelo congelado. El plan de U12 tiene un
script que usa la semilla TOTP de `cumplimiento-1` para reactivarlo por el BFF. Está autenticado y
solo corre en kind, pero es automático y una auditoría puede preguntar por él. ¿Qué se hace?

A) Mantener el script solo en kind, documentar la excepción en FR-BIA-05 y exigir con `conftest` que usuario y semilla no existan en staging ni en producción (Recomendado)

B) Que un operador escriba cada código TOTP durante la corrida; cumple el requisito al pie de la letra, pero exige atención humana en las 5 corridas

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 10 — Evidencia de AUTONOMIA-03 y AUTONOMIA-06

La extensión pide comprobar estas reglas antes de cerrar cada unidad, pero los planes de U7 y U8
dependen de dobles, X01 o «cuando exista U12». Las demostraciones completas solo son posibles
cuando existe U12. ¿Cuándo debe exigirse la evidencia?

A) Por unidad, con lo que exista (dobles y X01), y la demostración completa en U12; dejarlo escrito como una decisión del proyecto (Recomendado)

B) Una unidad no cierra hasta tener la evidencia completa en kind; cumple la regla literal, pero U7 y U8 quedarían abiertas hasta U12

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 11 — Política de referencia de U5

BR-U5-13 calibra el modelo contra el umbral de baja confianza de la «política de referencia», pero
U5 no define sus valores. Sin ellos no se puede construir esa prueba. ¿De dónde salen?

A) Definir `cutoff` y `low_confidence_threshold` en la configuración de U5 como valores sintéticos, y cargarlos en U4 como la política de kind (Recomendado)

B) Que riesgo entregue los valores antes de construir U5

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 12 — Varias resoluciones de un congelamiento

`FreezeRecord.resolution` admite una sola resolución, pero `investigar` y luego `reactivar` son dos.
Si se toma la primera, BR-U9-08 no reinicia la ventana y el modelo podría volver a congelarse. ¿Cómo
se modela?

A) Cambiar a `resolutions`, una lista ordenada, y que BR-U9-08 use la última `reactivar` (Recomendado)

B) Mantener un solo campo con la resolución más reciente; es más simple, pero se pierde la historia en esa vista, aunque siga en el registro

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 13 — Consulta de explicación reenviada tarde

Una `explanation_view` que se reenvía después de 7 días recibe 422 por BR-U0-37, y BR-U8-19 no
contempla ese caso. La evidencia quedaría atascada y la decisión podría contarse sin consulta
previa en la North Star. ¿Qué debe pasar?

A) Marcarla como descartada, con alerta y métrica, y sin reintentos infinitos (Recomendado)

B) Permitir más de 7 días para `explanation_view`; conserva el dato, pero debilita la cota de BR-U0-37

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 14 — Outlier detection del borde

El borde saca un pod del balanceo tras 5 errores 5xx seguidos. Si una dependencia cae, el BFF
responde 503 `dependency_unavailable` aunque esté sano, y podrían expulsarse pods que no fallan.
Este efecto no se ha comprobado en ejecución. ¿Qué se hace?

A) Contar solo errores de conexión en `/api/console/**`, no los 5xx (Recomendado)

B) Dejarlo igual y medirlo en la prueba de carga de U12

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 15 — `AppProject` de Argo CD

Ningún documento define un `AppProject`, así que el alcance de Argo CD no está limitado.

A) Definir en U1 un `AppProject` por entorno, con repositorios, namespaces y tipos de recurso permitidos, y validarlo con `conftest` (Recomendado)

B) Usar el proyecto `default`; es más simple, pero Argo CD queda con alcance amplio

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 16 — US-603 desactualizada

US-603 pide `kubectl auth can-i` con impersonación y un POST desde el pod de scoring. U12 lo retiró
a propósito: K16 no da impersonación, y RT-5 usa el Job de U8 más X01.

A) Actualizar US-603 para que refleje RT-5 y X01 (Recomendado)

B) Restaurar la prueba original y dar impersonación a K16; amplía los permisos del operador de verificación

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 17 — Ajustes menores

Son puntos señalados por la revisión que todavía no confirmé en detalle. Al aplicarlos, primero
compruebo cada uno y descarto el que no sea real:

- K01 da `pods/log` sin `list pods`: agregar `list` sobre `pods` en `vectra-staging`.
- `rt5-demo` lleva identidad de `case-service`: asegurar que el Service de `case-service` no lo seleccione.
- K16 no cubre `vectra-mock`: agregarlo si U12 necesita leer ese namespace.
- 504 de explainability: usar el `code` `deadline_exceeded` de U0 para la cabecera vencida y documentar el de los demás casos.
- F32: alinear «grupo × banda × resultado» de U4 con `CountTable` (`favorable` y `total`).
- U0 §9.6: quitar «falta de una verificación» o agregar ese valor a `reason`.
- Timeouts del BFF iguales o menores que los de abajo: `get_dashboard` frente a `daily:query`, y `get_context_package` frente a `monitoring/freezes`.
- Values de staging de U6 con el predictor activo: añadirlos al plan de U6 (INF-U4-05).

A) Comprobar y aplicar todos los que sean reales (Recomendado)

B) Enviarme primero la lista comprobada, para decidir uno por uno

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

---

## Parte C — Cierre

## Pregunta 18 — Quinta revisión de coherencia

Cambiaron 46 documentos, y siguen sin revisar a fondo las cuotas de `vectra-edge`,
`vectra-identity` y `vectra-data`, los planes completos, las historias US-605 a US-611 y los buckets
de los histogramas, que no están declarados en ningún documento.

A) Revisión dirigida: lo cambiado el 2026-10-31 y lo que quedó sin revisar, después de aplicar estas respuestas (Recomendado)

B) Revisión completa de todas las unidades; encuentra más, pero cuesta bastante más

C) Ninguna por ahora

D) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 19 — Aprobaciones

Las aprobaciones de cada etapa son anteriores a estos cambios. ¿Cómo se validan antes de generar
código?

A) Una aprobación tuya sobre el conjunto de cambios, registrada en `audit.md`, y revisar cada plan contra su tabla de cambios al empezar esa unidad (Recomendado)

B) Volver a aprobar por unidad las etapas afectadas ahora; es lo más estricto, pero implica muchas aprobaciones

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 20 — Commit de los cambios

Los cambios están sin commit en la rama local `docs/audit-status-check`, y no se ha enviado nada al
remoto.

A) Commit ahora de las correcciones ya aplicadas y otro commit aparte con estas respuestas; deja más clara la historia (Recomendado)

B) Un solo commit al final, con todo junto

C) No hacer commit todavía; primero reviso el `git diff`

D) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A
