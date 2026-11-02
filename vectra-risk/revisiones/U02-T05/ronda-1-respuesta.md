# Respuesta a la ronda 1 — U02-T05

F-01: Corregido en el commit de esta ronda: se implementa la forma única de domain-entities §3 (`secretData` String JSON con `value` = `$(env:SYNTH_<USUARIO>_TOTP_SEED)` del propio usuario; `credentialData` String JSON con `"secretEncoding":"BASE32"`); cualquier otra forma falla (CA-3, `-k otp_credential_form`: 78 passed).
F-02: Corregido en el commit de esta ronda: casos del `value` de primer nivel y de varias credenciales (`password`+`otp`, `otp`+`password`, otp mala y luego buena); las mutaciones «solo la primera credencial» (3 failed) y «`value` de primer nivel» (3 failed) ahora mueren.
F-03: Corregido en el commit de esta ronda: las pruebas usan `SYNTH_<USUARIO>_TOTP_SEED` y el lint exige el nombre del propio usuario (mutación «ignorar variable propia»: 36 failed).
F-04: Corregido en el commit de esta ronda: el rojo con las pruebas reales de c1e6c98 contra la base 2dbe403 es 12 failed, 189 passed, 170 deselected (bitácora, Ronda 2).
