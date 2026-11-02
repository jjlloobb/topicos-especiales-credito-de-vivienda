# Respuesta a la ronda 2 — U02-T05

F-01: Corregido en el commit de esta ronda: `BAD_FORMS` cubre `secretEncoding` dentro de `secretData`, la semilla dentro de `credentialData` y (prueba aparte) `secretEncoding` de primer nivel; N5 y N6 mueren (3 failed cada una) y N10 solo sobrevive como mutante equivalente, pues la clave extra `value` en `credentialData` ya la rechaza; su variante N10b muere (3 failed).
F-02: Corregido en el commit de esta ronda: `_has_referenced_otp` rechaza `username` ausente, no-String o vacío, y hay casos para cada uno; N11 muere (12 failed).
F-03: Corregido en el commit de esta ronda: `credentialData` debe ser exactamente los cinco campos (con su tipo) o esos más `counter: 0`; un caso por campo con otro valor, ausente, de otro tipo y por clave extra (`-k otp_credential_data`: 78 passed; `digits` 8 y otro algoritmo, 33 failed cada mutante).
