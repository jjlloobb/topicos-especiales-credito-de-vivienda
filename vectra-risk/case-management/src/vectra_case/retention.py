"""Purga de `intake_keys` vencidas (P-5 de la enmienda, BR-U8-02). Sin CLI: la completa es del Paso 16.

Corre con el rol `case_retention`, el unico con `DELETE` sobre `intake_keys`; el plazo sale de `retention_settings`, nunca de un argumento.
"""

import psycopg

PURGE_INTAKE_KEYS = (
    "DELETE FROM intake_keys WHERE created_at < now() - "
    "make_interval(days => (SELECT intake_keys_days FROM retention_settings WHERE id = 1))"
)


def purge_intake_keys(conn: "psycopg.Connection[tuple[object, ...]]") -> int:
    """Borra las llaves con mas de `intake_keys_days` dias; devuelve cuantas."""
    with conn.transaction():
        cur = conn.execute(PURGE_INTAKE_KEYS)
        return cur.rowcount
