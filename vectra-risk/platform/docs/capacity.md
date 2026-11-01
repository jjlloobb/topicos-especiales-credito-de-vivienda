# Capacidad (NFR-U1-10, 11, 13)

- Diseño: 2 solicitudes/s sostenidas y picos de 10/s. Prueba: 20/s durante 15 min (sección `load` de U12).
- Nodos iniciales (INF-U1-01): `general` ≥ 4 por zona de 8 vCPU / 32 GiB; `data` ≥ 2 por zona de 8 vCPU / 32 GiB.
- Cuotas: `platform/policies/quotas/quotas.yaml`, con el proxy de Linkerd y el 30 %.
- Los recursos de `vectra-data` y `vectra-observability` son estimaciones iniciales: U12 informa los resultados y un PR a los values los ajusta.
