# Ronda 1 — U04-T05b

VEREDICTO: NO-VERDE

Revisor, 2026-11-10, punta `8b760fd`, base `b0724ee`. El revisor entregó el informe en su respuesta; el orquestador lo transcribe.

## Criterios (corridos por el revisor)

| # | Resultado |
|---|---|
| CA-1 | 17 passed (git, `ssh-keygen` y `helm template` reales); el `grep` negativo sale en 0. Además, `promote` + `edit` sobre los values reales de kind, staging y prod con `helm template -f envs/<env>/values.yaml`: rc 0, `isvc-8a98ab02` con `storageUri=s3://model-store/mv-2026-01-01-8a98ab02/` |
| CA-2 | 53 passed. Con el modelo entrenado con `encode`: U5 0,875698, Job 0,8757. Con el base real: U5 0,908666, Job 0,9087. Rojo con el `features.py` de la base: fallan 2 (matriz con -1; AUC 0,8757 frente a 0,8898). Mutaciones de `confidence` (fallan 2) y de canal (falla 1) |
| CA-3 | `make -C governance check` rc 0 (335 passed); `make -C platform check` rc 0 |
| CA-4 | Paso 12 `[x] (U04-T05b, acotado a la demo)` |
| `--all` | sin fallos nuevos; NFR-U4-20 y 21 trazados |

Mutaciones de `promotion-tool`: sin `-S` (fallan 2), segundo commit (fallan 5), token en `~/.config` (falla 1), `has_entry` siempre verdadero (falla 1), `storage_uri` cambiado (fallan 3).

## Hallazgos

- **F-01 · NARANJA, rompe el flujo base** · `governance/promotion_tool/vectra_promotion/login.py:57`: el `redirect_uri` es `http://127.0.0.1:{port}/callback`. El diseño de U2 (`aidlc-docs/construction/identity-edge/functional-design/domain-entities.md:67`) fija `http://127.0.0.1:{puerto}` sin ruta, y el realm (`identity-edge/keycloak/realm/realm.kind.yaml:957-958`) registra `http://127.0.0.1`. Keycloak ignora el puerto en loopback (RFC 8252 §7.3) pero compara la ruta exacta → `Invalid parameter: redirect_uri`. Sin login no hay `list_promotable` ni `mark_active` (F08 exige `azp=promotion-tool`), y U04-T07 activa el modelo de referencia con `promotion-tool`. El doble del IdP acepta cualquier `http://127.0.0.1:`. No verificado contra un Keycloak real (sin clúster). La candidata del codificador lo atribuye al puerto y a U2; es la ruta, y es de U4.
- **F-02 · NARANJA (candidata)** · `values.py:104,114`: un comentario en la columna 0 dentro de la lista `inferenceServices` termina el bloque y duplica entradas en el YAML del PR. Hoy los values reales no tienen comentarios ahí.
- **F-03 · NARANJA (candidata)** · `governance/pyproject.toml`: `vectra_promotion` importa `yaml` sin declarar `pyyaml`; funciona porque otros miembros del workspace lo traen.
- **F-04 · AMARILLO** · `commands.py:45`: el recorte a 500 puede cortar el sufijo `[inference_service=...]`; 500 repetido como literal.
- **F-05 · AMARILLO** · `gitops.py:112-125`: si `git commit -S` falla, el `finally` vuelve a la rama original con el archivo en stage; la rama sale del `main` local, no de `origin/main`.

## Juicio sobre las preguntas del orquestador

1. `promotion-tool` cumple: un commit firmado, sin token en disco, no sincroniza ni aplica, `storageUri = dirname(manifest_uri)+"/"` como `api.py:243`, sin campos inventados, `mark_active` se niega si la versión no está en `prod`, sin `retire_inference_service`.
2. AUC: las cifras 0,863/0,848 eran del modelo del revisor de U04-T05; la prueba con el fixture `encode` muerde el defecto; la del base real es regresión. Aceptado.
3. Gateway (U2): F08 solo publica `GET /v1/models?state=aprobado` y `POST …/activation`; no rompe el rollback (el estado `inactive` está en los values y governance valida la transición) y ninguna de las cuatro demos usa rollback. El `redirectUri` sí es un problema: F-01.
