# U02-T05 — `realm-lint` acepta una credencial OTP referenciada

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-601
**Depende de:** U02-T03 (`realm-lint`), en `main`

Ajuste del Paso 3 del plan de U2, por la decisión D5 del usuario tras la ronda 1 de U02-T04 (2026-11-02). Los usuarios sintéticos de kind y staging traen su credencial OTP con la semilla desde ESO y no llevan la acción `CONFIGURE_TOTP` (domain-entities, tabla de usuarios por entorno, enmendada). Hoy `realm-lint` exige `CONFIGURE_TOTP` a todo usuario con MFA, así que rechazaría esos realms.

## Alcance

**Dentro:** que la regla de MFA de `realm-lint` (BR-U2-03, domain-entities §1.1) acepte, para un usuario que necesita MFA, **una de dos**: la acción requerida `CONFIGURE_TOTP`, o una credencial de tipo `otp` cuyo secreto sea una referencia exacta `$(env:NOMBRE)` (nunca un literal). Lo demás de la regla no cambia.

**Fuera:**
- Los realms `realm.{kind,staging,prod}.yaml` (U02-T04).
- Cualquier otra regla de `realm-lint`.
- Cambios en `contracts/`, `platform/` y `.github/workflows/`.

## Archivos de contexto

- `aidlc-docs/construction/identity-edge/functional-design/domain-entities.md` (§1.1 y la tabla de usuarios por entorno)
- `aidlc-docs/construction/identity-edge/functional-design/business-rules.md` (BR-U2-03)
- `identity-edge/tools/realm_lint.py` y `identity-edge/tests/` (de U02-T03)

## Criterios de aceptación

- [ ] **CA-1** — Un usuario con rol que exige MFA pasa con `CONFIGURE_TOTP` o con una credencial `otp` referenciada, y falla sin ninguna de las dos, con una credencial `otp` cuyo secreto es un literal o con una credencial de otro tipo. Lectura de vuelta: un caso por variante, parametrizado por kind, staging y prod.
  ```bash
  uv run pytest identity-edge/tests/unit/test_realm_lint.py -q -k otp_credential
  ```
  Esperado: pasa, con los casos de error y los válidos en los tres entornos.
- [ ] **CA-2** — Lo que ya cumplía `realm-lint` sigue cumpliendo.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests -q && uv sync --frozen && make -C identity-edge check
  ```
  Esperado: todo pasa y termina en 0.

- [ ] **CA-3** — La credencial OTP referenciada solo es válida con la forma única de domain-entities: `secretData` String JSON con `value` = `$(env:SYNTH_<USUARIO>_TOTP_SEED)` del propio usuario, y `credentialData` String JSON con `"secretEncoding":"BASE32"`. Lectura de vuelta: casos que fallan con `secretData` como mapa, con un `value` de primer nivel, con otra variable o la de otro usuario, sin `secretEncoding` o con otra codificación; con varias credenciales (`password` y `otp`), la regla mira la `otp` y no solo la primera; en kind, staging y prod.
  ```bash
  uv run pytest identity-edge/tests/unit/test_realm_lint.py -q -k otp_credential_form
  ```
  Esperado: pasa.

> **Enmienda del 2026-11-02 (orquestador, con aprobación del usuario, decisiones E1–E3):** se agrega CA-3 con la forma única de la credencial OTP que fija domain-entities.

- [ ] **CA-4** — `credentialData` exige exactamente `subType: totp`, `digits: 6`, `period: 30`, `algorithm: HmacSHA1` y `secretEncoding: BASE32`, y solo admite además `counter: 0`; `secretEncoding` fuera de `credentialData` o la semilla fuera de `secretData` fallan; un usuario sin `username` no tiene credencial válida. Lectura de vuelta: un caso por campo con otro valor, por clave extra, por campo en sitio equivocado y sin `username`, en kind, staging y prod.
  ```bash
  uv run pytest identity-edge/tests/unit/test_realm_lint.py -q -k otp_credential_data
  ```
  Esperado: pasa.

> **Enmienda del 2026-11-02 (orquestador, con aprobación del usuario, decisión E4):** se agrega CA-4.

## Plan de pruebas

**Rojo primero:** escribe los casos de CA-1 y registra que el caso válido con credencial `otp` referenciada falla con el validador actual.

## Notas

- Implementa lo que define el diseño enmendado. Si falta un dato, detente y repórtalo.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker** (el proyecto los deniega por configuración). El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
