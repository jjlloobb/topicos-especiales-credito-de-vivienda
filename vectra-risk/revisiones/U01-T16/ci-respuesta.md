# U01-T16 — respuesta a la CI del PR #195

CI-01: Corregido en el commit de este archivo: las dos pruebas de `main()` de `test_identity_seed.py` ejecutaban `kubectl` real (y leían el clúster de la máquina); ahora inyectan un clúster falso, `Vault` y `ca_from_cluster` buscan el ejecutor al llamar, y `platform/kind/tests/conftest.py` trae una salvaguarda `autouse` que hace fallar con mensaje claro cualquier prueba que lo intente (con su prueba). `KUBECONFIG=/nonexistent` y sin `kubectl` en el PATH: 1021 passed.
