# Ronda 1 — U01-T05

VEREDICTO: VERDE

Revisado: rama `tarea/U01-T05`, sha `7036e18`, base `f44ba83`. Ejecuté todo desde `vectra-risk/`. No corrí nada contra un clúster. El worktree quedó limpio (`git status --short` vacío antes y después) y el HEAD no cambió.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Casos `promtool`: archivador fallando (dispara), base inactiva (no dispara), segmentos pendientes (dispara) | `cd platform/observability/rules/tests && ../../../.tools/bin/promtool test rules *.yaml` | pasa: `SUCCESS`, rc=0, 2m26s con la máquina cargada. Los tres casos existen en el archivo |
| 2 | Reglas válidas y las probadas son las desplegadas | `platform/.tools/bin/promtool check rules platform/observability/rules/platform-rules.yaml && uv run pytest platform/tests/test_ci.py platform/tests/test_platform.py -q` | pasa: `SUCCESS: 33 rules found`, `348 passed in 14.11s`, rc=0 |

Los dos tiempos tienen explicación:
- El subconjunto de 5 casos de `WalArchiveStale` tarda 0,14 s, así que los 2m26s vienen del resto del archivo. No medí qué parte exacta los consume.
- La bitácora dice 107 s para los 348 tests y yo medí 14 s. El número de pruebas coincide y la diferencia es compatible con la carga de la máquina, pero no la medí.
- Ninguna prueba se omitió.

## Comprobaciones adversariales
Todas se hicieron en una copia temporal, nunca en el worktree.

**Rojo primero, reproducido.** Con la regla de `f44ba83` y las pruebas de HEAD filtradas a `WalArchiveStale`, `promtool` da rc=1. Falla un caso, `time: 10m`, `exp` con `SEV1`/`registry-db` y `got:[]`. Coincide con la bitácora.

**Mutaciones de la regla.** Las corrí con la suite filtrada a los 5 casos de `WalArchiveStale`.

| Mutación | Resultado |
|---|---|
| M1 quitar la rama de fallos | detectada (rc=1) |
| M2 `failed_count > 0` sin `increase` | detectada: es el caso de base inactiva |
| M3 quitar la rama de pendientes | detectada |
| M4 quitar `and on (cluster) ...ready` | detectada (2 casos) |
| M5 nombre de métrica erróneo | detectada |
| M6 umbral `> 100` | detectada |
| M7 ventana `[5m]` → `[1h]` | **sobrevive** (ver F-01) |
| M8 quitar la rama solo de `.prometheusrule.yaml` | detectada por `test_deployed_rules_are_the_tested_rules`; el control sin mutar pasa |

**Escenarios propios sobre la regla real, con `promtool`.** Todos dieron el resultado esperado:
- **Fallo único:** el contador pasa de 3 a 4 en t=5m. Sin alerta a 4m ni a 5m (`pending`), firing a 6m y resuelta a 12m y a 30m.
- **Ambas ramas a la vez:** una sola alerta. El `or` deduplica porque coinciden las etiquetas.
- **Reinicio del contador de 100 a 0:** no dispara.
- **Multi-instancia:** solo alerta el pod que falla.
- **Fallos históricos con base inactiva 300 min:** no dispara.
- **Archivador fallando con `ready=0` y último archivado antiguo:** dispara.
- **`0x20` sin comillas:** `promtool` lo lee como repetición y no como hexadecimal, así que los casos "no dispara" no pasan por accidente.

**Alcance.**
- El diff en las reglas se limita a la línea `expr` de `WalArchiveStale` en los dos archivos.
- No cambian severidad, `for`, anotaciones ni otras alertas.
- También tocan el runbook (síntoma), el archivo de pruebas y la bitácora. No hay desborde.
- El hash de la tarea en la bitácora coincide con `git hash-object` (`ac4e702…`).

**Fuente de la métrica.**
- El `PodMonitor` de `platform/data/chart/templates/clusters.yaml` pone la etiqueta `cluster` por relabel y no hay `metricRelabelings` ni `keep`/`drop` en `platform/` (sin contar `.tools` y `rendered`), así que nada filtra la métrica.
- `platform/tests/test_alert_sources.py` da 7 passed, aunque está fuera del CA.
- **Sin verificar:** que `cnpg_pg_stat_archiver_failed_count` exista en un exportador real. Comprobarlo exigiría un clúster. La tarea da el nombre y la métrica hermana ya se usa.

**Literal `[5m]`.** No lo trato como hallazgo. Prometheus no admite constantes en la expresión, el valor está en la misma regla que el `300` existente y el runbook lo documenta.

## Hallazgos
### F-01 · AMARILLO · `platform/observability/rules/tests/platform-rules-test.yaml` · La suite no fija la ventana de 5 min
La mutación `[5m]` → `[1h]` deja la suite filtrada en `SUCCESS`. Ningún caso comprueba que una base con un fallo reciente deje de disparar al pasar la ventana, aunque el runbook promete "aumenta en 5 min". El comportamiento actual es correcto (escenario de fallo único, resuelta a 12m). Lo que falta es solo el candado y ningún CA lo exige.

### F-02 · AMARILLO · `aidlc-docs/construction/platform-foundation/nfr-design/logical-components.md:111` y `nfr-requirements/nfr-requirements.md:34` · Documentos con la definición anterior
Ambos describen `WalArchiveStale` solo como "> 5 min" o "> 5 min con segmentos pendientes". Tras este diff esa descripción queda incompleta. No figuran en los archivos de contexto de la tarea, y por eso lo dejo como candidata y no como exigencia aquí.

### F-03 · AMARILLO · `platform-rules.yaml`, `expr` de `WalArchiveStale` · Un solo fallo transitorio pagina SEV1
Con `for: 1m` y `increase[5m] > 0`, un único fallo de archivado produce un SEV1 de unos 5 min (escenario de fallo único). Es lo que pide la tarea ("aumenta") y cambiar severidades queda fuera de alcance. Lo señalo para que quien fusiona lo sepa, por el posible ruido en operación ante cortes breves de S3.

## Tareas candidatas (defectos reales fuera de alcance)
- Actualizar en `aidlc-docs` (F-02) la definición de `WalArchiveStale`.
- Añadir el caso "un fallo antiguo deja de disparar" (F-01).
- Valorar si un fallo aislado debe pagina SEV1 o si conviene exigir fallos sostenidos (F-03).

## Rutas de transcripciones largas
- Escenarios, mutaciones y copia temporal: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-U01-T05-ccqjqe`

VEREDICTO: VERDE
