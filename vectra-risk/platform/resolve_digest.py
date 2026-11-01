#!/usr/bin/env python3
"""Imprime el digest de una imagen consultando su registro de forma anonima. No descarga la imagen."""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)


def parse(image: str) -> tuple[str, str, str]:
    name, _, tag = image.partition(":") if ":" in image.split("/")[-1] else (image, "", "latest")
    if ":" in image.split("/")[-1]:
        name, tag = image.rsplit(":", 1)
    first = name.split("/")[0]
    if "." in first or ":" in first:
        registry, repository = first, name[len(first) + 1 :]
    else:
        registry, repository = "docker.io", name
    if registry == "docker.io":
        registry = "registry-1.docker.io"
        repository = repository if "/" in repository else f"library/{repository}"
    return registry, repository, tag


def request(url: str, method: str, headers: dict[str, str]) -> urllib.request.Request:
    return urllib.request.Request(url, method=method, headers=headers)  # noqa: S310


def digest_of(image: str) -> str:
    registry, repository, tag = parse(image)
    url = f"https://{registry}/v2/{repository}/manifests/{tag}"
    headers = {"Accept": ACCEPT}
    try:
        with urllib.request.urlopen(request(url, "HEAD", headers), timeout=30) as response:  # noqa: S310
            return response.headers["Docker-Content-Digest"]
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            raise
        challenge = dict(re.findall(r'(\w+)="([^"]+)"', exc.headers["WWW-Authenticate"]))
    query = urllib.parse.urlencode({k: challenge[k] for k in ("service", "scope") if k in challenge})
    with urllib.request.urlopen(f"{challenge['realm']}?{query}", timeout=30) as response:  # noqa: S310
        token = json.load(response)
    headers["Authorization"] = f"Bearer {token.get('token') or token['access_token']}"
    with urllib.request.urlopen(request(url, "HEAD", headers), timeout=30) as response:  # noqa: S310
        return response.headers["Docker-Content-Digest"]


if __name__ == "__main__":
    for item in sys.argv[1:]:
        print(item, digest_of(item))
