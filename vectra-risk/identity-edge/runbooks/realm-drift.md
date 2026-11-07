# RealmDrift y RealmDriftStale

- **Severidad**: SEV2 (`RealmDrift`), SEV3 (`RealmDriftStale`)
- **Alerta**: `RealmDrift` y `RealmDriftStale` (U2)

## Síntoma
`RealmDrift`: `vectra_realm_drift > 0`, la cantidad de diferencias entre el realm de Git y el de Keycloak que empuja el CronJob `realm-drift` al Pushgateway. `RealmDriftStale`: el CronJob no empuja desde hace más de 26 horas (corre a diario), **o** el Pushgateway no tiene el grupo (`absent(push_time_seconds{job="realm-drift"})`, B13): el CronJob nunca empujó, o el Pushgateway perdió el grupo (se borró, o se perdió su volumen de persistencia en `/data/metrics`). La alerta por ausencia solo trae la etiqueta `job="realm-drift"`.

**En kind**, si los CronJobs no corren (el clúster recién creado, o el CronJob suspendido), `RealmDriftStale` dispara. Es lo esperado: no hay medición.

## Impacto
`RealmDrift`: Keycloak se configuró fuera de Git, o Git cambió y no se aplicó. `RealmDriftStale`: no hay comparación y la deriva puede pasar sin aviso.

## Diagnóstico
1. Estado del CronJob: `kubectl -n vectra-identity get cronjob realm-drift` y `kubectl -n vectra-identity get jobs`.
2. Las diferencias, en el log del último job: `kubectl -n vectra-identity logs job/<job-de-realm-drift>`.
3. Para `RealmDriftStale`, además el Pushgateway: `pushgateway-down.md` en `platform/runbooks/`.
4. Compara con el realm de Git del entorno: `identity-edge/keycloak/realm/realm.<entorno>.yaml`.

## Mitigación
1. Si Git es lo correcto, aplica el realm con `keycloak-config-cli` (ya lo corre el despliegue) y deja que el CronJob vuelva a medir.
2. Si el cambio en Keycloak era legítimo, llévalo a Git por PR y repite el paso 1.
3. Si el job falla, resuelve la causa (token `keycloak-reader`, F94) y relanza: `kubectl -n vectra-identity create job --from=cronjob/realm-drift realm-drift-manual`.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`platform/runbooks/coe-template.md`).

## Verificación
- `kubectl -n vectra-identity logs job/realm-drift-manual` informa 0 diferencias.
- `vectra_realm_drift` en Grafana (`push_time_seconds{job="realm-drift"}` reciente) y la alerta deja de estar `firing` en Alertmanager.
- `promtool test rules identity-edge/observability/rules/tests/*.yaml` en el repositorio (la alerta dispara y no dispara con series sintéticas).
