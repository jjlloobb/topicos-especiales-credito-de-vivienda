# Failover de zona (NFR-U1-03, 08)

## Síntoma
`SingleZoneOperation` y, según la zona, `RegistryDbWritesBlocked`.

## Impacto
Con 2 zonas, si cae la que tiene 2 de las 3 instancias, las escrituras se bloquean hasta tener réplica síncrona. MinIO deja de aceptar escrituras (`MinioWriteQuorumLost`).

## Diagnóstico
1. `kubectl get nodes -L topology.kubernetes.io/zone`.
2. `kubectl get clusters.postgresql.cnpg.io -n vectra-data`.

## Mitigación
1. Deja que CloudNativePG promueva (≤ 60 s) y clone la réplica.
2. **Pendiente de comprobar en kind:** con `syncReplicaElectionConstraint` por zona, una réplica clonada en la zona viva podría no contar como síncrona. Mide este caso en el Paso 20.

3. **Prueba reducida en kind (2026-11-02, inconclusa):** con `registry-db` en 3 instancias y una tercera `Pending` por anti-afinidad, CloudNativePG no promovió durante 5 min de nodo caído; promovió después de que volvió, sin perder filas. No mide un failover limpio. Queda pendiente para una máquina de al menos 32 GiB.

## Escalamiento
SEV1: COE en 5 días hábiles.

## Verificación
- Réplica sincronizada y lag 0: `kubectl cnpg status registry-db -n vectra-data`.
- Pods repartidos de nuevo: `kubectl get pods -n vectra-data -o wide`.
