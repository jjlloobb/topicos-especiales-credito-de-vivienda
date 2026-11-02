# Evidencia del ensayo de U1 en kind (issue 7)

Ejecutado por el agente a pedido del responsable, con su aprobación registrada en el issue 7, solo en `kind-vectra`. El perfil es el liviano de 14 GiB.

| Archivo | Contenido |
|---|---|
| `digests.txt` | Digests de las imágenes publicadas en `kind-registry` |
| `conformidad-cni.txt` | Resultado de la conformidad de NetworkPolicy |
| `estado-tras-tramo-c.txt` | Aplicaciones, bases y nodos después de la instalación |
| `simulacro-restore.txt` | Restore de `registry-db` y `case-db` desde MinIO |
| `simulacro-latest.txt` | Rechazo de un Pod con `latest` |
| `simulacro-objeto-bloqueado.txt` | Borrado rechazado de un objeto bloqueado |
| `simulacro-ilm.txt` | Regla `ilm` repetida: se acumula, sin corregir |
| `simulacro-failover-reducido.txt` | Failover reducido de `registry-db`: **inconcluso** |
| `make-check.txt` | Final de `make -C platform check` |
| `linkerd-check.txt` | Salida de `linkerd check` |
| `cierre-acotado.md` | Cierre con alcance acotado |
