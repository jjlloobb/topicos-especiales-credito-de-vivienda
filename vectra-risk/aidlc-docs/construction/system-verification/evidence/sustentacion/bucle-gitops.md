# El bucle GitOps de punta a punta, con un PR real

Pedido de `modulo8/guia-entrega-proyecto-final.md`, sección 3.2: «el bucle GitOps funcionando: un cambio en Git que se reconcilia en el clúster».

Este documento sigue un cambio real del 21 de noviembre de 2026, el PR #233, desde que se propone hasta que el clúster `kind-vectra` lo refleja. Es la promoción a producción de una versión de modelo durante la demo D2.

**De dónde sale cada dato.**

- Lo de GitHub (fechas, autor, quién aprobó, commit de fusión, CI) se leyó el 21 de noviembre de 2026 con `gh pr view <n> --json title,createdAt,mergedAt,mergeCommit,author,mergedBy,reviews` y `gh pr checks <n>`. Cualquiera puede repetirlo.
- Lo del clúster **no se volvió a ejecutar para escribir este documento**. Se cita lo que el operador ya dejó escrito en la plantilla de evidencia de D2, [`../kind/08-d2-rt2.md`](../kind/08-d2-rt2.md), entradas K-54 y K-61. La versión llena de esa plantilla está en la rama `verificacion/20261120-9dc027f` (PR #236); en `main` queda llena cuando ese PR se fusione.
- Todas las horas son UTC.

## El cambio

Una línea de configuración en Git: la versión `mv-2026-01-01-f12bfeaf` pasa a tener, además de su entrada `staging`, una entrada `prod` en `vectra-risk/vectra-risk-gitops/values/kind/model-serving.yaml`.

```diff
   - modelVersionId: mv-2026-01-01-8a98ab02
     storageUri: s3://model-store/mv-2026-01-01-8a98ab02/
     profile: prod
-  - { modelVersionId: mv-2026-01-01-f12bfeaf, storageUri: "s3://model-store/mv-2026-01-01-f12bfeaf/", profile: staging }
+  - modelVersionId: mv-2026-01-01-f12bfeaf
+    storageUri: s3://model-store/mv-2026-01-01-f12bfeaf/
+    profile: staging
+  - modelVersionId: mv-2026-01-01-f12bfeaf
+    storageUri: s3://model-store/mv-2026-01-01-f12bfeaf/
+    profile: prod
```

Ese archivo lo lee la Application `model-serving` de Argo CD (`vectra-risk/vectra-risk-gitops/apps/kind/model-serving.yaml`, wave 6, sin `syncPolicy.automated`). El chart `vectra-risk/model-serving/chart` genera un `InferenceService` de KServe por entrada.

## Los cinco pasos

| # | Paso | Quién | Cuándo (UTC) | Evidencia |
|---|---|---|---|---|
| 1 | **Propuesta.** `promotion-tool create-promotion-pr mv-2026-01-01-f12bfeaf` edita el archivo y abre el PR #233. La herramienta exige la sesión de un ingeniero con MFA (`acr=mfa`, `vectra-risk/governance/promotion_tool/vectra_promotion/api.py`) | Operador, con `promotion-tool` | 09:52:59 la orden; 09:53:07 el PR | Commit `1f85ac2`. El cuerpo del PR trae la evidencia: el SHA-256 del `helm template`, la tabla de objetos que resultan y un `kubectl diff` de solo lectura contra kind |
| 2 | **CI.** Corren los workflows del repositorio | GitHub Actions | tras abrir el PR | `gh pr checks 233`: `checks`, `evidence`, `forbidden`, `policies`, `rollback-note`, `supply-chain / scan` y `tests` en `pass`. `forbidden` es la prueba de que ningún workflow aplica cambios a un clúster (`.github/workflows/forbidden-steps.yml`) |
| 3 | **Aprobación humana.** Aprueba una cuenta distinta de la autora; la protección de `main` exige esa revisión, también a administradores | `joseluisjedi` | 09:53:57 | Revisión `APPROVED`. El PR toca `vectra-risk/vectra-risk-gitops/`, que `.github/CODEOWNERS` reserva a dos cuentas |
| 4 | **Fusión.** | `joseluisjedi` | 10:00:31 | Commit de fusión `81b5fd38e315d0aafb3280be5b0eab897068c513` en `main` |
| 5 | **Reconciliación.** Argo CD no sincroniza solo: hace falta la orden `argocd app sync model-serving --prune` | Operador (ver «Quién dio la orden de sync») | entre 10:00:31 y 10:01:25 | Plantilla 08, K-54 |

## El estado en el clúster después del sync

Citado de la plantilla 08, K-54 (no ejecutado de nuevo):

- `promotion-tool mark-active mv-2026-01-01-f12bfeaf` salió con código 0 a las 10:01:27 y respondió `isvc-f12bfeaf`.
- A las 10:02:15 el sistema respondía: `mv-2026-01-01-f12bfeaf` en `activo` y `mv-2026-01-01-8a98ab02` en `inactivo`.
- Durante la promoción los 4 pods de `isvc-8a98ab02` siguieron `Running` mientras nacían los 4 de `isvc-f12bfeaf`: el modelo activo nunca bajó de 2 réplicas.
- Memoria en el pico de la promoción: 2 637 MiB disponibles con 52 pods medidos (la puerta es 1 536 MiB).

## El camino de vuelta: rollback por el mismo bucle

La reversión no es un `kubectl` de emergencia. Es otro PR, el #237 (`promotion-tool rollback-pr mv-2026-01-01-8a98ab02`), que devuelve el modelo de referencia a `profile: prod`.

| Paso | Cuándo (UTC) | Dato |
|---|---|---|
| PR abierto | 11:33:22 | #237, «restaurar minimos de produccion de isvc-8a98ab02» |
| Aprobado | 11:33:57 | `joseluisjedi` |
| Fusionado | 11:38:47 | commit `533647dc4c8c4d712ac96fc265709ab2d806d858` |
| Sync y `mark-active` | 11:46:08 a 11:46:46 | `mark-active` con código 0, responde `isvc-8a98ab02` |
| Estado final | 11:47:00 | `mv-2026-01-01-8a98ab02` en `activo`, `mv-2026-01-01-f12bfeaf` en `inactivo`; «cierre de D2: pasa» (plantilla 08, K-61) |

Un tropiezo real de ese camino, también en la plantilla: `mark-active` dio 403 dos veces antes de pasar, porque el navegador reutilizó la sesión del presentador y el token no era de ingeniero (hallazgo H-10). El control de acceso funcionó; lo que falló fue la operación.

## Todos los cambios al clúster de esa jornada

Cada fila es un PR creado, aprobado, fusionado y sincronizado a mano. Los datos son de `gh pr view`.

| PR | Qué cambia | Fusionado (UTC, 21 nov) | Commit |
|---|---|---|---|
| #226 | `runId` de RT-5 en kind (demo D3) | 01:10:22 | `85c267d` |
| #227 | F22 apagado (demo D1) | 01:44:38 | `7306d7d` |
| #228 | F22 encendido de nuevo | 02:12:37 | `e67ce6d` |
| #230 | F22 apagado para repetir D1 | 03:25:29 | `8fbf10b` |
| #231 | F22 encendido de nuevo | 09:39:35 | `a83ee8e` |
| #232 | Proxy de D2 en staging | 09:49:32 | `45c2b2e` |
| #233 | Promoción de `isvc-f12bfeaf` (`promotion-tool`) | 10:00:31 | `81b5fd3` |
| #234 | `isvc-8a98ab02` a inactivo (`promotion-tool`) | 10:07:16 | `b57c889` |
| #237 | Rollback: `isvc-8a98ab02` de vuelta a `prod` (`promotion-tool`) | 11:38:47 | `533647d` |
| #238 | Retirar el proxy de staging | 11:53:49 | `077a228` |
| #239 | Imagen de la consola con el tema nuevo | 13:03:33 | `797e6aa` |
| #240 | `isvc-f12bfeaf` a inactivo (`promotion-tool`) | 13:17:11 | `e222643` |
| #243 | Imagen de la consola con el arreglo de enlaces directos | 14:04:00 | `d8d00f0` |

Los trece los aprobó y fusionó `joseluisjedi`; el autor de todos es `jjlloobb`.

## Lo que este documento no demuestra

- **Quién dio la orden de sync.** La plantilla 08 dice: «Operador: jjlloobb, con Claude Code ejecutando las órdenes». El `argocd app sync` lo tecleó la sesión del orquestador, con la aprobación de la persona orden por orden (`vectra-risk/DECISIONES-LOOP.md`, §11). No fue un agente por su cuenta, pero tampoco fue una persona sola en una terminal.
- **El estado del clúster tras los PR #238, #239, #240 y #243.** Son posteriores a la plantilla 08, que se cerró a las 11:47. De ellos este documento solo afirma lo que dice GitHub.
- **Reconciliación automática.** No existe y es a propósito: la política `disallow-argocd-auto-sync` de Kyverno la prohíbe (`vectra-risk/platform/policies/kyverno/disallow-argocd-auto-sync.yaml`). El bucle es «Git manda, una persona sincroniza», no «Git manda y el clúster sigue solo».
- **Staging y producción.** Todo ocurrió en kind, en un portátil.
