# Cargar la política de referencia en kind

Lo ejecuta el operador en U04-T07 (escenarios 2 y 3 del flujo base de la demo; P-7), desde `vectra-risk/`. Sin una política `activa`, `serving-config` no tiene `policy_version_id` y `POST /v1/models/{id}/validations` responde 409 (el Job necesita el `cutoff`).

Corrige los hallazgos de la ronda 2 de la revisión de U04-T06 (`revisiones/U04-T06/ronda-2.md`): el token no se guarda en un Secret (F-01), la verificación va antes de la limpieza (F-02), no hay marcadores por reemplazar (F-04) y no queda ningún archivo temporal (F-05). `governance/tests/unit/test_kind_runbook.py` lee este archivo y falla si alguno vuelve.

## Síntoma

No hay política `activa`: `GET /v1/policies` no devuelve ninguna con `state = "activa"`, o `serving-config` no lleva `policy_version_id`.

## Impacto

Scoring no puede evaluar (falla cerrado) y la validación de un modelo no se puede pedir. Hasta que la política de referencia esté activa no corre ningún escenario de la demo.

## Diagnóstico

Antes de empezar:

1. `governance-service` está listo:

```bash
kubectl --context kind-vectra -n vectra-app rollout status deploy/governance-service --timeout=120s
```

2. `reference-policy.json` existe. Lo genera U5 en la entrega del modelo de referencia (`make -C reference-model release`; `release-base` no lo genera; ver `reference-model/docs/release.md`). Es el cuerpo de `PolicyDraft` (`cutoff`, `low_confidence_threshold`, `channel_rules`, `normative`). Su vigencia normativa debe cubrir la fecha de la demo (enmienda §5.3); si no, se reporta.

```bash
test -s reference-model/.out/reference-policy.json
```

3. Las credenciales de las personas sintéticas están en tu shell (`source "${VECTRA_E2E_KEYS_DIR:-${XDG_RUNTIME_DIR:-/tmp}/vectra-e2e-keys}/env"`, que deja `platform/kind/seed-vault.sh identity`). Hay dos personas de rol `cro` con MFA: `cro-2` y `cro-1` (`identity-edge/keycloak/realm/realm.kind.yaml`). La matriz (`contracts/openapi/role-endpoint-matrix.md`) deja `POST /v1/policies` y `POST /v1/policies/{id}/approval` solo al rol `cro`, con MFA, y BR-U4-10 exige que quien aprueba sea distinto de quien propone.

4. La imagen de `governance` está publicada en `kind-registry` (paso 1 de `governance/docs/paso-20-kind.md`): el pod de las llamadas usa su digest, que `llamar.sh` lee con `docker inspect`.

## Mitigación

Sin ningún atajo en el servicio: ni semilla en una migración ni escritura directa en `governance-db` (BR-U4-17, BR-U4-11). La política se propone y se aprueba por la API normal, con evidencia en el registro.

**Quién hace qué (P-9):** `cro-2` propone y `cro-1` aprueba. `ingeniero_riesgo` recibe 403.

**Por dónde se llama.** Con el BFF de U10 desplegado, `POST /api/console/policies` y `POST /api/console/policies/{id}/approval` por el gateway, cada una con el token de su persona. Mientras el BFF no exista (el caso de U04-T07), la malla solo admite `GET` y `POST` de `/v1/policies` desde la identidad `console-bff` (`http_routes.governance-service`, ruta `console`), y los nombres internos del clúster no resuelven en tu máquina: **todas** las llamadas, también la verificación, salen de un pod efímero de `vectra-app` con esa identidad. Governance valida el token de la persona (rol `cro`, MFA, `auth_time` de 15 min como máximo), no la identidad del pod.

**El token no se guarda en ningún sitio.** `disallow-plain-secrets` (Enforce en kind) rechaza un Secret hecho a mano, y además un token en etcd es justo lo que no se quiere. `token.sh` lo imprime y `llamar.sh` lo recibe por stdin y lo pasa por stdin al pod (`kubectl run -i`): no pasa por una variable exportada, ni por el historial, ni por un argumento de proceso. Cada token se pide justo antes de usarlo (`accessTokenLifespan` de 300 s).

### 1. Requisito previo: la ServiceAccount `console-bff`

La crea U10. Si todavía no existe, créala **solo en kind y solo para este arranque**; no va en ningún chart:

```bash
kubectl --context kind-vectra -n vectra-app get serviceaccount console-bff || { kubectl --context kind-vectra -n vectra-app create serviceaccount console-bff && kubectl --context kind-vectra -n vectra-app label serviceaccount console-bff vectra.io/creado-por=runbook-politica; }
```

Si la creaste tú, queda con la etiqueta `vectra.io/creado-por=runbook-politica` y se borra en la limpieza del final (la de U10, si existe, no se toca). Sin ella el pod no se crea: es un bloqueo explícito y el comando de arriba es la salida.

### 2. Proponer (cro-2)

El cuerpo es `reference-policy.json`. `POLICY_ID` es el de la respuesta (`policy_version_id`, `pol-...`) y no es un secreto:

```bash
POLICY_ID="$({ governance/docs/kind/token.sh cro-2; cat reference-model/.out/reference-policy.json; } | governance/docs/kind/llamar.sh politica-propone POST /v1/policies | sed -E 's/^[0-9]{3} //' | python3 -c 'import json, sys; print(json.load(sys.stdin)["policy_version_id"])')"
echo "$POLICY_ID"
```

Esperado: un `pol-` seguido del identificador. La política queda en `propuesta`. Si el comando falla, la llamada devolvió un error: ejecútala sin la sustitución para leer el cuerpo (`... | governance/docs/kind/llamar.sh politica-propone POST /v1/policies`).

### 3. Aprobar (cro-1)

Persona distinta de la que propuso; su token se pide ahora, no antes:

```bash
{ governance/docs/kind/token.sh cro-1; printf '%s\n' '{"decision":"aprobada"}'; } | governance/docs/kind/llamar.sh politica-aprueba POST "/v1/policies/$POLICY_ID/approval"
```

Esperado: `204` y cuerpo vacío. `cro-2` aprobando su propia propuesta daría 409 (`approver_is_proposer`).

## Escalamiento

- 403: el token no es del rol `cro` o el MFA venció (`auth_time` de más de 15 min): vuelve a correr el paso.
- 409 `approver_is_proposer`: aprueba con la otra persona.
- El pod queda en `ImagePullBackOff`: el digest que lee `llamar.sh` no es el publicado en `kind-registry`; repite el paso 1 de la guía.
- El pod no se crea (`serviceaccount "console-bff" not found`): falta el paso 1 de arriba.
- 503 en la propuesta o la aprobación: el registro de decisiones (U3) no responde; la transición queda `pendiente_registro` y el reconciliador la completa. Mira la regla `CompensationEventPending` y `governance/runbooks/compensation-event-pending.md`.

## Verificación

La verificación va **antes** de la limpieza. Desde dentro del clúster, con la misma identidad `console-bff` y la ruta que la malla admite:

```bash
governance/docs/kind/token.sh cro-1 | governance/docs/kind/llamar.sh politica-lee GET /v1/policies
```

Esperado: `200` y la política del paso 2 con `"state":"activa"`. La base lo confirma (solo lectura):

```bash
kubectl --context kind-vectra -n vectra-data exec governance-db-1 -c postgres -- psql -d governance -tAc "SELECT policy_version_id FROM policies WHERE state = 'activa'"
```

Imprime el mismo `POLICY_ID`. `serving-config` llevará ese `policy_version_id` cuando haya además una versión `activa` del modelo (escenario 3 de la guía): con solo la política responde 503, y es lo esperado. El evento de propuesta y el de activación están en la cadena del registro (U3).

### Limpieza (después de verificar)

Los pods de `llamar.sh` se borran solos (`--rm`) y no hay Secrets ni archivos temporales. Lo único que puede haber creado este runbook es la ServiceAccount del paso 1; se borra solo si lleva la etiqueta de este runbook:

```bash
kubectl --context kind-vectra -n vectra-app get serviceaccount -l vectra.io/creado-por=runbook-politica -o name | grep -q console-bff && kubectl --context kind-vectra -n vectra-app delete serviceaccount console-bff
```
