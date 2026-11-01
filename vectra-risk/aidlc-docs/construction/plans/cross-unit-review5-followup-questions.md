# Preguntas de seguimiento — Quinta revisión de coherencia entre unidades

Resuelven lo que quedó abierto después de las correcciones del 2026-10-31. Escribe la letra de
tu elección después de cada `[Answer]:`; si eliges «Otro», describe tu respuesta ahí mismo.
Cuando termines, avísame y aplico las respuestas. Ninguna cambia nada hasta entonces.

Si quieres ir rápido, responde primero las marcadas con **Prioridad alta**.

---

## Parte A — Decisiones de diseño

## Pregunta 1 — Métricas de los SLO · Prioridad alta

U1 calcula los SLO y el burn rate con «métricas HTTP del middleware de U0», pero U0 solo define
cuatro métricas, ninguna HTTP, y ninguna unidad declara buckets de histograma. Sin eso no se pueden
calcular el burn rate ni alertas como `RecommendationLatencyHigh` (400 ms). ¿De dónde salen?

A) U0 define un histograma HTTP con buckets que incluyan los umbrales de los SLO, y cada servicio lo hereda del middleware; las métricas con otra escala, como los ciclos de U11, declaran sus propios buckets (Recomendado)

B) Usar las métricas de latencia del proxy de Linkerd; no agrega código, pero sus buckets no se ajustan a los umbrales y no separan por ruta de la aplicación

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 2 — Alerta `GatewayHighLatency`

La alerta mide un «sobrecosto» del gateway mayor de 5 ms, pero ninguna métrica en producción da ese
valor: NFR-U2-11 solo lo mide comparando con y sin gateway hacia un backend de eco. ¿Qué se hace?

A) Medir el sobrecosto solo en la prueba de NFR-U2-11, y que la alerta use la latencia que Envoy sí reporta frente a la del backend (Recomendado)

B) Quitar la alerta y dejar solo la prueba

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 3 — Tamaño del pool `data` · Prioridad alta

El pool tiene al menos 2 nodos por zona de 4 vCPU / 16 GiB: 16 vCPU en total. Debe alojar 16 pods
(12 de PostgreSQL y 4 de MinIO), es decir, 1 vCPU por pod, y nadie declara sus recursos ni la cuota
de `vectra-data`. Con una zona caída la cuenta es más ajustada. ¿Cómo se resuelve?

A) Subir los nodos a 8 vCPU / 32 GiB, declarar recursos por cluster y por MinIO, y ajustar con la prueba de carga de U12 (Recomendado)

B) Mantener el tamaño de nodo y pasar a 3 nodos por zona; da más holgura ante una zona caída, pero son más nodos

C) Mantener el pool y solo declarar recursos; hay riesgo de contención en la zona que sobrevive

D) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 4 — MinIO con una zona caída

Hay 4 pods de MinIO, 2 por zona. Según cómo funciona MinIO, con 2 de 4 pods se puede leer pero se
pierde el quórum de escritura. Esto no está en los documentos y no se ha comprobado en ejecución.
Afectaría a logs (Loki), trazas (Tempo) y al model-store. ¿Qué se hace?

A) Aceptarlo para el MVP: documentar que escribir queda detenido durante la caída, agregar una alerta y probarlo en el simulacro de zona (Recomendado)

B) Distribuir MinIO en 3 zonas; exige que el banco tenga una tercera zona

C) Usar el S3 del banco para logs y trazas; agrega egress y contradice INF-U1-03

D) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 5 — Sentinel de Valkey sin mayoría

Hay 1 Sentinel en la zona A y 2 en la B. Si cae B y la primaria estaba ahí, queda 1 de 3, no hay
promoción y `/auth/**` responde 503, aunque el documento dice que Sentinel promueve la réplica.

A) Mantener 1 + 2, preferir la primaria en la zona de 1 Sentinel y documentar el 503 que queda posible hasta que vuelva la zona (Recomendado si el banco no tiene tercera zona)

B) Poner el tercer Sentinel en una tercera zona; resuelve el problema, pero exige esa zona

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 6 — Scrape del kubelet

`PostgresVolumeUsageHigh` usa `kubelet_volume_stats_*`, pero el inventario no tiene ese scrape ni
K02 da `nodes/metrics`. La regla compara con 6 volúmenes y quedaría disparada en los cuatro clusters.

A) Agregar el flujo de Prometheus a los kubelets y `nodes/metrics` a K02; amplía un permiso, pero es solo de lectura (Recomendado)

B) Usar otra fuente, como las métricas de disco de CloudNativePG, y reescribir la regla; hay que comprobar que da lo mismo

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 7 — Tráfico interno de Loki y Tempo

Loki corre en modo simple escalable y Tempo en distribuido mínimo. Sus componentes se hablan entre
sí, y con deny-all, sin flujos, no formarían el anillo. Los logs se conservan 90 días por requisito.

A) Agregar los flujos internos de Loki y Tempo al inventario y conservar los modos (Recomendado)

B) Pasar Tempo a modo monolítico, con menos flujos, y agregar solo los de Loki; Tempo pierde redundancia, pero sus trazas solo duran 7 días

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 8 — Prueba de carga de US-609 · Prioridad alta

La carga tiene dos problemas: el script de U7 no tiene ruta por el gateway, y un token fijo caduca a
los 5 de los 30 minutos.

A) Generar toda la carga por el gateway, con ingesta por el cliente del simulador y consola con usuarios reales, renovando tokens; el script de U7 queda como prueba de U7 fuera de `LOAD` (Recomendado)

B) Correr k6 dentro del clúster contra scoring; mide scoring directo, pero agrega una identidad y un flujo solo de prueba

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 9 — Readiness de governance · Prioridad alta

NFR-U4-03 y US-610 dicen que la readiness depende de `governance-db`. El plan de U4 dice que solo de
la copia en memoria, y que `serving-config` sigue funcionando con la base pausada. Si la readiness
sigue a la base, una caída de `governance-db` deja a scoring sin `serving-config` y todo pasa a
fail-closed.

A) Readiness con la copia en memoria; con la base caída siguen las lecturas de `serving-config` y las escrituras responden 503; actualizar NFR-U4-03 y US-610 y agregar esa prueba (Recomendado)

B) Readiness con la base, como dice US-610; es más simple, pero una caída de esa base detiene las recomendaciones

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 10 — Simulacros de US-608 y US-610 · Prioridad alta

El restore del sitio, el `restore-drill` manual y las pruebas de readiness quedan «pendientes hasta
que existan U3, U7 y U8», y ninguna de esas unidades los retoma por completo. La decisión de proyecto
RESILIENCY-14 ya difiere a Operations la ejecución de las pruebas de resiliencia, pero estas dos
historias las piden como evidencia.

A) Agregar a U12 una sección de resiliencia en kind con esos simulacros, incluidas `governance-db` y `registry-db`; alarga la verificación, pero las historias pueden pasar (Recomendado)

B) Diferirlos formalmente a Operations; U12 informa esas historias como `no ejecutado` hasta entonces

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 11 — Réplica síncrona en otra zona

US-605 exige que PostgreSQL declare una réplica síncrona en otra zona. El plan de U1 solo pide
reparto «preferido» por zona, así que la síncrona podría quedar en la misma zona y la prueba pasaría.

A) Exigirlo con `syncReplicaElectionConstraint` por zona y probarlo; hay que comprobar que escribir se detiene con una zona caída como ya prevé NFR-U1-03 (Recomendado)

B) Dejarlo como preferencia y cambiar US-605; pierde la garantía de RPO 0 ante el fallo de una zona

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 12 — `kubectl diff` en CI

NFR-U1-42 pide adjuntar `kubectl diff` contra kind en cada PR, pero ningún workflow tiene acceso a un
clúster. El entorno kind ya contempla clústeres efímeros en CI.

A) Levantar kind efímero en el workflow para ese diff, y agregar la prueba de que un Dockerfile con `latest` hace fallar el CI (US-606) (Recomendado)

B) Que el operador adjunte el diff al PR; es más simple, pero no se comprueba automáticamente

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 13 — Prueba de extremo a extremo de U2

El Paso 16 de U2 prueba el step-up con el diálogo de la SPA, pero U10 se construye después y U2 no
tiene un doble de la SPA, así que ese paso no puede cerrar.

A) Dejar en U2 la prueba del flujo OIDC sin SPA y pasar a U10 el diálogo de step-up, donde ya hay suite de Playwright (Recomendado)

B) Crear en U2 una SPA mínima de prueba; se mantiene en U2, pero es código de prueba adicional

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 14 — Alcance de las políticas de réplicas

Grafana y Pushgateway corren con 1 réplica. `require-spread-and-pdb` y NFR-U1-04 hablan de los
«Deployments de Vectra», pero nadie define qué namespaces cubren.

A) Fijar el alcance a los namespaces de servicios y dejar fuera `vectra-observability`, con una prueba de Kyverno (Recomendado)

B) Mantener el alcance amplio y agregar una exención por Deployment

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 15 — Usuarios `cumplimiento-*` en staging (P9)

Elegiste que no existieran en staging, pero el Infrastructure Design de U10 (Q6) los exige ahí. Hoy
siguen en staging, y la herramienta de U12 no lee sus semillas fuera de kind.

A) Dejarlo así: la reactivación automatizada solo es posible en kind, y U10 conserva su suite (Recomendado)

B) Quitarlos de staging y reabrir esa decisión de U10; la suite de U10 no cubriría ese rol en staging

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

---

## Parte B — Correcciones sin decisión de diseño

## Pregunta 16 — Lote de correcciones

Todos estos puntos salen de la quinta revisión. Al aplicarlos compruebo cada uno y descarto el que
no sea real; las cifras de cuotas se recalculan, porque las del revisor no están confirmadas:

- Declarar y sumar en U1 los aportes a las cuotas de `vectra-edge` y `vectra-identity`, fijando el `maxSurge` de U2.
- Resumen al solicitante: que la regla de objeto del BFF exija decisión `desfavorable`, en `component-methods.md`, el plan y PBT-U10-02, y aclarar quién pone `recommendation_entry_id`.
- Permitir `prepare` en staging, porque sin ella el humo de U12 no arranca.
- Valkey: agregar los usuarios de replicación y de Sentinel a las ACL, y los PDB si faltan.
- Exportador de llaves: recursos, flujo y scrape; recursos del exportador de Valkey; credencial de administración de `keycloak-config-cli` y `realm-drift`.
- Bindings K que faltan para Prometheus Operator y el instance manager de CloudNativePG, si de verdad usan la API.
- Corregir `grep -q "NFR-U1-11"` del plan de U1, que no puede pasar, y asignar quién recalcula los HPA y `max_connections`.
- Agregar las pruebas de 413 en U2 y de que el CRO no llama a `record_explanation_view` en U10.
- Unificar las réplicas de Keycloak («2 por zona» frente a «2 repartidas»).
- Comprobar que `containerPort`, NetworkPolicy y `Server` coinciden en F01, F19, F22 y F30.
- Completar las tablas «Depende de» y «Lo consumen» de U1, U3, U4, U5, U7 y U9.

A) Comprobar y aplicar todos los que sean reales (Recomendado)

B) Enviarme primero la lista comprobada, para decidir uno por uno

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

---

## Parte C — Cierre

## Pregunta 17 — Restricción de no escribir código · Prioridad alta

Cinco revisiones siguen encontrando problemas, y varios solo se confirman ejecutando: red generada,
políticas de Kyverno, failover. La instrucción vigente es no escribir código.

A) Después de aplicar estas respuestas, levantarla solo para U0 y U1, con su Code Generation Part 2, y comprobar la plataforma en kind (Recomendado)

B) Mantener la restricción y terminar con los documentos; sigue siendo solo diseño, sin evidencia en ejecución

C) Mantener la restricción y hacer otra revisión completa de los planes de U0, U3, U4, U5, U6, U9 y U11, que no se han revisado a fondo

D) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 18 — Aprobación pendiente (P19)

Elegiste una aprobación sobre el conjunto de cambios, pero la dejé pendiente por los hallazgos
abiertos.

A) Pedírtela después de aplicar estas respuestas, con un resumen de todo lo cambiado desde el 2026-10-31 (Recomendado)

B) Registrarla ahora y tratar lo abierto como trabajo aparte

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A

## Pregunta 19 — Commit y rama

La rama local `docs/audit-status-check` tiene todo el trabajo, sin enviar al remoto.

A) Commit de estas respuestas en la misma rama; la decisión de integrar en `main` la tomamos después de la aprobación (Recomendado)

B) Commit en la rama y abrir ya un PR hacia `main`; publica estos cambios en el remoto

C) Otro (describe después de la etiqueta [Answer]:)

[Answer]: A
