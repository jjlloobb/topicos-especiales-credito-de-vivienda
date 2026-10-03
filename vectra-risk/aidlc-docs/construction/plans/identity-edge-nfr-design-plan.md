# Plan de NFR Design — U2 `identity-edge`

**Alcance:** convertir NFR-U2-01..42 en patrones y componentes lógicos de Keycloak y del
gateway. El punto abierto principal es NFR-U2-21: cómo lograr el modo de fallo distinto
por ruta cuando Redis no responde.

**Ya decidido** (no se pregunta): el stack de `tech-stack-decisions.md`, la topología de
réplicas y HPA (NFR-U2-01..04), los límites y cabeceras (U2 FD), las severidades y
runbooks (U1) y RESILIENCY-14 = C.

**Categorías obligatorias:**

| Categoría | Preguntas |
|---|---|
| Resilience Patterns | Q1, Q4, Q5 |
| Scalability Patterns | **Sin preguntas nuevas**: el escalado por HPA y el dimensionamiento de Redis ya están en NFR-U2-01, 03 y 30 |
| Performance Patterns | Q4, Q5 |
| Security Patterns | Q1, Q2, Q3, Q5 |
| Logical Components | Q1, Q6 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Cómo se implementa el modo de fallo por ruta de NFR-U2-21 (Resilience / Security)
NFR-U2-21 exige: si Redis no responde, *fail-open* en consola e ingesta y *fail-closed* en
`/auth/**`. El filtro de rate limit de Envoy tiene un modo de fallo (`failure_mode_deny`),
pero no confirmé si la versión de Envoy Gateway que se pinnee lo expone por política. Hay
que verificarlo contra esa versión en el plan de tareas.

A) **Orden de alternativas, verificado en el plan de tareas:**
   1. si la `BackendTrafficPolicy` de la versión pinneada expone el modo de fallo del rate limit global, se usa una política para `/auth/**` con fail-closed y otra para el resto con fail-open;
   2. si no lo expone, una `EnvoyPatchPolicy` acotada **solo** a la ruta de `/auth/**`, que fija `failure_mode_deny: true` en su filtro, con una prueba que falla si un cambio de versión rompe el parche;
   3. si ninguna sirve, `/auth/**` va en un `Gateway` propio con su `EnvoyProxy` configurado en fail-closed.

   El resultado queda registrado en `audit.md` (recomendado: la opción más simple que la versión real permita, con una prueba que lo demuestra)

B) Ir directo a un `Gateway` separado para `/auth/**` (opción 3), sin probar las otras

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — De dónde salen las claves del rate limit (Security)

A) **Solo de datos verificados**:
   - `/api/console/**` y `/api/promotion/**`: el claim `sub` del JWT, después de validarlo;
   - `/api/intake/**`: el claim `azp` del JWT validado;
   - `/auth/**`: la IP de origen que fija Envoy desde el balanceador de confianza (NFR-U2-23).

   Nunca de cabeceras que manda el cliente. El filtro JWT copia los claims a cabeceras internas que se borran antes de llegar al backend (recomendado: un atacante no puede elegir su propia clave de límite)

B) De una cabecera `X-Client-Id` que mandan los clientes

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Rotación de las llaves de firma de Keycloak (Security)

A) **Rotación cada 90 días con solapamiento**:
   - se agrega una llave nueva (RS256 o ES256) con mayor prioridad, que pasa a firmar;
   - la anterior queda **pasiva** (publicada en JWKS, sin firmar) durante 24 h, más que la vida del token (5 min) y la cache de JWKS (10 min);
   - después se desactiva.

   Se hace por realm como código (PR + sync manual), con un runbook y la alerta `SigningKeyAgeHigh` a los 80 días (recomendado)

B) Sin rotación programada: solo ante un incidente

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Timeouts, reintentos y detección de backends caídos en el gateway (Resilience / Performance)

A) Por ruta:
   - **timeouts**: consola 15 s, ingesta 5 s, promoción 10 s, auth 10 s, Grafana 30 s;
   - **reintentos**: solo en métodos **idempotentes** (`GET`, `HEAD`), 1 reintento ante `connect-failure` o `503`, con presupuesto del 20 %. **Nunca** se reintentan `POST`, `PUT` ni `PATCH`, para no duplicar una decisión, una aprobación o una solicitud;
   - **outlier detection**: saca del balanceo por 30 s un pod con 5 errores 5xx consecutivos, hasta el 50 % de los pods.

   (Recomendado)

B) Reintentos automáticos en todos los métodos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — JWKS en el gateway (Resilience / Security)
U0 deja de validar cuando su cache de JWKS vence y Keycloak no responde (P-U0-06). El
filtro JWT de Envoy, en cambio, conserva la última JWKS válida.

A) El gateway trae la JWKS de Keycloak **dentro del clúster** (no a través de sí mismo), la refresca cada 5 min y conserva la última válida si Keycloak no responde. Esa diferencia con U0 es aceptable porque el gateway es la primera capa y **cada servicio vuelve a validar** con las reglas de U0. Una llave retirada (Q3) deja de aceptarse en el gateway en ≤ 5 min (recomendado)

B) El gateway también rechaza las requests autenticadas si no puede refrescar la JWKS en 10 min

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Páginas de login (Logical Components / Usability)

A) **Tema de Keycloak en español** (Q20 de requirements: español con textos externalizados), con un tema hijo del predeterminado (`keycloak.v2`): logo y colores del banco y textos en un archivo de mensajes. **Sin JavaScript propio**, para mantener una CSP estricta en `/auth/**`. Cumple WCAG 2.1 AA, el objetivo de la SPA (recomendado)

B) El tema predeterminado de Keycloak sin cambios

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar `construction/identity-edge/nfr-requirements/` (NFR-U2-01..42, stack)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/identity-edge/nfr-design/nfr-design-patterns.md`
- [x] 4. Generar `construction/identity-edge/nfr-design/logical-components.md` (diagrama validado)
- [x] 5. Verificar el cumplimiento de las extensiones
