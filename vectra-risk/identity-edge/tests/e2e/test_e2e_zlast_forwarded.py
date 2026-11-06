"""`X-Forwarded-For` falso (NFR-U2-23, BR-U2-10): la IP registrada y el contador de `/auth`. Se ejecutan en el Paso 16, al final.

Último archivo del orden alfabético: el contador de `/auth/**` queda saturado un minuto y los logins de otras pruebas fallarían.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor

import e2e_support as support
import gateway_design as gd
import httpx

FORGED_IP = "203.0.113.77"  # TEST-NET-3
LOGIN_URL = f"{support.OIDC}/auth"
OVERSHOOT = 20  # solicitudes de más sobre el límite, para ver el 429


def test_forged_x_forwarded_for_does_not_change_the_logged_ip(gateway: httpx.Client, loki: support.Loki) -> None:
    """H6: `client_ip` del access log del gateway, en Loki, no es la que dice la cabecera falsa."""
    since = time.time_ns() - 1_000_000_000
    for _ in range(3):
        gateway.get(f"{support.REALM_PATH}/.well-known/openid-configuration", headers={"X-Forwarded-For": FORGED_IP})
    query = f'{support.GATEWAY_STREAM} | json | route_name =~ ".*auth.*" | client_ip != ""'
    lines = loki.wait_for(query, since)
    assert lines, "Loki no tiene líneas del access log del gateway para la ruta de /auth"
    ips = {json.loads(line)["client_ip"] for line in lines if line.lstrip().startswith("{")}
    assert ips, lines[:3]
    assert FORGED_IP not in ips, f"el access log registró la IP falsa: {ips}"


def test_forged_x_forwarded_for_does_not_change_the_auth_counter(gateway: httpx.Client) -> None:
    """Con una IP falsa distinta en cada solicitud, el contador por IP de `/auth/**` sigue contando la de origen (NFR-U2-23).

    El contador es de ventana fija alineada a la unidad (`routes.yaml`): se arranca al comienzo de una ventana y la ráfaga
    entera cabe en su primera mitad, así que no depende del segundo en que empiece la prueba (F-04).
    """
    limit = gd.rate_limit_numbers()["auth"]
    assert limit == support.rate_limit("auth-login")["requests"]
    window = support.window_seconds("auth-login")
    wanted = gd.retry_after()["auth"]
    total = limit + OVERSHOOT
    pace = -(-total // (window // 2))  # solicitudes por segundo para enviar todas en la primera mitad de la ventana
    assert pace < gd.rate_limit_numbers()["global"], "el ritmo de la prueba supera el límite global"
    statuses: list[tuple[int, str | None]] = []

    def call(n: int) -> tuple[int, str | None]:
        reply = gateway.get(LOGIN_URL, headers={"X-Forwarded-For": f"198.51.100.{n % 250 + 1}"})
        return reply.status_code, reply.headers.get("retry-after")

    support.wait_for_next_window("auth-login")
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=pace) as pool:
        for second in range(0, total, pace):
            statuses += list(pool.map(call, range(second, min(second + pace, total))))
            time.sleep(max(0.0, (second // pace + 1) - (time.monotonic() - started)))
    assert time.monotonic() - started < window, "la ráfaga no cupo en una ventana: la prueba no es concluyente"
    limited = [retry for status, retry in statuses if status == 429]
    assert limited, f"{total} solicitudes con IP falsas distintas no llegaron a 429 (límite {limit} por ventana y por IP de origen)"
    assert set(limited) == {wanted}
    time.sleep(window + 1)  # deja la ventana libre para quien corra después
