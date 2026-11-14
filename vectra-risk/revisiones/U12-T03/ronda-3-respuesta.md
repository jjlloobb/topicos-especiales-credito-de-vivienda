# U12-T03 — respuesta a la ronda 2 (ronda 3 acotada)

- F-11: Corregido en d689d2f: `count_bias_runs` toma como referencia la primera marca >= `floor(recorded_at)` (U9 publica `int(finished_at)`, `publish.py:133`); el doble `rt2_world` publica el entero truncado a milisegundos del `freeze`. Pruebas: `test_rt2_bias_counting_uses_the_truncated_second_...`, `test_rt2_f11_the_run_that_froze_plus_two_is_not_enough` y `..._plus_three_passes` (mismo segundo y cruza al siguiente). Rojo previo en 9da11c1/bitácora: `solo 1 de 3` y 22 corridas correctas que daban 4; verde: 165 passed. `_no_recongela` comparte la función: solo cambia la referencia truncada, su cuenta no.
- F-12: Corregido en d689d2f: `RT2-LATENCY` da `rt2_latencia_sin_freeze` solo si la fase `freeze` quedó en `rt2_freeze_ausente`; prueba `test_rt2_f12_a_403_in_the_freeze_phase_...` (rojo: `('rt2_latencia_sin_freeze',) != ('rt2_latencia_sin_freeze',)` sin el arreglo).
- F-13: Fuera de alcance: `CANDIDATAS.md` por el arbitraje (no lo toqué).
- F-14: Fuera de alcance: `CANDIDATAS.md` por el arbitraje.
- F-15: Fuera de alcance: `CANDIDATAS.md`, destino U12-T06, por el arbitraje; `_no_recongela` sin cambios salvo la referencia truncada compartida.
