"""Los dobles de `world` (registro, governance y Pushgateway) detras de un socket real en `127.0.0.1` (U09-T04, CA-4).

`world.Registry`, `world.Governance` y `world.Pushgateway` hablan `httpx.Request`/`httpx.Response` (con `MockTransport`). Un contenedor no
puede usarlos asi: este puente recibe la solicitud HTTP, arma el `httpx.Request` (con el `timeout` de lectura que esos dobles esperan en
`extensions`) y devuelve la respuesta del doble tal cual. Asi la imagen real corre contra los mismos dobles que las pruebas de `run`.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx

Handle = Callable[[httpx.Request], Awaitable[httpx.Response]]
TIMEOUT = {"connect": 5.0, "read": 30.0, "write": 5.0, "pool": 5.0}


class Bridge:
    def __init__(self, handle: Handle) -> None:
        self.requests: list[tuple[str, str]] = []

        class Handler(BaseHTTPRequestHandler):
            def _serve(self) -> None:
                length = int(self.headers.get("content-length") or 0)
                body = self.rfile.read(length) if length else b""
                bridge.requests.append((self.command, self.path))
                request = httpx.Request(
                    self.command,
                    f"http://127.0.0.1:{bridge.port}{self.path}",
                    headers=dict(self.headers.items()),
                    content=body,
                    extensions={"timeout": TIMEOUT},
                )
                try:
                    response = asyncio.run(handle(request))
                except httpx.HTTPError:  # un doble «caido»: el cliente ve un 503
                    response = httpx.Response(503)
                payload = response.content
                self.send_response(response.status_code)
                for name in ("content-type",):
                    if name in response.headers:
                        self.send_header(name, response.headers[name])
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                if payload and response.status_code not in (204, 304):
                    self.wfile.write(payload)

            do_GET = do_POST = do_PUT = do_DELETE = _serve  # noqa: N815

            def log_message(self, *_: Any) -> None:
                return

        bridge = self
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> Bridge:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
