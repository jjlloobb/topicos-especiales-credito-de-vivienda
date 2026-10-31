"""Falla si un benchmark supera su umbral absoluto (P-U0-09, NFR-U0-01..03)."""

import json
import sys
from pathlib import Path

LIMITS_MS = {
    "test_bench_pipeline": {"p95": 5.0, "p99": 15.0},
    "test_bench_outcome": {"p99": 1.0},
    "test_bench_derive": {"p99": 2.0},
}


def main(path: str) -> int:
    results = {
        b["name"]: b["extra_info"] for b in json.loads(Path(path).read_text(encoding="utf-8"))["benchmarks"]
    }
    failed = False
    for name, limits in LIMITS_MS.items():
        if name not in results:
            print(f"falta el benchmark {name}")
            failed = True
            continue
        for metric, limit in limits.items():
            value = results[name][f"{metric}_ms"]
            status = "ok" if value <= limit else "EXCEDE"
            print(f"{name} {metric} = {value:.3f} ms (limite {limit}) {status}")
            failed = failed or value > limit
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
