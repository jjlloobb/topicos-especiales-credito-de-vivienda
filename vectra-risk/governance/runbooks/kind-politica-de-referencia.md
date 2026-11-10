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

- **Con el BFF de U10 desplegado**: `POST /api/console/policies` y `POST /api/console/policies/{id}/approval` por el gateway (`https://vectra.localtest.me`), cada una con el token de su persona, desde tu máquina. El BFF las lleva a U4. Los pasos 1 y 2 de abajo no hacen falta.
- **Mientras el BFF no exista (el caso de U04-T07)**: la malla solo admite `GET` y `POST` de `/v1/policies` desde la identidad `console-bff` (`http_routes.governance-service`, ruta `console`). Los nombres internos (`governance-service.vectra-app.svc.cluster.local`) **no resuelven fuera del clúster**, así que **todas** las llamadas, también la verificación, salen de un pod efímero de `vectra-app` con esa identidad. Governance valida el token de la persona (rol `cro`, MFA, `auth_time` ≤ 15 min), no la identidad del pod.

### 1. Requisito previo: la ServiceAccount `console-bff`

La crea U10. Si todavía no existe, créala **solo en kind y solo para este arranque**; no va en ningún chart:

```bash
kubectl --context kind-vectra -n vectra-app get serviceaccount console-bff || kubectl --context kind-vectra -n vectra-app create serviceaccount console-bff
```

Si la creaste tú, bórrala al terminar (paso 5). Sin ella, el pod del paso 3 no se crea: es un bloqueo explícito, y el comando de arriba es la salida.

### 2. Tokens con MFA y variables

Un token de cada persona con `acr` de MFA y `auth_time` de los últimos 15 minutos (el step-up de U0), como `user_access_token` de `identity-edge/tests/e2e/e2e_support.py` (el TOTP sale de Vault). El de `cro-1` se obtiene justo antes del paso 4.

`DIGEST` es el digest de la imagen de `governance` que el operador publicó en `kind-registry` (`docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/governance:dev`, solo la parte `sha256:…`). Esa imagen trae Python con `urllib`, no hace falta `curl`; Kyverno exige digest en `vectra-app`.

```bash
export CTX=kind-vectra
export DIGEST=sha256:REEMPLAZA_POR_EL_DIGEST_DE_LA_IMAGEN
export TOKEN_CRO2='REEMPLAZA_POR_EL_TOKEN_DE_CRO_2'
export TOKEN_CRO1='REEMPLAZA_POR_EL_TOKEN_DE_CRO_1'
test -s reference-model/.out/reference-policy.json
```

### 3. Preparar el cliente en el clúster

Un ConfigMap temporal con la política y un cliente de 15 líneas, y un Secret temporal por token (Kyverno `disallow-plain-secrets` rechaza un token literal en el pod):

```bash
cat > /tmp/llamar.py <<'EOF'
import os, sys, urllib.request, urllib.error
metodo, ruta = sys.argv[1], sys.argv[2]
cuerpo = open(sys.argv[3], "rb").read() if len(sys.argv) > 3 else None
req = urllib.request.Request("http://governance-service.vectra-app.svc.cluster.local:8080" + ruta, data=cuerpo, method=metodo)
req.add_header("Authorization", "Bearer " + open("/token/token").read().strip())
req.add_header("Content-Type", "application/json")
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print(r.status, r.read().decode())
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode())
EOF
kubectl --context $CTX -n vectra-app create configmap politica-cli --from-file=llamar.py=/tmp/llamar.py --from-file=policy.json=reference-model/.out/reference-policy.json --from-literal=aprobar.json='{"decision":"aprobada"}'
kubectl --context $CTX -n vectra-app create secret generic politica-token-cro2 --from-literal=token="$TOKEN_CRO2"
```

### 4. Proponer (cro-2), aprobar (cro-1) y verificar, desde el pod

Cada llamada es un pod propio con la identidad `console-bff`, cumpliendo la admisión de U1 (digest, no root, sistema de archivos de solo lectura, recursos, prioridad, sidecar nativo de Linkerd para que el pod termine). Define una vez la función y úsala:

```bash
llamar() {  # llamar <nombre-del-pod> <secret-del-token> <METODO> <ruta> [archivo-en-/cli]
  kubectl --context $CTX -n vectra-app delete pod "$1" --ignore-not-found >/dev/null
  kubectl --context $CTX -n vectra-app apply -f - <<MANIFEST
apiVersion: v1
kind: Pod
metadata:
  name: $1
  namespace: vectra-app
  labels: { app.kubernetes.io/name: console-bff, vectra.io/criticality: medium }
  annotations: { config.alpha.linkerd.io/proxy-enable-native-sidecar: "true" }
spec:
  serviceAccountName: console-bff
  restartPolicy: Never
  priorityClassName: vectra-low
  securityContext: { runAsNonRoot: true, runAsUser: 65532, runAsGroup: 65532, seccompProfile: { type: RuntimeDefault } }
  containers:
    - name: llamar
      image: kind-registry:5000/vectra/governance@$DIGEST
      command: [python, /cli/llamar.py, "$3", "$4"$( [ -n "${5:-}" ] && printf ', "%s"' "$5" )]
      securityContext: { allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: { drop: [ALL] } }
      resources: { requests: { cpu: 50m, memory: 64Mi }, limits: { cpu: 200m, memory: 128Mi } }
      volumeMounts: [ { name: cli, mountPath: /cli, readOnly: true }, { name: token, mountPath: /token, readOnly: true } ]
  volumes:
    - { name: cli, configMap: { name: politica-cli } }
    - { name: token, secret: { secretName: $2 } }
MANIFEST
  kubectl --context $CTX -n vectra-app wait pod "$1" --for=jsonpath='{.status.phase}'=Succeeded --timeout=120s
  kubectl --context $CTX -n vectra-app logs "$1" -c llamar
}
llamar politica-propone politica-token-cro2 POST /v1/policies /cli/policy.json
```

La respuesta es `200 {…}` con la política en `propuesta` y su `policy_version_id` (`pol-…`). Anótalo y aprueba con `cro-1` (el cuerpo `aprobar.json` ya está en el ConfigMap del paso 3):

```bash
export POLICY_ID=pol-REEMPLAZA_POR_EL_ID_DE_LA_RESPUESTA
kubectl --context $CTX -n vectra-app create secret generic politica-token-cro1 --from-literal=token="$TOKEN_CRO1"
llamar politica-aprueba politica-token-cro1 POST "/v1/policies/$POLICY_ID/approval" /cli/aprobar.json
```

Esperado: `204` y cuerpo vacío. `cro-2` aprobando su propia propuesta daría 409 (`approver_is_proposer`).

### 5. Limpieza

```bash
kubectl --context $CTX -n vectra-app delete pod politica-propone politica-aprueba politica-lee --ignore-not-found
kubectl --context $CTX -n vectra-app delete configmap politica-cli --ignore-not-found
kubectl --context $CTX -n vectra-app delete secret politica-token-cro1 politica-token-cro2 --ignore-not-found
kubectl --context $CTX -n vectra-app delete serviceaccount console-bff   # solo si la creaste en el paso 1
```

## Escalamiento

- 403: el token no es del rol `cro` o el MFA venció (`auth_time` > 15 min): vuelve a obtenerlo.
- 409 `approver_is_proposer`: aprueba con la otra persona.
- El pod queda en `ImagePullBackOff`: el digest no es el publicado en `kind-registry`.
- 503 en la propuesta o la aprobación: el registro de decisiones (U3) no responde; la transición queda `pendiente_registro` y el reconciliador la completa. Mira la regla `CompensationEventPending` y `governance/runbooks/compensation-event-pending.md`.

## Verificación

Desde dentro del clúster, con la misma identidad `console-bff` y la ruta que la malla admite (`GET /v1/policies`):

```bash
llamar politica-lee politica-token-cro1 GET /v1/policies
```

Esperado: `200` y un `"state":"activa"` para el `policy_version_id` del paso 4. Luego, `kubectl --context $CTX -n vectra-data exec governance-db-1 -c postgres -- psql -d governance -tAc "SELECT policy_version_id FROM serving_config"` imprime el mismo id: `serving-config` ya lleva la política. El evento de propuesta y el de activación están en la cadena del registro (U3).
