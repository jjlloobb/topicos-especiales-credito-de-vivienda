# PR `rt5-run-id`: el `runId` de la verificación (D3, RT-5)

El parche **lo genera `prepare`** (`vectra-verification prepare --commit … --operator …`), con el `runId` de esa verificación: `case-management-runid.patch` en el directorio de la verificación. Agrega
`runId: "<runId>"` bajo `probes:` en `vectra-risk/vectra-risk-gitops/values/kind/case-management.yaml`, entre comillas, y nada más (ni `probes.enabled`, ni staging, ni producción). `ejemplo.patch` es el de un
`runId` de ejemplo (`20261112-0900`); una prueba comprueba que `prepare` produce exactamente ese formato.

El operador abre el PR, lo fusiona y sincroniza la Application `case-management` en Argo CD, con prune: el Job `rt5-demo-<runId>` nace después de `started_at`.
El formato `AAAAMMDD-HHMM` lo valida la plantilla del chart (`case-management/chart/templates/rt5-demo-job.yaml`), no `conftest`. Ese `runId` solo vive en los values de kind:
`make -C case-management policy-chart` lo prohíbe en staging, producción y los values del chart.

## Repetir D3 tras un fallo a medias

Un segundo `prepare` se niega mientras los values conserven el `runId` (`values_already_have_runid`, `system-verification/src/vectra_verification/manifest.py`, `runid_patch`), y el Job `rt5-demo-<runId>` se creó con `backoffLimit: 0` y sin `ttlSecondsAfterFinished`
(`case-management/chart/templates/rt5-demo-job.yaml`): no se reintenta solo y el operador no puede borrarlo con su lista cerrada de órdenes. Argo CD lo **poda** cuando deja de renderizarse (`prune`). El camino, todo por PR desde el clon de
promoción de la guía (`$PROMO`, con `git -C "$PROMO" pull --ff-only` antes de cada rama):

1. **Quitar el `runId`:** `git -C "$PROMO" apply -R "$EVID/case-management-runid.patch"` en una rama nueva, PR, fusión. El parche de `prepare` solo toca esa línea de `case-management.yaml`, que `promotion-tool` no edita: el inverso aplica.
2. **Sincronizar `case-management` con prune:** el Job viejo desaparece.
3. **Volver a ponerlo:** `git -C "$PROMO" apply "$EVID/case-management-runid.patch"` en otra rama nueva, PR, fusión, y otro sync con prune: nace `rt5-demo-<runId>` otra vez, con el mismo `runId` y después de `started_at`.
4. `vectra-verification rt5 --redo` (el contador de Linkerd no distingue un ensayo anterior: ver `demos/rt-5.md`).

Para una verificación **nueva** (otro directorio de evidencias) el paso 3 no se hace: tras quitar el `runId` viejo, `prepare` en el directorio nuevo produce otro `runId` y otro parche.
