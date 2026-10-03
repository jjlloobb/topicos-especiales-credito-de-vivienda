# Plan de NFR Requirements — U2 `identity-edge`

**Alcance:** requisitos no funcionales y stack de Keycloak (realm `vectra`) y de Envoy
Gateway (rutas F01–F09), sobre el Functional Design aprobado (BR-U2-01..17).

**Ya decidido** (no se pregunta):
- Keycloak como IdP y Envoy Gateway como gateway (INCEPTION);
- `keycloak-db` en CloudNativePG y ≥ 2 réplicas con spread por zona y PDB (U1);
- realm aplicado con `keycloak-config-cli` como hook de sync manual (U2 FD Q10);
- límites, cabeceras, MFA, sesiones y eventos (U2 FD);
- eventos y access log a Loki con 90 días (U1); PBT con Hypothesis para Python (U0).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Despliegue de Keycloak (Tech Stack)

A) **Chart `keycloakx` (codecentric)** con la imagen oficial de Keycloak 26.x (Quarkus), pinneada por digest, en modo producción (`start --optimized`, imagen precompilada con los proveedores necesarios). Sin operador: es un Deployment más del patrón Helm + Argo CD y no agrega bindings K0x (recomendado)

B) **Keycloak Operator** oficial (CRD `Keycloak`), con su propio binding de RBAC

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Alta disponibilidad y sesiones de Keycloak (Availability)

A) **2 réplicas repartidas por zona** con clúster de Infinispan embebido (descubrimiento por `jdbc-ping` sobre `keycloak-db`) y **sesiones de usuario persistentes en la base**: perder un pod o una zona no cierra las sesiones. Un HPA de 2 a 4 réplicas por CPU (recomendado)

B) 3 réplicas fijas, con sesiones solo en memoria (owners = 2)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Objetivos de rendimiento de identidad (Performance)
Usuarios internos: del orden de decenas a pocos cientos (analistas, ingenieros, CRO, cumplimiento).

A) Con 200 usuarios concurrentes y 8 identidades de servicio renovando tokens cada 5 min:
   - página de login con **p95 ≤ 500 ms**;
   - endpoint de token **p95 ≤ 200 ms** (incluida la emisión por client credentials);
   - JWKS **p95 ≤ 50 ms**.

   Se mide con una prueba de carga en kind que ejecuta el operador (recomendado)

B) Sin objetivos propios: solo el SLO de la ruta de recomendación (U1)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Disponibilidad y sobrecosto del gateway (Availability / Performance)

A) Envoy (data plane) con **≥ 2 réplicas repartidas por zona**, PDB y un HPA de 2 a 6 por CPU. El controlador de Envoy Gateway con 2 réplicas en elección de líder. Sobrecosto del gateway (TLS + JWT + rate limit + cabeceras) de **p95 ≤ 5 ms** por request. Si el controlador cae, el data plane sigue sirviendo con la última configuración (recomendado)

B) 1 réplica del data plane, sin HPA

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Implementación del rate limiting (Tech Stack / Scalability)
Los límites de BR-U2-08 son por usuario, por cliente y por IP. Con varias réplicas de Envoy,
un límite **local** se multiplica por el número de réplicas. Un límite **global** exige el
servicio de rate limit de Envoy y Redis.

A) **Rate limiting global**: el servicio de rate limit de Envoy con **Redis** en `vectra-edge` (Redis con réplica y Sentinel, repartido por zona, sin persistencia porque los contadores son efímeros). Los límites son exactos sin importar el número de réplicas. Si Redis cae, se aplica *fail-open* **solo** en las rutas de consola e ingesta y *fail-closed* en `/auth/**` (login y token), además del bloqueo de Keycloak (recomendado: el límite por IP de login es un control de seguridad y no debe depender del número de réplicas)

B) **Rate limiting local** por réplica, con los límites divididos por el mínimo de réplicas; es aproximado y no tiene componentes nuevos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — TLS en el borde (Security, SECURITY-01)

A) **Certificado emitido por la CA del banco** para el hostname público de Vectra, gestionado por cert-manager con un `ClusterIssuer` del banco (ACME interno o CA) en staging y prod, y con la CA interna de U1 en kind. **TLS 1.2 como mínimo, 1.3 preferido**; suites del perfil *intermediate* de Mozilla; OCSP stapling si la CA lo soporta; alerta de vencimiento (P-U1-03) (recomendado)

B) La CA interna de U1 en todos los entornos, con la CA distribuida a los navegadores del banco

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — IP de origen real (Security / Networking)
El límite por IP de `/auth/**` y los eventos de Keycloak necesitan la IP real del
navegador, no la del balanceador.

A) Service del gateway con **`externalTrafficPolicy: Local`** cuando el balanceador del banco lo permita; si no, **PROXY protocol v2** desde el balanceador. Envoy confía en `X-Forwarded-For` solo desde el balanceador (1 salto) y Keycloak usa la cabecera que fija Envoy (`proxy-headers=xforwarded`). Una prueba verifica que una cabecera `X-Forwarded-For` falsa del cliente no cambia la IP registrada (recomendado)

B) Confiar en `X-Forwarded-For` tal como llega

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Política de contraseñas de usuarios locales (Security, SECURITY-12)
Aplica a los usuarios sintéticos de kind y staging y a `break-glass`. En producción, las
contraseñas son del LDAP del banco.

A) **Longitud ≥ 14**, distinta del nombre de usuario y del email, historial de 5, *hash* **Argon2** (el predeterminado de Keycloak 26), sin vencimiento periódico (NIST SP 800-63B). La de `break-glass` se rota después de cada uso (recomendado)

B) Longitud ≥ 8 con complejidad (mayúsculas, números y símbolos) y vencimiento de 90 días

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 — Pruebas de U2 (Tech Stack / Testing, PBT-09)

A) **Python 3.12 + pytest + Hypothesis** para `realm-lint`, `route-gen` y los modelos (mismo stack que U0, PBT-09). Las pruebas de extremo a extremo de login, MFA (TOTP con `pyotp`), bloqueo y cabeceras usan **Playwright** + `httpx`, en kind, ejecutadas por el operador (U1, Paso 19). La validación estática de los manifiestos del gateway usa `kubeconform` con los CRDs de Gateway API (recomendado)

B) Solo pruebas manuales siguiendo un checklist

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el Functional Design de U2 y los NFR heredados (NFR-SEC-01/02/04/08/09/11/12/14, NFR-U1)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/identity-edge/nfr-requirements/nfr-requirements.md` (disponibilidad, rendimiento, seguridad, escalabilidad, pruebas)
- [x] 4. Generar `construction/identity-edge/nfr-requirements/tech-stack-decisions.md` (incluye PBT-09)
- [x] 5. Verificar el cumplimiento de las extensiones
