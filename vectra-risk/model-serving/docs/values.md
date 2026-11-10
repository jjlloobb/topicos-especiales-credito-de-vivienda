# Values de `model-serving`: contrato con `promotion-tool`

Para U04-T05b (`promotion-tool`, Paso 12 de U4). Fija U06-T02 (Paso 7 del plan de U6; INF-U6-02, P-U6-02). El esquema que `helm` aplica es
[`chart/values.schema.json`](../chart/values.schema.json) (JSON Schema, borrador 7); este documento dice cómo editar el archivo
sin inventar campos. `test_promotion_renders.py` aplica los cuatro cambios tal como están descritos aquí y comprueba que los
ejemplos de este documento son lo que esas ediciones producen.

## Qué archivo y qué clave

- Archivo: `vectra-risk-gitops/values/<env>/model-serving.yaml` (`<env>` = `kind`, `staging` o `prod`). Argo CD lo agrega solo a los
  `valueFiles` de la Application `model-serving` cuando existe (`generate.py`); el PR no toca `components.yaml` ni `apps/`.
- Clave que edita `promotion-tool`: **solo `inferenceServices`** (una lista). Nada más del archivo: `images` (digest de las imágenes,
  del operador, Paso 11 de U6) y cualquier otra clave no son del PR. El esquema cierra el objeto (`additionalProperties: false`): una
  clave desconocida, o un `inferenceService` (sin «s») por error, hace fallar `helm template`.
- Estado inicial de los tres entornos: `inferenceServices: []`.
- Edición recomendada: cargar el YAML, cambiar la lista y escribirlo preservando el resto de claves y los comentarios (un editor que
  conserve comentarios, como `ruamel.yaml`; la prueba usa PyYAML y no comprueba los comentarios).

## Una entrada (`InferenceService`)

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| `modelVersionId` | cadena | sí | `mv-<aaaa>-<mm>-<dd>-<8 hex>` (el de `vectra_reference.package`) |
| `storageUri` | cadena | sí | `s3://model-store/<ruta>/`: el directorio del paquete (`manifest.json` y los archivos de la versión). En `prod` e `inactive` no puede tener un segmento `adversarial/` |
| `profile` | enumerado | sí | `prod`, `inactive` o `staging` |

No hay más campos. Lo demás lo deduce el chart:

- **Nombre:** `isvc-<8 hex>`, los 8 hex finales de `modelVersionId` (es el `inference_service` que `mark_active` guarda en `serving-config`).
  No se escribe en el values, así que no puede quedar incoherente con la versión.
- **Namespace:** `prod` e `inactive` → `vectra-serving`; `staging` → `vectra-staging`.
- **Predictor y explicador:** mismo `storageUri` y misma anotación `vectra.io/model-version-id`. En `staging` solo hay predictor.
- **Cómo llega el paquete al contenedor:** el chart pone `storageUri` en la variable `STORAGE_URI` de `kserve-container` (KServe descarta la
  anotación `internal.serving.kserve.io/storage-initializer-sourceuri`, por eso no se escribe). El storage initializer descarga el paquete,
  lo deja en el volumen `kserve-provision-location` (`emptyDir`, 1 GiB, declarado por el chart) montado en `/mnt/models`, y dentro del pod
  reescribe `STORAGE_URI` a `/mnt/models`. El cargador de U06-T01 lee `MODEL_DIR`, que el chart fija en `/mnt/models` (igual que su valor por omisión).
- **Arranque:** los dos contenedores declaran `command: ["python", "-m", "vectra_predictor"|"vectra_explainer"]`. KServe agrega `args`
  (`--model_name`, `--predictor_host`, `--http_port`) al explicador y, sin `command`, reemplazarían el `CMD` de la imagen; el programa ignora `sys.argv`.
- **Réplicas, recursos, prioridad, HPA, spread y PDB:** del perfil (INF-U6-01, INF-U6-02), definidos en `chart/values.yaml` bajo
  `profiles`. `promotion-tool` no los toca: solo elige el perfil. Excepción de kind (DECISIONES-LOOP.md §7): `values/kind/model-serving.yaml`
  baja los requests de memoria a 256 MiB por pod con una clave `profiles` propia; `promotion-tool` la deja intacta, como `images`.

| Perfil | Réplicas | Prioridad | Otros |
|---|---|---|---|
| `prod` | predictor 2–4, explicador 2–6, HPA por CPU al 60 % | `vectra-high` | spread por zona, un PDB por componente |
| `inactive` | 1 fija por componente | `vectra-normal` | etiqueta `vectra.io/serving-state: inactivo`, anotación `vectra.io/hpa-exempt`, sin HPA ni PDB |
| `staging` | 1 fija, solo predictor | `vectra-low` | `vectra-staging` (F30 y F46) |

## Reglas que el esquema y el chart hacen cumplir

- La clave de una entrada es (`modelVersionId`, namespace). Dos entradas con la misma versión y `profile` en el mismo namespace
  (`prod` + `inactive`, o dos `prod`) hacen fallar `helm template` con «repetido». Una versión puede estar a la vez en `prod` o
  `inactive` y en `staging`.
- El orden de la lista no importa; `promotion-tool` **agrega al final** y no reordena, para que el diff del PR sea mínimo.
- Una entrada `prod` nunca baja de 2 réplicas por componente: el mínimo está en el perfil, no en la entrada.

## Los cuatro PR

Las dos versiones de los ejemplos son M1 = `mv-2026-01-01-26300247` y M2 = `mv-2026-02-01-a1b2c3d4`.

### 1. Promoción (PR 1: agrega la nueva, no toca el activo)

Cuándo: la versión está `aprobado`. Efecto: se agrega `isvc-a1b2c3d4` con los mínimos de producción; `isvc-26300247` queda igual.

<!-- ejemplo:promocion:antes -->
```yaml
inferenceServices:
  - modelVersionId: mv-2026-01-01-26300247
    storageUri: s3://model-store/mv-2026-01-01-26300247/
    profile: prod
```

Cambio: **agregar al final** `{modelVersionId: <nueva>, storageUri: <su paquete>, profile: prod}`.

<!-- ejemplo:promocion:despues -->
```yaml
inferenceServices:
  - modelVersionId: mv-2026-01-01-26300247
    storageUri: s3://model-store/mv-2026-01-01-26300247/
    profile: prod
  - modelVersionId: mv-2026-02-01-a1b2c3d4
    storageUri: s3://model-store/mv-2026-02-01-a1b2c3d4/
    profile: prod
```

### 2. Post-activación (PR 2: baja el anterior)

Cuándo: después de `mark_active` de M2. Efecto: `isvc-26300247` pasa a 1 réplica por componente, sin HPA ni PDB.

Cambio: en la entrada de la versión anterior, `profile: prod` → `profile: inactive`. Ninguna otra entrada cambia.

<!-- ejemplo:post-activacion:despues -->
```yaml
inferenceServices:
  - modelVersionId: mv-2026-01-01-26300247
    storageUri: s3://model-store/mv-2026-01-01-26300247/
    profile: inactive
  - modelVersionId: mv-2026-02-01-a1b2c3d4
    storageUri: s3://model-store/mv-2026-02-01-a1b2c3d4/
    profile: prod
```

### 3. Rollback (PR de restauración, antes de `mark_active`)

Cuándo: US-208, con la versión anterior `inactivo`. Efecto: `isvc-26300247` vuelve a los mínimos de producción (la etiqueta
`inactivo` y la anotación `hpa-exempt` salen del render); M2 sigue en `prod` hasta el PR de post-activación que viene después de `mark_active`.

Cambio: en la entrada de la versión que se restaura, `profile: inactive` → `profile: prod`.

<!-- ejemplo:rollback:despues -->
```yaml
inferenceServices:
  - modelVersionId: mv-2026-01-01-26300247
    storageUri: s3://model-store/mv-2026-01-01-26300247/
    profile: prod
  - modelVersionId: mv-2026-02-01-a1b2c3d4
    storageUri: s3://model-store/mv-2026-02-01-a1b2c3d4/
    profile: prod
```

Después del sync, `mark_active` de M1, y el PR de post-activación baja M2 (`prod` → `inactive`), como en el punto 2.

### 4. Retiro (PR 3: quita el inactivo de más de 7 días)

Cuándo: la versión lleva más de 7 días `inactivo`. Efecto: desaparece `isvc-26300247`.

Cambio: **eliminar la entrada** de la versión retirada, que debe estar en `profile: inactive`. Partiendo del ejemplo del punto 2:

<!-- ejemplo:retiro:despues -->
```yaml
inferenceServices:
  - modelVersionId: mv-2026-02-01-a1b2c3d4
    storageUri: s3://model-store/mv-2026-02-01-a1b2c3d4/
    profile: prod
```

## `staging` (la plantilla del predictor para `source_comparison`)

No forma parte de los cuatro PR de producción. Una entrada `profile: staging` crea el predictor de 1 réplica en `vectra-staging`
con `vectra.io/component: predictor`, que es lo que seleccionan F30 y F46. El explicador de staging no se renderiza: `flows.yaml`
solo selecciona el predictor en `vectra-staging` (abierto en INF-U6-02 §3).

## Verificar un PR

```bash
helm template ms model-serving/chart -f vectra-risk-gitops/envs/<env>/values.yaml -f vectra-risk-gitops/values/<env>/model-serving.yaml
```

`helm` valida contra el esquema antes de renderizar. La evidencia de `promotion-tool` (`helm template` y `kubectl diff`) sale de ese mismo comando.
