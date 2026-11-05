Copia de los `realm.{kind,staging,prod}.yaml` en 8c18021 (antes de U02-T14). La usa
`test_realm_files.py::test_the_realms_only_differ_from_the_baseline_in_the_declared_fields` para fijar que U02-T14 solo
toca `bruteForceStrategy`, `maxTemporaryLockouts` y la acción requerida `UPDATE_PASSWORD`. No se edita: si otra tarea
cambia un realm a propósito, se amplía la lista de diferencias declaradas en esa prueba.
