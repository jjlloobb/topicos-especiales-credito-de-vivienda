"""Backend de eco de kind (U02-T14, H1). Solo biblioteca estandar.

Responde 200 a cualquier metodo y camino, con un JSON que lleva las cabeceras tal como llegaron (nombre y valor, sin tocarlas),
el metodo, el camino y el tamano del cuerpo recibido. Las pruebas e2e leen de ahi lo que el gateway deja pasar o quita (P-U2-06).
No fija ninguna cabecera de seguridad: las del perfil `spa` y `api` las pone el gateway, y es lo que las pruebas observan.

Modo de error (U02-T19, B-4, P-U2-02; solo kind): una peticion con la cabecera `X-Echo-Fail: 503` recibe 503 en vez de 200. Toda peticion
con la cabecera `X-Echo-Key: <clave>` suma una llamada al contador de esa clave (sin la cabecera, la clave es el camino). El contador se lee
en `GET /__echo/calls?key=<clave>` -> `{"key": ..., "calls": n}` y se pone en 0 con `DELETE /__echo/calls?key=<clave>`; esas dos llamadas no
cuentan. Cada replica lleva su propio contador: quien prueba suma las de todas.
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

CHUNK = 64 * 1024
FAIL_HEADER = "X-Echo-Fail"
KEY_HEADER = "X-Echo-Key"
CALLS_PATH = "/__echo/calls"
FAIL_STATUS = 503

_calls: dict[str, int] = {}
_lock = threading.Lock()


def count_call(key: str) -> int:
    with _lock:
        _calls[key] = _calls.get(key, 0) + 1
        return _calls[key]


def _raw(value: str) -> str:
    """`http.server` decodifica las cabeceras como latin-1; se devuelven los bytes que llegaron, leidos como UTF-8."""
    return value.encode("latin-1").decode("utf-8", errors="backslashreplace")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "echo"
    sys_version = ""

    def _read_body_size(self) -> int:
        """Cuenta los bytes del cuerpo sin guardarlos."""
        remaining = int(self.headers.get("Content-Length") or 0)
        total = 0
        while remaining > 0:
            chunk = self.rfile.read(min(CHUNK, remaining))
            if not chunk:
                break
            total += len(chunk)
            remaining -= len(chunk)
        return total

    def _counter(self) -> None:
        """`GET` lee y `DELETE` pone en 0 el contador de `?key=`; no cuentan como llamada."""
        key = (parse_qs(urlsplit(self.path).query).get("key") or [""])[0]
        with _lock:
            if self.command == "DELETE":
                _calls.pop(key, None)
            calls = _calls.get(key, 0)
        payload = json.dumps({"key": key, "calls": calls}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _echo(self) -> None:
        if urlsplit(self.path).path == CALLS_PATH and self.command in {"GET", "DELETE"}:
            self._counter()
            return
        total = self._read_body_size()
        count_call(self.headers.get(KEY_HEADER) or urlsplit(self.path).path)
        status = FAIL_STATUS if self.headers.get(FAIL_HEADER) == str(FAIL_STATUS) else 200
        payload = json.dumps(
            {
                "method": self.command,
                "path": self.path,
                "headers": [[name, _raw(value)] for name, value in self.headers.items()],
                "body_bytes": total,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = _echo

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - firma de la clase base
        """Sin registro de acceso: el eco no escribe nada de lo que recibe."""


def make_server(host: str = "0.0.0.0", port: int = 8080) -> ThreadingHTTPServer:  # noqa: S104 - el pod escucha en todas las interfaces
    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    make_server(port=int(os.environ.get("PORT", "8080"))).serve_forever()
