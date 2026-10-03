# Mapa historias → unidades — Vectra Risk

Cada historia tiene **una unidad dueña** y puede tener **unidades contribuyentes**.
- La **dueña** planifica las tareas que cumplen los criterios de aceptación y la línea "Verificación" de la historia.
- Las **contribuyentes** planifican la parte que les toca, que se referencia en el plan de la dueña.
- La **verificación e2e** es la unidad donde vive la prueba que cruza unidades. Suele ser U12.

## 1. Asignación de las 49 historias

| Historia | Título corto | Prio | Dueña | Contribuyentes | Verificación e2e |
|---|---|---|---|---|---|
| US-101 | Ingesta desde el simulador | M | U8 | U2 (ruta F04), U12 (simulador) | U12 |
| US-102 | Alta manual | M | U8 | U10 (formulario) | U10 |
| US-103 | Recomendación con política | M | U7 | U4 (política), U0 (tipos) | U7 |
| US-104 | Explicación no técnica | M | U7 | U10 (vista) | U7 |
| US-105 | Validación de factualidad | M | U7 | — | U7 |
| US-106 | Marca de baja confianza (RT-4) | M | U7 | U5 (casos RT-4), U10 (marca visible) | U12 (RT-4) |
| US-107 | Bandeja con estados | M | U8 | U10 (vista) | U10 |
| US-108 | Decisión firmada | M | U8 | U3 (append), U10 (vista) | U8 |
| US-109 | Texto libre como dato (RT-1) | M | U7 | U8 (almacenamiento escapado), U10 (escape en UI), U5 (casos RT-1) | U12 (RT-1) |
| US-110 | Resumen al solicitante | S | U7 | U10 (acción), U3 (lectura) | U7 |
| US-111 | Fail-closed por desincronía (RT-3) 🎯 | M | U7 | U0 (invariante de tipo), U6 (misma revisión), U5 (artefacto desincronizado) | U12 (RT-3, demo 7.3) |
| US-112 | Reintento y escalamiento | M | U8 | U1 (Alertmanager), U10 (vista del CRO) | U8 |
| US-113 | Sin persistencia no hay recomendación | M | U7 | U3 (confirmación síncrona), U1 (réplica F45) | U7 |
| US-201 | Registrar versión de modelo | M | U4 | U5 (artefacto), U10 (vista) | U4 |
| US-202 | Validación en staging | M | U4 | U9 (librería de disparidad), U5 (dataset), U6 (staging) | U4 |
| US-203 | Aprobación del CRO (modelo) | M | U4 | U10 (vista), U2 (MFA) | U4 |
| US-204 | Promoción atómica vía PR | M | U4 | U6 (plantilla), U1 (Argo CD manual) | U4 |
| US-205 | Proponer política | M | U4 | U10 (vista) | U4 |
| US-206 | Aprobar política | M | U4 | U10 (vista), U7 (lectura de la nueva versión) | U4 |
| US-207 | Reglas VIS y tope de usura | C→ | U7 | U4 (parámetros con vigencia) | U7 |
| US-208 | Rollback aprobado | M | U4 | U1 (Argo CD), U6 | U4 |
| US-301 | Disparidad por bandas | M | U9 | U3 (lectura), U8 (etiquetas de monitoreo en la ingesta) | U9 |
| US-302 | Disparidad de decisiones humanas | M | U9 | U3 | U9 |
| US-303 | Congelamiento automático (RT-2) 🎯 | M | U9 | U4 (transición), U5 (modelo proxy), U7 (rechazo por modelo congelado) | U12 (RT-2, demo 7.4) |
| US-304 | Paquete de contexto 🎯 | M | U9 | U10 (vista), U1 (Alertmanager) | U12 (demo 7.4) |
| US-305 | Resolución humana del congelado 🎯 | M | U4 | U10 (vista), U2 (MFA) | U12 (demo 7.4) |
| US-306 | Fuente nueva con pre/post | S | U9 | U4 (flujo de aprobación), U10 (vista) | U9 |
| US-307 | Dashboard que no certifica | M | U9 | U10 (vista y lint de frases) | U10 |
| US-308 | Alerta de monitoreo detenido | M | U9 | U1 (Alertmanager) | U9 |
| US-401 | Registro append-only encadenado | M | U3 | U1 (rol de BD) | U3 |
| US-402 | Verificador de integridad | M | U3 | U10 (acción) | U3 |
| US-403 | Expediente para el supervisor | M | U3 | U10 (vista) | U3 |
| US-404 | Eventos de gobierno registrados | M | U3 | U4, U9 (emisores) | U3 |
| US-501 | Consulta de la explicación instrumentada | S | U8 | U10 (evento al abrir) | U8 |
| US-502 | Justificación estructurada | S | U8 | U10 (formulario) | U8 |
| US-503 | North Star 🎯 | S | U11 | U3 | U12 (demo dashboard) |
| US-504 | Métrica de ruido con alerta 🎯 | S | U11 | U1 (Alertmanager) | U12 (demo dashboard) |
| US-505 | Métricas operativas y de producto 🎯 | M/S | U11 | U8, U7 (métricas operativas) | U12 (demo dashboard) |
| US-601 | Autenticación con roles y MFA | M | U2 | U0 (middleware) | U2 |
| US-602 | Autorización en servidor | M | U10 | U0 (middleware), todos los servicios (revalidación) | U10 |
| US-603 | Sin escritura de estado de crédito (RT-5) 🎯 | M | U8 | U1 (NetworkPolicy), U7 (sin cliente hacia el core) | U12 (RT-5, X01) |
| US-604 | Egress denegado y logs sin PII | M | U1 | U0 (logger), U7, U9 | U12 (X02) |
| US-605 | Helm self-hosted multi-zona | M | U1 | Todas (charts) | U1 |
| US-606 | CI con evidencia | M | U1 | Todas (usan los workflows) | U1 |
| US-607 | Argo CD con sync manual | S | U1 | — | U1 |
| US-608 | Backups y restore probado | M | U1 | U3 (`verify_chain` tras el restore) | U1 |
| US-609 | Autoscaling con carga simulada | M | U12 | U6 (KServe), U7/U8/U10 (HPA en sus charts) | U12 |
| US-610 | Observabilidad y runbooks | M | U1 | Todas (alertas y runbooks propios) | U1 |
| US-611 | Endurecimiento del gateway y la SPA | M | U2 | U10 (errores genéricos del BFF) | U2 |

## 2. Resumen por unidad

| Unidad | Historias dueñas | # |
|---|---|---|
| U0 contracts | — (habilitadora) | 0 |
| U1 platform-foundation | US-604, 605, 606, 607, 608, 610 | 6 |
| U2 identity-edge | US-601, 611 | 2 |
| U3 decision-registry | US-401, 402, 403, 404 | 4 |
| U4 governance | US-201, 202, 203, 204, 205, 206, 208, 305 | 8 |
| U5 reference-model | — (habilitadora) | 0 |
| U6 model-serving | — (habilitadora) | 0 |
| U7 scoring-explainability | US-103, 104, 105, 106, 109, 110, 111, 113, 207 | 9 |
| U8 case-management | US-101, 102, 107, 108, 112, 501, 502, 603 | 8 |
| U9 bias-monitoring | US-301, 302, 303, 304, 306, 307, 308 | 7 |
| U10 console | US-602 | 1 |
| U11 product-metrics | US-503, 504, 505 | 3 |
| U12 system-verification | US-609 | 1 |
| **Total** | | **49** |

**Unidades habilitadoras sin historias propias.** U0, U5 y U6 no tienen historias
dueñas, pero son contribuyentes necesarias de historias concretas: US-111, 602, 604 y
611 (U0); US-106, 109, 111, 201, 202 y 303 (U5); US-111, 204 y 609 (U6). Sus planes de
tareas se trazan a esas historias.

**U10 es dueña de una sola historia**, pero contribuye a otras 22 (UI, errores genéricos del BFF y acciones de consola) como
contribuyente. Su plan de tareas se traza a todas ellas.

## 3. Asignación de la verificación de flujos prohibidos y red-teaming

| Escenario | Unidad que lo verifica | Unidades cuyo diseño lo hace cumplir |
|---|---|---|
| RT-1 Inyección indirecta | U12 | U7, U8, U10 |
| RT-2 Variables proxy → congelamiento | U12 | U9, U4, U5 |
| RT-3 Desincronía forzada | U12 | U7, U6, U0 |
| RT-4 Adversarial examples | U12 | U7, U5 |
| RT-5 Escritura hacia estado de crédito | U12 | U8, U1 |
| X01 Solo GET al core, solo desde case | U12 | U8, U1 |
| X02 Sin egress desde scoring, explain, bias | U12 | U1, U7, U9 |
| X03 Solo cumplimiento saca de `congelado` | U12 | U4 |
| X04 bias → governance solo `freeze` | U12 | U4, U2 |
| X05 Sin acceso a bases ajenas | U12 | U1, U3, U4, U8 |
| X06 `registry_app` sin UPDATE/DELETE | U12 (y U3 unitaria) | U3 |
| X07 Sin API de K8s salvo K01 | U12 | U1, U4 |
| X08 staging ↔ prod aislados | U12 | U1, U6 |
| X09 Único ingress | U12 | U1, U2 |
| X10 Consola admin de Keycloak no expuesta | U12 (y U2 unitaria) | U2 |

## 4. Validación

- **49 de 49** historias tienen una unidad dueña (§2).
- **18 de 18** componentes de Application Design tienen unidad:
  - C01 → U2, C02 → U10, C03 → U10, C04 → U8, C05 → U7, C06 → U7;
  - C07 → U6, C08 → U1, C09 → U4, C10 → U4, C11 → U9, C12 → U3;
  - C13 → U11, C14 → U12, C15 → U8, C16 → U2, C17 → U1, C18 → U1 + U4 (`promotion-tool`).
- **RT-1..5 y X01–X10**: todos tienen una unidad que los verifica (§3).
- **Dependencias**: acíclicas en construcción (ver `unit-of-work-dependency.md` §1).
- **Demos 🎯 de la Sesión 16**: 8 historias (US-111, 303, 304, 305, 503, 504, 505, 603); todas terminan su verificación en U12.
