# SigningKeyAgeHigh y SigningKeyAgeStale

- **Severidad**: SEV3
- **Alerta**: `SigningKeyAgeHigh` y `SigningKeyAgeStale` (U2)

## Síntoma
`SigningKeyAgeHigh`: la llave de firma activa tiene más de 80 días (`vectra_signing_key_created_timestamp_seconds`, empujada por el CronJob `signing-key-age`). `SigningKeyAgeStale`: el CronJob no empuja desde hace más de 3 horas (corre cada hora).

## Impacto
Una llave de firma sin rotar a tiempo incumple la política de rotación. Sin la medición, no se sabe la edad.

## Diagnóstico
1. Edad actual y `kid`: en Grafana, `time() - vectra_signing_key_created_timestamp_seconds{job="signing-key-age"}`.
2. Estado del CronJob: `kubectl -n vectra-identity get cronjob signing-key-age` y `kubectl -n vectra-identity get jobs`.
3. Para `SigningKeyAgeStale`, además el Pushgateway: `pushgateway-down.md` en `platform/runbooks/`.
4. Llaves del realm, desde la consola de administración con port-forward aprobado (BR-U2-12): proveedor de llaves, prioridad y estado.

## Mitigación
1. Rota la llave por PR en el realm de Git (`identity-edge/keycloak/realm/realm.<entorno>.yaml`): un proveedor nuevo con mayor prioridad, y deja la anterior pasiva hasta que expiren los tokens que firmó.
2. Aplica con `keycloak-config-cli` y espera a que el CronJob mida la llave nueva.
3. Los servicios refrescan el JWKS por sí solos (`vectra_jwks_refresh_total`).
4. Si el CronJob falla, relánzalo: `kubectl -n vectra-identity create job --from=cronjob/signing-key-age signing-key-age-manual`.

## Escalamiento
SEV3: sin COE (`platform/runbooks/coe-template.md` solo se exige en SEV1 y SEV2).

## Verificación
- `kubectl -n vectra-identity logs job/signing-key-age-manual` informa la llave nueva.
- La edad en Grafana (`time() - vectra_signing_key_created_timestamp_seconds{job="signing-key-age"}`) es menor de 80 días y la alerta deja de estar `firing`.
- `promtool test rules identity-edge/observability/rules/tests/*.yaml` en el repositorio (la alerta dispara y no dispara con series sintéticas).
