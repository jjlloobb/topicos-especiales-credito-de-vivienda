"""Datos para `conftest` sobre el render de los charts de U10 (Paso 18): el entorno y el cliente publico `vectra-console` del realm de U2.

`conftest` no lee el realm. Este script lo lee (`identity-edge/keycloak/realm/realm.<env>.yaml`), sustituye `$(env:PUBLIC_HOSTNAME)` por `vectra.publicHostname` de
`identity-edge/keycloak/values/<env>.yaml` y escribe el JSON que se pasa con `--data`: `{"env": ..., "realm": {"client_id": ..., "redirect_uris": [...]}}`. No se versiona
(el target `policy-chart` lo genera cada vez), para que el valor esperado no se copie a mano.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
CLIENT = "vectra-console"
PLACEHOLDER = "$(env:PUBLIC_HOSTNAME)"


def realm_data(env: str, root: Path = ROOT) -> dict[str, Any]:
    realm = yaml.safe_load(
        (root / f"identity-edge/keycloak/realm/realm.{env}.yaml").read_text(encoding="utf-8")
    )
    values = yaml.safe_load((root / f"identity-edge/keycloak/values/{env}.yaml").read_text(encoding="utf-8"))
    hostname = values["vectra"]["publicHostname"]
    clients = [c for c in realm["clients"] if c["clientId"] == CLIENT]
    if len(clients) != 1 or clients[0].get("publicClient") is not True:
        raise SystemExit(f"realm.{env}.yaml: se esperaba un solo cliente publico {CLIENT}")
    uris = [uri.replace(PLACEHOLDER, hostname) for uri in clients[0]["redirectUris"]]
    return {"env": env, "realm": {"client_id": CLIENT, "redirect_uris": uris}}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, choices=("kind", "staging", "prod"))
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(realm_data(args.env), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
