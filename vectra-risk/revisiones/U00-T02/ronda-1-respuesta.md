F-01: Corregido en el commit de la ronda 2: `models/__init__.py` resuelve los nombres de `models.api` de forma perezosa (PEP 562), se retira la línea de `vectra_contracts/__init__.py`; M3 y M4 pasan, import-linter 3 KEPT, mypy --strict limpio.
F-02: Corregido en el commit de la ronda 2 como efecto de F-01: `import vectra_contracts.catalog` pasa de 19 módulos vectra* con pydantic (125 ms) a 2 módulos sin pydantic (9 ms).
F-03: Corregido en el commit de la ronda 2: la guarda incluye módulos privados (solo omite dunder); ahora 38 casos con `outcome._internal`.
F-04: Corregido en el commit de la ronda 2: la prueba exige stdout y stderr vacíos además de returncode 0.
