# Plan de Infrastructure Design — U10 `console`

**Alcance:** llevar los componentes lógicos de U10 (`logical-components.md`) a recursos de
Kubernetes en kind, staging y producción, sobre la plataforma de U1 y el borde de U2.

**Ya decidido** (no se pregunta):
- **Namespaces** (`component-dependency.md` §1): `console-bff` en `vectra-app` y `console-spa` en `vectra-edge`, con el api-gateway.
- **Flujos existentes**: F02 (gateway → SPA), F03 (gateway → BFF), F10–F14 (BFF → destinos) y F50 (BFF → JWKS de Keycloak).
- **Criticidad y PriorityClass**: BFF High con `vectra-high`, HPA de 2 a 6 por CPU al 70 %, PDB y spread por zona; SPA Medium con `vectra-normal`, 2 réplicas fijas con `vectra.io/hpa-exempt`, PDB y spread (NFR-U10-10..22).
- **Despliegue**: GitOps con Argo CD y sync manual (AUTONOMIA-01), en la wave 5 con los servicios de Vectra (P-U1-12).
- **Imágenes**: firmadas, por digest, con SBOM (U1); `runAsNonRoot` y `readOnlyRootFilesystem`.

**Categorías obligatorias:**

| Categoría | Preguntas |
|---|---|
| Deployment Environment | Q6 |
| Compute Infrastructure | Q1 |
| Storage Infrastructure | Sin preguntas: U10 no tiene datos propios. La tabla `integrity_checks` es de U3 (P-U10-05) y la cubre su Infrastructure Design (cambio registrado aquí) |
| Messaging Infrastructure | Sin preguntas: U10 no usa colas ni eventos; todo es HTTP síncrono, y la verificación de integridad es asíncrona dentro de U3 |
| Networking Infrastructure | Q3 |
| Monitoring Infrastructure | Q5 |
| Shared Infrastructure | Q2, Q4 (imagen previa de la SPA y configuración) |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Recursos y aporte a las cuotas (Compute; NFR-U10-10, 12; NFR-U1-13)

A)
   | Componente | Requests | Limits | Réplicas | PriorityClass |
   |---|---|---|---|---|
   | `console-bff` | 250m / 256 MiB | 1 CPU / 512 MiB | HPA de 2 a 6 | `vectra-high` |
   | `console-spa` (`nginx-unprivileged`) | 50m / 32 MiB | 200m / 64 MiB | 2 fijas | `vectra-normal` |

   - Aporte con el 30 % de margen, **con** el sidecar de Linkerd (supuesto de INF-U9-01: 100m / 20 MiB y 500m / 128 MiB por pod, hasta que U1 fije `proxy.resources`):
     - `vectra-app` (BFF, 6 réplicas): requests ≈ 2,73 CPU y 2,15 GiB; limits ≈ 11,7 CPU y 4,9 GiB;
     - `vectra-edge` (SPA, 2 réplicas): requests ≈ 0,39 CPU y 0,13 GiB; limits ≈ 1,82 CPU y 0,5 GiB;
   - la prueba de carga de NFR-U10-01 (P-U10-11) confirma o ajusta los valores.

   (Recomendado)

B) Los mismos recursos para el BFF que para el servicio HTTP de bias (100m / 128 MiB)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Recursos de la versión anterior en la imagen de la SPA (Shared; P-U10-06)

A) **Etapa de build que copia de la imagen previa por digest**:
   - el Dockerfile tiene una etapa `FROM <registro>/console-spa@<digest previo> AS previous`, y la etapa final copia `assets/` de `previous` y del build nuevo;
   - el digest previo vive en `console-spa/previous-image.txt`, que el workflow de release actualiza con el digest publicado en el release anterior (por PR, no a mano);
   - solo se conserva **una** versión anterior: los recursos de `previous` que a su vez venían de la versión N−2 se descartan con la lista de `manifest.json` de N−1;
   - en el primer release, sin imagen previa, la etapa se omite.

   (Recomendado)

B) Un bucket de MinIO o S3 compartido con todos los recursos históricos, servido por el gateway

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Malla y políticas de red (Networking; NFR-U10-46)

A) **Las dos piezas en la malla de Linkerd**:
   - `console-spa` en la malla (`vectra-edge` ya está mallado por el gateway), con un `Server` en el puerto 8080 y una `AuthorizationPolicy` que solo admite la identidad del data plane del gateway (F02);
   - `console-bff`: `Server` en 8080 solo para el gateway (F03) y en 8081 solo para Prometheus (F60); el BFF solo sale hacia F10–F14 y F50;
   - las `NetworkPolicy` y `AuthorizationPolicy` las genera `platform/network/generate.py` de U1 desde `flows.yaml`, como en las demás unidades, con casos bloqueados: SPA → cualquier servicio de `vectra-app` (bloqueado) y BFF → `vectra-data` (bloqueado; el BFF no tiene base);
   - la ruta `/grafana/**` del gateway sigue en U2 (perfil `grafana`): el iframe de BR-U10-16 no pasa por el BFF.

   (Recomendado)

B) La SPA fuera de la malla (contenido estático), protegida solo por `NetworkPolicy`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Configuración de la SPA por entorno (Shared; domain-entities §4 de U10)

A) **`config.json` desde un ConfigMap**:
   - el chart genera `config.json` (`oidc.authority`, `client_id`, los dos `redirect_uri`, refrescos, `stepup.timeout_seconds`, el `uid` de `bias.json`) desde los values de cada entorno y lo monta en nginx como archivo de solo lectura, con `Cache-Control: no-store`;
   - `version.json` va dentro de la imagen (lo genera el build), no en el ConfigMap;
   - la imagen es la **misma** en los tres entornos; solo cambia el ConfigMap;
   - `conftest`: `config.json` no tiene secretos (es un cliente público) y los `redirect_uri` coinciden con los del realm de U2 del mismo entorno;
   - nginx con `readOnlyRootFilesystem` usa `emptyDir` para `/tmp` y su caché temporal.

   (Recomendado)

B) Una imagen por entorno con la configuración compilada

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Dashboard y runbooks (Monitoring; P-U10-10, 11)

A)
   - **Dashboard `console.json`** como código (ConfigMap de dashboards de U1):
     - por ruta del BFF: tasa, errores y latencia p50/p95/p99;
     - por destino: el sobrecosto de NFR-U10-01 y el estado de cada circuito;
     - errores del navegador por `error_code`;
     - presupuesto de errores del SLO de 30 días;
     - réplicas del HPA.
   - **Runbooks** de las cinco alertas de P-U10-10, con el test de runbooks de U1. El de `ConsoleClientErrorsSpike` explica cómo distinguir un `chunk_load_failed` de un despliegue (P-U10-06) de uno real.
   - **Evidencias de rendimiento**: el reporte de k6 y el de Lighthouse CI se adjuntan al PR; `size-limit` corre en cada PR.

   (Recomendado)

B) Solo las alertas, sin dashboard propio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Entornos y pruebas de extremo a extremo (Deployment Environment; NFR-U10-63)

A)
   - **kind**: el mismo chart con 2 réplicas fijas del BFF (sin HPA), el realm `kind` de U2 con un usuario por rol y TOTP de prueba, y los servicios reales de U3, U4, U7, U8 y U9. Playwright y k6 corren contra kind (operador).
   - **staging**: igual que producción, con el realm `staging` y datos sintéticos de U12.
   - **producción**: HPA de 2 a 6, el realm `prod` (sin usuarios de prueba; `realm-lint` lo verifica).
   - **CI** (sin clúster): Playwright contra la SPA servida por Vite y un BFF con dobles de los destinos y un emisor de JWT de prueba.

   (Recomendado)

B) Además, un entorno efímero por PR

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Plan de trabajo

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `infrastructure-design.md` (INF-U10-xx): recursos y cuotas, imagen de la SPA, red, configuración, observabilidad, entornos
- [x] `deployment-architecture.md`: topología, ciclo de vida, inventario de recursos
- [x] Cambios a otras unidades (U1 cuotas y `flows.yaml`; U2 realm `kind`; U3 pool de la verificación asíncrona) registrados
- [x] Tabla de cumplimiento de extensiones
- [x] Validar el contenido (Mermaid y texto alternativo) antes de crear los archivos
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
