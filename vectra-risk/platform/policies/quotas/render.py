#!/usr/bin/env python3
"""Genera ResourceQuota y LimitRange desde `quotas.yaml` (NFR-U1-13). Sin cifras a mano en los manifiestos.

`--check` falla si `generated.yaml` no corresponde a `quotas.yaml`, sin escribirlo.
"""

import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent


def render() -> str:
    data = yaml.safe_load((HERE / "quotas.yaml").read_text(encoding="utf-8"))
    documents = []
    limits = data["limit_range"]
    for ns, config in data["namespaces"].items():
        parts = config["contributions"].values()
        requests = [round(sum(p["requests"][i] for p in parts), 2) for i in (0, 1)]
        maxima = [round(sum(p["limits"][i] for p in parts), 2) for i in (0, 1)]
        documents.append(
            {
                "apiVersion": "v1",
                "kind": "ResourceQuota",
                "metadata": {"name": "vectra-quota", "namespace": ns},
                "spec": {
                    "hard": {
                        "requests.cpu": str(requests[0]),
                        "requests.memory": f"{requests[1]}Gi",
                        "limits.cpu": str(maxima[0]),
                        "limits.memory": f"{maxima[1]}Gi",
                    }
                },
            }
        )
        documents.append(
            {
                "apiVersion": "v1",
                "kind": "LimitRange",
                "metadata": {"name": "vectra-defaults", "namespace": ns},
                "spec": {
                    "limits": [
                        {
                            "type": "Container",
                            "default": {"cpu": limits["default_cpu"], "memory": limits["default_memory"]},
                            "defaultRequest": {"cpu": limits["request_cpu"], "memory": limits["request_memory"]},
                        }
                    ]
                },
            }
        )
    return "---\n".join(yaml.safe_dump(d, sort_keys=True) for d in documents)


def main(argv: list[str]) -> int:
    target = HERE / "generated.yaml"
    if "--check" in argv:
        if not target.is_file() or target.read_text(encoding="utf-8") != render():
            print(f"{target.name} difiere de quotas.yaml: corre render.py")
            return 1
        return 0
    target.write_text(render(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
