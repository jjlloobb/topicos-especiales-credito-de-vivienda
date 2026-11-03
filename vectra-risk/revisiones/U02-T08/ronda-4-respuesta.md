# Respuesta a la ronda 4 — U02-T08

Código en 589f894. Evidencia, con las salidas expandidas, en `bitacoras/U02-T08.md` (sección «Ronda 5»).

- T1-b: Corregido en 589f894: `platform/tests/test_platform.py` (`test_trivy_skips_only_the_kind_secret_read`, ahora `test_trivy_skips_only_the_kind_secret_read_and_the_realm_configmaps`) exige que `skip-files` sea exactamente la lista de cuatro archivos (el de ESO y los tres `realm-configmap.yaml`), sin comodines ni espacios. Antes de cambiarla la corrí tal cual y falló como en el PR 59; después pasa. `make -C platform check-local` termina en 0 en este entorno (619 passed; la prueba de Grafana no necesitó Docker).
- F-14/F-15: candidatas: ya están en `CANDIDATAS.md`; no se tocaron en esta ronda. En cuanto a F-14, esta vez la bitácora trae las salidas reales expandidas.
