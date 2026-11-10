# Ronda 2 — U04-T08

VEREDICTO: VERDE

Revisor, 2026-11-10, punta `cd6a50b`, base `ef65ce6`. El revisor entregó el informe en su respuesta; el orquestador lo transcribe.

| # | Resultado |
|---|---|
| Diff | 14 archivos: chart (`service-identity.yaml`, `service.yaml`, `values.yaml`, `service.rego`, `set.rego`), `service.py`, `api.py`, 5 pruebas, `CANDIDATAS.md` y bitácora; nada en `platform/` ni en otras unidades |
| Identidad | `ExternalSecret` `governance-service-client` desde `identity/clients/governance-service`, propiedad `private-key`; el cliente existe en `realm.{kind,staging,prod}.yaml` (`client-jwt`, ES256, `bias:compare`, `registry:append:governance`) y la bóveda lo siembra; montaje `readOnly`, `defaultMode` 0444, pod como 65532 |
| URLs | registro → `decision-registry-service:8080` (F24); bias → `bias-monitoring-service:8080` (F25); `VECTRA_TOKEN_URL` igual al de los identity-jobs de U2 (F50) |
| `REQUIRED` | las 5 variables, sin `DEFAULT_*` |
| CA-1 | 7 passed: contenedor real como 65532, `read_only`, llave EC montada; `POST /v1/policies` 200 y transición `confirmada`; el registro falso exige el token que solo sale del `/token` (`client_assertion`, `scope=registry:append:governance`) |
| Admisión | `policy-chart-u1` en los tres entornos `pass: 19, fail: 0`, incluida `disallow-plain-secrets`; mutaciones de la regla `service-identity` fallan como deben |
| F-02 / F-04 | aviso al arrancar sin llave, fila `pendiente_registro`, 503 `problem+json`, ningún token al registro; store cerrado en el `lifespan` |
| Checks | `make -C governance check` rc 0 (556 passed, 97,34 %); `make -C platform check` rc 0; `test_kind_profile.py` 6 passed; `--all` idéntico a la base |

## Hallazgos (candidatas)

- **F-01 · AMARILLO** · `service.rego` (`service-identity`): no fija `defaultMode: 292` ni la existencia del volumen; con 0400 el proceso 65532 no leería la llave y todo quedaría `pendiente_registro` en silencio.
- **F-02 · AMARILLO** · los `/token` de prueba no validan la firma de `client_assertion` (la cubre U0, `ServiceTokenProvider`).

Candidata fuera de alcance: U9 aún no tiene el Service `bias-monitoring-service`; confirmar el nombre de F25 cuando publique su chart (U09-T04).
