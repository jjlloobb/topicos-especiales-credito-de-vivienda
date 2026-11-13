# Realm de kind anterior a U02-T22

`realm.kind.yaml` es una copia literal de `identity-edge/keycloak/realm/realm.kind.yaml` en el commit `23e8d73dacd6f9994e99ce1e6c7a2d275477e42b` (`origin/main` antes de U02-T22), con alias de `authenticatorConfig` compartidos y sin `VERIFY_PROFILE`.

Es el estado que puede tener hoy el Keycloak de kind del operador. Solo lo lee `tests/integration/test_realm_import.py` (migracion, CA-8). No lo edites: si cambia, la prueba de migracion deja de medir lo que dice.
