"""El mundo real de la CLI (U12-T04): la implementacion de `cli.Backend` que usa la herramienta. La bóveda por `VAULT_ADDR`/`VAULT_TOKEN`, el login OIDC por el gateway, `kubectl` (solo lectura) y `port-forward` a pods.

Se importa **solo al ejecutar una seccion**, nunca al cargar `cli` ni con `--help`. Lo que aqui se construye no hace nada hasta que una seccion lo pide: ninguna solicitud sale en el constructor, salvo la lectura de la bóveda
que `Credentials` hace al pedir la primera credencial. `tests/unit/test_live.py` prueba el armado sin cluster (con dobles de la bóveda y de `kubectl`, via `runner=` y `vault_transport=`); el recorrido contra kind lo hace U12-T06.

Ninguna ruta del repositorio va escrita aqui (la demo corre en otra maquina y desde una imagen, sin un clon en una ruta fija): la entrega de U5 llega por `--delivery` o por el manifiesto (`prepare --delivery`).
"""

from __future__ import annotations

import argparse
import ssl
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx

from vectra_verification.clients._api import RunTag
from vectra_verification.clients.bff import BffClient
from vectra_verification.clients.gateway import GatewayClient
from vectra_verification.clients.k8s_read import K8sRead, Runner, SubprocessRunner
from vectra_verification.clients.oidc import OidcClient
from vectra_verification.clients.prom import PromClient
from vectra_verification.clients.registry import RegistryClient
from vectra_verification.clock import Clock
from vectra_verification.credentials import Credentials
from vectra_verification.driver import ANALYSTS, DEMO_MIX, Driver
from vectra_verification.guard import Environment
from vectra_verification.scenarios.common import Sessions
from vectra_verification.simulator import Simulator, SimulatorError, read_delivery

DEFAULT_CONTEXT = "kind-vectra"
TOTP_WINDOWS: dict[
    str, int
] = {}  # F-09: la ventana TOTP de cada usuario es una por proceso: la comparten todos los `OidcClient` (uno por seccion en `all`), o un login nuevo reusaria un codigo ya gastado
REGISTRY_SCOPES = ("registry:read:metrics", "registry:read:monitoring")


class LazySimulator:
    """El simulador se arma al **primer uso**: las secciones que no envian solicitudes (`rt5`, `rt2-setup`, `u11`) no necesitan la entrega de U5, y una entrega que falta es un prerrequisito de quien la usa."""

    def __init__(self, build: Callable[[], Simulator]) -> None:
        self._build = build
        self._simulator: Simulator | None = None

    def _get(self) -> Simulator:
        if self._simulator is None:
            self._simulator = self._build()
        return self._simulator

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get(), name)


class LiveBackend:
    def __init__(
        self,
        environment: Environment,
        args: argparse.Namespace,
        clock: Clock,
        prefix: str,
        environ: Mapping[str, str],
        *,
        runner: Runner | None = None,
        vault_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._environment, self._args, self._clock, self._prefix = environment, args, clock, prefix
        self._credentials = Credentials.from_environ(environment, environ, vault_transport)
        ca = Path(args.ca_file) if getattr(args, "ca_file", None) else None
        self._verify: ssl.SSLContext | bool = ssl.create_default_context(cafile=str(ca)) if ca else True
        self._oidc = OidcClient(environment, self._credentials, clock, ca_file=ca, totp_windows=TOTP_WINDOWS)
        self._k8s = K8sRead(
            runner or SubprocessRunner(), context=environ.get("KUBE_CONTEXT", DEFAULT_CONTEXT)
        )
        self._sessions: Sessions | None = None

    def secret_values(self) -> frozenset[str]:
        return self._credentials.secret_values()

    def k8s(self) -> K8sRead:
        return self._k8s

    def prom(self) -> AbstractContextManager[PromClient]:
        return PromClient.through_port_forward(self._k8s)

    def registry(self) -> AbstractContextManager[RegistryClient]:
        reader = self._oidc.service_session("verification-reader", REGISTRY_SCOPES)
        return RegistryClient.through_port_forward(self._k8s, reader.bearer)

    def sessions(self) -> Sessions:
        if self._sessions is None:
            self._sessions = Sessions(
                self._environment,
                self._oidc,
                self._clock,
                RunTag(str(self._args.section), self._prefix),
                verify=self._verify,
            )
        return self._sessions

    def bff(self) -> BffClient:
        return self.sessions().reader("analista-1")

    def simulator(self, run_prefix: str) -> Any:
        return LazySimulator(lambda: self._build_simulator(run_prefix))

    def _build_simulator(self, run_prefix: str) -> Simulator:
        delivery = getattr(self._args, "delivery", None)
        if not delivery:
            raise SimulatorError(
                "u5_delivery_missing: pasa --delivery o dilo en `prepare --delivery` (la entrega de U5, con datasets/test.parquet)"
            )
        population = read_delivery(Path(delivery), self._clock.now())
        scenario = "stratified" if self._args.section == "rt2" else "normal"
        session = self._oidc.service_session("channel-simulator", ("intake:submit",))
        gateway = GatewayClient(
            self._environment, session.bearer, RunTag(scenario, run_prefix), verify=self._verify
        )
        return Simulator(self._environment, gateway, self._clock, population, run_prefix)

    def driver(self, seed: int) -> Driver:
        sessions = {user: self._oidc.login(user) for user in ANALYSTS}
        transport = httpx.HTTPTransport(verify=self._verify)
        return Driver(
            self._environment,
            dict(sessions),
            RunTag("decisions", self._prefix),
            self._clock,
            replace(DEMO_MIX, seed=seed),
            transport=transport,
        )

    def close(self) -> None:
        self._oidc.close()


def live_backend(
    environment: Environment, args: argparse.Namespace, clock: Clock, prefix: str, environ: Mapping[str, str]
) -> LiveBackend:
    return LiveBackend(environment, args, clock, prefix, environ)


__all__ = ["LiveBackend", "live_backend"]
