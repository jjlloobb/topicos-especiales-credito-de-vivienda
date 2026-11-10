# Cargar la política de referencia en kind

Lo ejecuta el operador en U04-T07 (escenarios 2 y 3 del flujo base de la demo; P-7). Sin una política `activa`, `serving-config` no tiene `policy_version_id` y `POST /v1/models/{id}/validations` responde 409 (el Job necesita el `cutoff`).

## Síntoma

No hay política `activa`: `GET /v1/policies` no devuelve ninguna con `state = "activa"`, o `serving-config` no lleva `policy_version_id`.

## Impacto

Scoring no puede evaluar (falla cerrado) y la validación de un modelo no se puede pedir. Hasta que la política de referencia esté activa no corre ningún escenario de la demo.

## Diagnóstico

Antes de empezar:

1. `governance-service` está listo: `kubectl --context kind-vectra -n vectra-app rollout status deploy/governance-service --timeout=120s`.
2. `reference-policy.json` existe. Lo genera U5 en la entrega del modelo de referencia: `make -C reference-model release` (o `release-base`, que no la genera; ver `reference-model/docs/release.md`). Queda en `reference-model/.out/reference-policy.json` y es el cuerpo de `PolicyDraft` (`cutoff`, `low_confidence_threshold`, `channel_rules`, `normative`).
3. Hay dos personas de rol `cro` con MFA: `cro-2` y `cro-1` (`identity-edge/keycloak/realm/realm.kind.yaml`). La matriz (`contracts/openapi/role-endpoint-matrix.md`) deja `POST /v1/policies` y `POST /v1/policies/{id}/approval` solo al rol `cro`, con MFA, y BR-U4-10 exige que quien aprueba sea distinto de quien propone.

## Mitigación

Sin ningún atajo en el servicio: ni semilla en una migración ni escritura directa en `governance-db` (BR-U4-17, BR-U4-11). La política se propone y se aprueba por la API normal, con evidencia en el registro.

**Quién hace qué (P-9: corrige al usuario de ingeniería que proponía en el plan, algo que la matriz y BR-U4-10 no permiten):** `cro-2` propone y `cro-1` aprueba. `ingeniero_riesgo` recibe 403.

### Por dónde se llama

- **Con el BFF de U10 desplegado** (lo normal cuando exista): `POST /api/console/policies` y `POST /api/console/policies/{id}/approval` por el gateway (`https://vectra.localtest.me`), cada una con el token de su persona. El BFF las lleva a U4 `POST /v1/policies` y `…/approval`.
- **Mientras el BFF no exista** (es el caso hoy): directo a U4 con el token del rol. La malla solo admite esas rutas desde la identidad `console-bff` (`http_routes.governance-service`, ruta `console`), así que la llamada sale de un pod efímero de `vectra-app` que usa la `ServiceAccount` `console-bff` y la etiqueta `app.kubernetes.io/name: console-bff`. Si esa cuenta no existe todavía, créala solo para este paso y bórrala al terminar. Governance sigue validando el token de la persona (rol, MFA, `auth_time` ≤ 15 min), no la identidad del pod.

### 1. Tokens con MFA

Un token de cada persona, con `acr` de MFA y `auth_time` de los últimos 15 minutos (el step-up de U0). Se obtienen como en `identity-edge/tests/e2e/e2e_support.py` (`user_access_token`, con el TOTP desde Vault): primero `cro-2`, y el de `cro-1` justo antes de aprobar.

```bash
export TOKEN_CRO2="$(…)"   # cro-2, MFA fresco
export TOKEN_CRO1="$(…)"   # cro-1, MFA fresco
```

### 2. Proponer (cro-2)

```bash
kubectl --context kind-vectra -n vectra-app run politica --rm -i --restart=Never \
  --image=localhost:5001/mc:dev --serviceaccount=console-bff --labels=app.kubernetes.io/name=console-bff \
  --env=TOKEN="$TOKEN_CRO2" --command -- sh -c \
  'curl -s -X POST http://governance-service.vectra-app.svc.cluster.local:8080/v1/policies \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" --data-binary @-' \
  < reference-model/.out/reference-policy.json
```

(Cualquier imagen con `curl` sirve; con el BFF, sustituye la URL por `https://vectra.localtest.me/api/console/policies`.) La respuesta es la política en `propuesta` con su `policy_version_id` (`pol-…`). Anótalo:

```bash
export POLICY_ID=pol-…
```

### 3. Aprobar (cro-1)

```bash
… curl -s -o /dev/null -w '%{http_code}\n' -X POST \
     http://governance-service.vectra-app.svc.cluster.local:8080/v1/policies/$POLICY_ID/approval \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"decision":"aprobada"}'
```

Esperado: `204`. `cro-2` aprobando su propia propuesta da 409 (`approver_is_proposer`).

## Escalamiento

- 403: el token no es del rol `cro` o el MFA venció (`auth_time` > 15 min): vuelve a obtenerlo.
- 409 `approver_is_proposer`: aprueba con la otra persona.
- 503 en la propuesta o la aprobación: el registro de decisiones (U3) no responde; la transición queda `pendiente_registro` y el reconciliador la completa. Mira la regla `CompensationEventPending` y `governance/runbooks/compensation-event-pending.md`.

## Verificación

Cada paso nombra su comando:

```bash
# La política quedó activa (lectura por la misma vía, con el token de cro-1):
curl -s http://governance-service.vectra-app.svc.cluster.local:8080/v1/policies -H "Authorization: Bearer $TOKEN" | grep -o '"state":"activa"'
# serving-config ya lleva su policy_version_id (lo leen scoring y case-worker; aquí, con la identidad console-bff solo si la ruta lo admite):
kubectl --context kind-vectra -n vectra-data exec governance-db-1 -c postgres -- psql -d governance -tAc "SELECT policy_version_id FROM serving_config"
```

Esperado: una línea `"state":"activa"` y el `policy_version_id` del paso 2. El evento `propuesta` y el de activación están en la cadena del registro (`GET /v1/entries?…` de U3).
