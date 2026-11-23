# Riesgos y cómo se mitigaron

Tabla completa de la sección 8 del `README.md` raíz. Estado al 21 de noviembre de 2026; la fila de Grafana es del 22. Las rutas son relativas a la raíz del repositorio.

| Riesgo | Mitigación | Estado al 21 nov 2026 |
|---|---|---|
| El agente actúa sin control | AUTONOMIA-01, Argo CD sin auto-sync, Kyverno prohíbe el auto-sync, reglas `deny`, RBAC de solo lectura | Implementado y con evidencia `can-i`. Queda un hueco: `deny` se esquiva con una variable, y el orquestador operó kind con aprobación |
| La explicación se desincroniza del score | Fail-closed: sin explicación no hay recomendación | Implementado (U7, U8). Medido en D1 |
| Un modelo sesgado sigue decidiendo | `CronJob` de sesgo que congela el modelo | Implementado (U9, U4). Medido en D2: congelado en 520,7 s |
| El sistema escribe en el core del banco | La malla lo deniega y una alerta lo avisa | Implementado. Medido en D3 |
| Los límites dependen del modelo | Límites por configuración y por RBAC | Añadidos tras la prueba del 2 de noviembre. La prueba no se repitió |
| El servidor MCP llegó el 21 de noviembre, al final | Seis lecturas en allowlist, sin escritura; el RBAC del clúster frena aunque el servidor fallara | Probado con el cliente del SDK. Sin verificar: que Claude Code lo cargue desde `.mcp.json` y un despacho real del revisor. Las 114 tareas se hicieron sin él |
| El loop corre en una sola sesión | Subagentes de contexto propio, worktrees, y una persona que fusiona | Declarado como límite |
| Solo existe en kind | Manifiestos de staging y producción conservados | Sin desplegar. Issue 28 cerrado sin implementar |
| External Secrets lee todos los `Secret` (K11) | Una instancia por namespace en staging y producción | Decidido, sin implementar |
| La edición comunitaria de MinIO ya no se mantiene: el repositorio [minio/minio](https://github.com/minio/minio) está archivado desde el 25 de abril de 2026 y su README dice «THIS REPOSITORY IS NO LONGER MAINTAINED» (consultado el 2026-11-21) | S3 del banco en staging y producción; MinIO solo en kind | Decidido, sin implementar |
| CloudNativePG va a retirar el soporte nativo de Barman Cloud, que es el que usamos. Las [notas de la versión 1.30](https://cloudnative-pg.io/docs/1.30/release_notes/v1.30) dicen 1.31.0 en la entrada de 1.30.0 (29 jun 2026) y 1.32 en la de 1.30.2 (17 nov 2026) (consultado el 2026-11-21) | Migrar al plugin de Barman Cloud antes de actualizar el operador | Pendiente. `vectra-risk/aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md` todavía dice 1.31.0 |
| Memoria: 13,8 GiB de requests en 14,8 GiB | Requests reducidos solo en kind, presupuesto con prueba (`vectra-risk/platform/tests/test_kind_profile.py`) | Mitigado. Pico medido en D2: 2 637 MiB libres |
| El registro responde lento al `CronJob` de sesgo (`U03-T07` aparcada) | Correr D2 sin otra carga | Sin 504 en la corrida de D2. La tarea sigue abierta |
| Pruebas diferidas: carga, resiliencia, PII, red negada, failover de zona | Listadas como «no ejecutado», no como aprobadas | Sin ejecutar |
| Comoditización: explicabilidad y sesgo ya son estándar | Moat en soberanía del dato y conocimiento local | Decidido en el PVB. Sin validar con un cliente |
| El argumento regulatorio es débil: no hay norma de IA vinculante de la SFC | Vender contra el marco de riesgo vigente | Decidido en el PVB |
| Grafana con al menos 5 000 carpetas «Vectra» y 5 000 «Operación» duplicadas (H-13, `vectra-risk/aidlc-docs/construction/system-verification/evidence/kind/09-d4-u11-y-grafana.md`) | Causa corregida en el PR #254 (un proveedor por carpeta con UID fijo) y comprobada en kind el 23 nov 2026: el conteo, que llegó a 49 345, dejó de crecer. Queda terminar de borrar las carpetas vacías. Respaldo: abrir el tablero por enlace directo | Mitigado al 23 nov 2026 |

Los riesgos de operación de la demo en kind (R-1 a R-11: memoria, bóveda en memoria, certificado de Linkerd, calendario de D4) están en `vectra-risk/system-verification/docs/paso-18-kind.md`, «Riesgos que pueden impedir una demo».
