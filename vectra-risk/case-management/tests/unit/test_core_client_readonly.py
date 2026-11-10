"""El cliente del core solo hace `GET` (Paso 1; NFR-U8-43, BR-U8-22, US-603).

Guardia estatica con `ast` sobre `vectra_case/credit.py`. Hoy el modulo esta vacio y la prueba pasa; el cliente real es del Paso 12
(U08-T03) y la guardia le impide escribir contra el core. Las pruebas de `violations` muestran que la guardia detecta cada forma.
"""

import ast
from pathlib import Path

import pytest

CREDIT = Path(__file__).resolve().parents[2] / "src" / "vectra_case" / "credit.py"
WRITE_METHODS = {"post", "put", "patch", "delete", "head", "options", "trace", "connect"}
HTTP_METHODS = {m.upper() for m in WRITE_METHODS} | {"GET", "REQUEST"}


def _string_args(call: ast.Call) -> list[tuple[str | None, str]]:
    """Los literales de texto pasados a la llamada, con el nombre del argumento por palabra clave (si lo hay)."""
    found: list[tuple[str | None, str]] = []
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            found.append((None, arg.value))
    for kw in call.keywords:
        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            found.append((kw.arg, kw.value.value))
    return found


def violations(source: str) -> list[str]:
    """Llamadas del modulo que no son `GET`: metodos de escritura, `request` con otro metodo o literales de metodo."""
    problems: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if name.lower() in WRITE_METHODS:
            problems.append(f"linea {node.lineno}: llamada al metodo {name}")
        literals = _string_args(node)
        if name == "request":
            # `client.request(method, url)`: el primer literal (o `method=`) debe ser GET.
            method = next((v for k, v in literals if k in (None, "method")), None)
            if method is None or method.upper() != "GET":
                problems.append(f"linea {node.lineno}: request con un metodo que no es GET ({method!r})")
        for key, value in literals:
            if value.upper() in HTTP_METHODS - {"GET", "REQUEST"} and (
                name == "call" or key in ("method", "http_method") or value.isupper()
            ):
                problems.append(f"linea {node.lineno}: literal de metodo {value} en {name or 'una llamada'}")
    return problems


def test_credit_client_has_no_method_other_than_get() -> None:
    assert CREDIT.is_file()
    assert violations(CREDIT.read_text()) == []


@pytest.mark.parametrize(
    "source",
    [
        "client.post('/v1/credits')",
        "await client.put('/v1/credits/1', json={})",
        "client.patch('/v1/credits/1')",
        "await client.delete('/v1/credits/1')",
        "client.request('POST', '/v1/credits')",
        "client.request(method='DELETE', url='/v1/credits')",
        "client.request()",
        "await deps.call(breaker, 'POST', url)",
        "deps.call(breaker, method='PUT', url=url)",
    ],
)
def test_guard_rejects_every_write_form(source: str) -> None:
    assert violations(source), source


@pytest.mark.parametrize(
    "source",
    [
        "client.get('/v1/credits/1')",
        "client.request('GET', '/v1/credits/1')",
        "deps.call(breaker, 'GET', url)",
        "deps.call(breaker, method='GET', url=url)",
        "answer = {'status': 'post'}",
    ],
)
def test_guard_accepts_get(source: str) -> None:
    assert violations(source) == [], source
