F-01: Corregido en 2340030: pruebas de esperas, tiempo agotado al conectar, conexion rechazada (simulada y real) y mensaje completo; M1, M2, M3, M5 y M10 mueren al re-correrlos.
F-02: Corregido en 2340030: `ensure_folder` tolera 409 en POST /api/folders; supuesto no verificado: que el Grafana real devuelva 409 ante UID duplicado.
F-03: Corregido en 2340030: fixture `fast_timeouts` ya no es autouse y sin `raising=False`.
F-04: Corregido en 2340030: bucle `while` sin AssertionError inalcanzable y sin `fast_client`.
