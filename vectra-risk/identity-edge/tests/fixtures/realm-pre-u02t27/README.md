# Realm de kind anterior a U02-T27

`realm.kind.yaml` es una copia literal de `identity-edge/keycloak/realm/realm.kind.yaml` en el commit `524273a` (`origin/main` antes de U02-T27): un subflujo `vectra-mfa-<rol>` por rol, cada uno con su propia condicion de nivel 2 (`loa-mfa-<rol>`).

Con Keycloak 26.8.1 ese realm responde 500 al descubrimiento y rompe el login de quien vuelve a entrar con una sesion abierta (`IllegalStateException: Duplicate key 2`). Es el estado que puede tener hoy el Keycloak de kind del operador. Solo lo lee `tests/integration/test_realm_import.py` (migracion). No lo edites: si cambia, la prueba de migracion deja de medir lo que dice.
