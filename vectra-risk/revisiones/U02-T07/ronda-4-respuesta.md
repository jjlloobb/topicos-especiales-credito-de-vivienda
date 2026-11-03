# Respuesta a la ronda 4 — U02-T07

F-09: Corregido en el commit de la ronda 5: `set.rego` regla `metadata-annotations`; ningún documento lleva `metadata.annotations`, igual que el render versionado. Comando: `uv run pytest identity-edge/tests/unit/test_keycloak_deploy.py -q -k metadata-annotations` (Skip en StatefulSet, PDB, keycloak-tls e identity-ca; PostSync con HookSucceeded en BackendTLSPolicy; helm.sh/hook test en el HPA; una anotación en un Service: todos fallan; 10 fallaban antes de la regla).
