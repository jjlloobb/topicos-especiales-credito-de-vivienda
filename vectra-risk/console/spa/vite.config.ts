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

// Perfil de las PBT (NFR-U10-62): `ci` por omision, `nightly` con `VECTRA_PBT_PROFILE=nightly`. Los casos de cada uno: tests/support/pbt.ts.
export default defineConfig({
  plugins: [react()],
  // `app_version` del `reporter` (BR-U10-22): SemVer de `package.json`, inyectado en el build.
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
  server: { proxy },
  preview: { proxy },
  test: {
    environment: "node",
    // La semilla de fast-check se imprime con console.log: sin esto el reportero por omision oculta la salida de las pruebas que pasan.
    silent: false,
    include: ["tests/unit/**/*.test.{ts,tsx}", "tests/property/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      // Sin `exclude`: ningun archivo de `src/` queda fuera del numero (U10-T03, «Cobertura y PBT»).
      reporter: [["text", { skipFull: false }]],
      thresholds: {
        // U10-T03 (P-5 (a)): >= 80 % de ramas sobre todo `src/`; NFR-U10-61: 100 % en `stepup`.
        branches: 80,
        "src/stepup/**": { branches: 100 },
      },
    },
  },
});
