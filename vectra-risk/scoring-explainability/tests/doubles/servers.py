"""Un servidor HTTP real (uvicorn en un hilo) para las pruebas que necesitan sockets: limite de conexiones y apagado."""

import threading
import time
from typing import Any

import uvicorn


class Server:
    def __init__(self, app: Any) -> None:
        self._server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error", lifespan="off")
        )
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self) -> "Server":
        self._thread.start()
        deadline = time.monotonic() + 10
        while not self._server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("el servidor de prueba no arranco")
            time.sleep(0.01)
        return self

    @property
    def url(self) -> str:
        port = self._server.servers[0].sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10)
