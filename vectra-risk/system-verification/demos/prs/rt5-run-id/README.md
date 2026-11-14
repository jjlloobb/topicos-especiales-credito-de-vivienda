# PR `rt5-run-id`: el `runId` de la verificación (D3, RT-5)

El parche **lo genera `prepare`** (`vectra-verification prepare --commit … --operator …`), con el `runId` de esa verificación: `case-management-runid.patch` en el directorio de la verificación. Agrega
`runId: "<runId>"` bajo `probes:` en `vectra-risk/vectra-risk-gitops/values/kind/case-management.yaml`, entre comillas, y nada más (ni `probes.enabled`, ni staging, ni producción). `ejemplo.patch` es el de un
`runId` de ejemplo (`20261112-0900`); una prueba comprueba que `prepare` produce exactamente ese formato.

El operador abre el PR, lo fusiona y sincroniza la Application `case-management` en Argo CD, con prune: el Job `rt5-demo-<runId>` nace después de `started_at`.
El formato `AAAAMMDD-HHMM` lo valida la plantilla del chart (`case-management/chart/templates/rt5-demo-job.yaml`), no `conftest`. Ese `runId` solo vive en los values de kind:
`make -C case-management policy-chart` lo prohíbe en staging, producción y los values del chart.
