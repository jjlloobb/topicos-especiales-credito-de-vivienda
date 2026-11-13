import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const here = dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(readFileSync(resolve(here, "package.json"), "utf-8")) as { version: string };

// Un solo origen (BR-U10-06): en desarrollo y en `vite preview`, `/auth/**` (Keycloak o el emisor de prueba) y `/api/**` (BFF) pasan
// al proceso que dice `VECTRA_E2E_PORT` (el servidor de dobles de `console/bff/tests/doubles/`). Sin la variable no hay proxy.
const backend = process.env["VECTRA_E2E_PORT"];
const proxy = backend === undefined ? undefined : { "/auth": `http://127.0.0.1:${backend}`, "/api": `http://127.0.0.1:${backend}` };

// Los objetivos de `build.target` (NFR-U10-50): uno por familia de `browserslist`, con un piso comun a las versiones vigentes.
export const BUILD_TARGET = ["chrome130", "edge130", "firefox128"];

// Perfil de las PBT (NFR-U10-62): `ci` por omision, `nightly` con `VECTRA_PBT_PROFILE=nightly`. Los casos de cada uno: tests/support/pbt.ts.
export default defineConfig({
  plugins: [react()],
  // `app_version` del `reporter` (BR-U10-22): SemVer de `package.json`, inyectado en el build.
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
  build: {
    // NFR-U10-50: las dos ultimas versiones de Chrome y de Edge y Firefox ESR (`browserslist` de `package.json`; una prueba las ata).
    target: BUILD_TARGET,
    // P-U10-08: sin el polyfill de `modulepreload`, que se inyectaria como `<script>` en linea (la CSP de U2 no lo permite).
    modulePreload: { polyfill: false },
    // `.size-limit.mjs` lee el manifiesto para medir el cierre del `index.html` (NFR-U10-03).
    manifest: true,
  },
  server: { proxy },
  preview: { proxy },
  test: {
    environment: "node",
    // La semilla de fast-check se imprime con console.log: sin esto el reportero por omision oculta la salida de las pruebas que pasan.
    silent: false,
    // La primera vista que se monta en cada archivo paga la carga de React Aria bajo la instrumentacion de la cobertura y la maquina es compartida:
    // 5 s (el valor por omision) no alcanza en frio (U10-T04: se medio ~6 s con la suite completa); 20 s si.
    testTimeout: 20_000,
    include: ["tests/unit/**/*.test.{ts,tsx}", "tests/property/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      // Sin `exclude`: ningun archivo de `src/` queda fuera del numero (U10-T03, «Cobertura y PBT»).
      reporter: [["text", { skipFull: false }]],
      thresholds: {
        // U10-T03 (P-5 (a)): >= 80 % de ramas sobre todo `src/`; NFR-U10-61: 100 % en `stepup`.
        // U10-T04 (Paso 16): ademas, 100 % en la validacion de la decision (el archivo que PBT-U10-04 ata al oraculo de U8).
        branches: 80,
        "src/stepup/**": { branches: 100 },
        "src/views/cases/decision-validation.ts": { branches: 100 },
      },
    },
  },
});
