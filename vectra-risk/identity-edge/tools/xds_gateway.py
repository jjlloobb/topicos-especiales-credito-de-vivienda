"""Traduccion offline de `gateway/generated/<env>/` a xDS con `egctl` (U02-T10, Paso 8 de U2).

`egctl x translate -f` acepta un archivo (o `-` por stdin), no un directorio, asi que se concatenan los documentos del entorno
con lo que el clúster pondria y `generated/` no versiona: el Secret TLS que escribe cert-manager (un certificado desechable,
generado con `openssl` en un directorio temporal) y los Services de los destinos de telemetria. Con `--add-missing-resources`
egctl agrega los Services de las rutas. Nada de esto toca un clúster.

`main` traduce los tres entornos, deja la salida en `identity-edge/.tools/xds/<env>.yaml` (no se versiona) y termina distinto de 0
si egctl falla o alguna politica, ruta, Gateway o EnvoyProxy queda con una condicion en `False`.
"""

import argparse
import base64
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

EDGE = Path(__file__).resolve().parents[1]
ROOT = EDGE.parent
GENERATED = EDGE / "gateway" / "generated"
EGCTL = ROOT / "platform" / ".tools" / "bin" / "egctl"
OUT = EDGE / ".tools" / "xds"
ENVS = ("kind", "staging", "prod")
# egctl solo conoce Gateway API y Envoy Gateway: el Certificate (cert-manager) y el ExternalSecret no entran en la traduccion.
OTHER_OPERATORS = {"Certificate", "ExternalSecret"}

Docs = list[dict[str, Any]]


class TranslateError(RuntimeError):
    """egctl fallo o no hay con que traducir."""


def load_dir(directory: Path) -> Docs:
    docs: Docs = []
    for path in sorted(directory.glob("*.yaml")):
        docs += [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
    return docs


def _certificate(hostname: str) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        key, crt = Path(tmp) / "tls.key", Path(tmp) / "tls.crt"
        run = subprocess.run(  # noqa: S603 - openssl del sistema, argumentos fijos
            [  # noqa: S607
                "openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
                "-keyout", str(key), "-out", str(crt), "-subj", f"/CN={hostname}", "-days", "1", "-addext", f"subjectAltName=DNS:{hostname}",
            ],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        if run.returncode != 0:
            raise TranslateError(f"openssl fallo: {run.stderr.strip()}")
        encode = lambda p: base64.b64encode(p.read_bytes()).decode()  # noqa: E731
        return encode(crt), encode(key)


def stub_documents(docs: Docs) -> Docs:
    """El Secret de cada `certificateRef` de los Gateway y el Service de cada destino de tracing de los EnvoyProxy."""
    stubs: Docs = []
    for gateway in (d for d in docs if d["kind"] == "Gateway"):
        namespace = gateway["metadata"]["namespace"]
        for listener in gateway["spec"]["listeners"]:
            for ref in listener.get("tls", {}).get("certificateRefs", []):
                crt, key = _certificate(listener["hostname"])
                stubs.append(
                    {
                        "apiVersion": "v1",
                        "kind": "Secret",
                        "type": "kubernetes.io/tls",
                        "metadata": {"name": ref["name"], "namespace": ref.get("namespace", namespace)},
                        "data": {"tls.crt": crt, "tls.key": key},
                    }
                )
    for proxy in (d for d in docs if d["kind"] == "EnvoyProxy"):
        tracing = proxy["spec"].get("telemetry", {}).get("tracing")
        for ref in (tracing or {}).get("provider", {}).get("backendRefs", []):
            stubs.append(
                {
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {"name": ref["name"], "namespace": ref.get("namespace", proxy["metadata"]["namespace"])},
                    "spec": {"ports": [{"port": ref["port"], "protocol": "TCP"}], "clusterIP": "10.0.0.9"},
                }
            )
    return stubs


def translate(docs: Docs, egctl: Path = EGCTL) -> dict[str, Any]:
    """`egctl x translate --from gateway-api --to gateway-api,xds` sobre `docs` mas los documentos de apoyo."""
    if not egctl.exists():
        raise TranslateError(f"falta {egctl}: corre platform/install-tools.sh")
    text = yaml.safe_dump_all([*(d for d in docs if d["kind"] not in OTHER_OPERATORS), *stub_documents(docs)], sort_keys=False)
    run = subprocess.run(  # noqa: S603 - herramienta fija de platform/.tools
        [str(egctl), "x", "translate", "--from", "gateway-api", "--to", "gateway-api,xds", "--add-missing-resources", "-f", "-", "-o", "yaml"],
        input=text, capture_output=True, text=True, check=False,
    )  # fmt: skip
    if run.returncode != 0:
        raise TranslateError(f"egctl fallo ({run.returncode}): {run.stderr.strip()}")
    result = yaml.safe_load(run.stdout)
    if not isinstance(result, dict) or not result.get("xds"):
        raise TranslateError("egctl no devolvio xDS")
    return result


def conditions(result: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(`Kind nombre`, ancestro/padre, condicion) de todo lo que egctl devuelve en `--to gateway-api`."""
    found = []
    for key, value in result.items():
        if key == "xds":
            continue
        for obj in value if isinstance(value, list) else [value]:
            if not isinstance(obj, dict) or "status" not in obj:
                continue
            who = f"{obj.get('kind', key)} {obj['metadata']['name']}"
            status = obj["status"]
            for cond in status.get("conditions", []):
                found.append((who, "", cond))
            for group in ("ancestors", "parents"):
                for entry in status.get(group, []):
                    for cond in entry.get("conditions", []):
                        found.append((who, entry.get("ancestorRef", entry.get("parentRef", {})).get("name", ""), cond))
            for listener in status.get("listeners", []):
                for cond in listener.get("conditions", []):
                    found.append((who, listener.get("name", ""), cond))
    return found


def not_accepted(result: dict[str, Any]) -> list[str]:
    """Las condiciones en `False`: una politica que no se acepta (`Conflicted`, `Invalid`...) no llega al xDS."""
    return [f"{who} {parent}: {c['type']}={c['status']} ({c.get('reason')}: {c.get('message', '')})" for who, parent, c in conditions(result) if c["status"] != "True"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    failed = False
    for env in ENVS:
        try:
            result = translate(load_dir(GENERATED / env))
        except TranslateError as error:
            print(f"xds_gateway: {env}: {error}", file=sys.stderr)  # noqa: T201
            failed = True
            continue
        (args.out / f"{env}.yaml").write_text(yaml.safe_dump(result, sort_keys=True), encoding="utf-8")
        bad = not_accepted(result)
        for line in bad:
            print(f"xds_gateway: {env}: {line}", file=sys.stderr)  # noqa: T201
        failed = failed or bool(bad)
        print(f"xds_gateway: {env}: {len(conditions(result))} condiciones, {len(bad)} sin aceptar, xDS en {args.out / (env + '.yaml')}")  # noqa: T201
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
