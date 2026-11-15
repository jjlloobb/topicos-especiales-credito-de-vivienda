# U01-T10 — Arbitraje de la ronda 1 (orquestador, 2026-11-14)

Informe: `ronda-1.md`. Veredicto NO-VERDE, con un ROJO (F-01). El usuario fusionó el PR #176 en `main` (baf38d1) antes de que la revisión terminara, así que no hay ronda 2 sobre esa rama: los hallazgos se atienden en **U01-T11** (recortes de kind), que nace de la rama de U01-T10, toca los mismos archivos y ya trata del presupuesto.

El ROJO no es un defecto del comportamiento: la política de MinIO es correcta y su prueba es buena (el revisor la vio fallar con dos mutaciones). Lo que falla es el comando del criterio CA-2 (`-k minio`), que escribió el orquestador en la tarea y que no selecciona la prueba nueva; la bitácora presentó como verde una corrida que no la ejecutó.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: el comando de CA-2 no ejecuta la prueba nueva | **Entra en U01-T11** | Un renombre; sin él, el criterio pasa con la política rota |
| F-02 NARANJA: el override global `instances: 3` del simulacro de failover ya no surte efecto | **Entra en U01-T11** | El runbook describe un mecanismo que ya no funciona |
| F-03 NARANJA: el presupuesto no cuenta Envoy, Envoy Gateway ni ratelimit (≥ 0,94 GiB) | **Entra en U01-T11** | U01-T11 fija el presupuesto tras los recortes: tiene que contar lo que se conoce |
| F-04 NARANJA: la imagen de metrics-server se descarga de `registry.k8s.io` sin autorización | **Pregunta al usuario** | Las descargas las autoriza él; no se sincroniza `metrics-server` hasta su respuesta |
| F-05 AMARILLO: frase duplicada en `install.md:18` | **Entra en U01-T11**, con F-02 | — |
| F-07 AMARILLO: pasos del runbook no marcados como no medidos | **Entra en U01-T11** | Una línea por paso |
| F-06 y F-08 AMARILLO | No requieren cambio | El límite de CPU de la bóveda se mide al desplegar |
| Candidatas (Jobs en el presupuesto; espejar los operadores de origen) | A `CANDIDATAS.md` | Fuera de alcance |

## Lo que se añade a U01-T11

- **F-01.** La prueba de la política de `validation-readonly` pasa a llamarse de forma que `-k minio` la seleccione. Evidencia: `--collect-only -k minio` la lista, y con la política mutada (sin `model-store`; con `s3:PutObject`) el comando de CA-2 falla.
- **F-02 y F-05.** El simulacro de failover (Paso 20) vuelve a tener un mecanismo que funciona con el `instances` por cluster, y `values-kind.yaml` e `install.md` lo describen sin la frase duplicada. Prueba: el render de kind con el override del simulacro da 3 instancias en los cuatro clusters.
- **F-03.** La prueba del presupuesto cuenta el data plane de Envoy (del `EnvoyProxy` de kind), el controlador de Envoy Gateway y ratelimit, o los declara como constantes atadas a sus archivos de origen con una prueba que falla si esos archivos cambian. Si el controlador de KServe tiene una cifra conocida, también. Los Jobs pueden quedar fuera, dicho en la bitácora con su estimación.
- **F-07.** Los pasos del runbook que no salen de lo medido el 2026-11-14 se marcan como no medidos.
