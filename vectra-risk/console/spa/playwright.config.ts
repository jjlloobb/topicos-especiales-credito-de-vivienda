// Playwright de la SPA: Chromium y Firefox, contra el emisor OIDC de prueba y el BFF con dobles (P-1 de U10-T03).
// Se corre desde `vectra-risk/`: `npx playwright test -c console/spa/playwright.config.ts <filtro>`. Los navegadores se instalan
// con `npx playwright install chromium firefox` (a `~/.cache`, sin `sudo`).
//
// Dos pares servidor + dobles, porque el emisor fija su origen: la PoC del step-up (`tests/poc`) y la SPA real (`tests/e2e`, `tests/csp` y
// `tests/a11y`: el BUILD servido con `vite preview` y las cabeceras del perfil `spa` de U2, P-3 (a) de U10-T04).
// Puertos: nunca 8080 ni 8081 (son de `run_service` y chocan con otros agentes). Por omision 47173 (SPA) y 47180 (dobles);
// `VECTRA_E2E_SPA_PORT` y `VECTRA_E2E_PORT` los cambian; la SPA real usa 47174 y 47181 (`VECTRA_E2E_APP_PORT`, `VECTRA_E2E_APP_DOUBLES_PORT`). Un solo `worker`: los contadores del emisor son de todo el proceso.
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const SPA_PORT = process.env["VECTRA_E2E_SPA_PORT"] ?? "47173";
const DOUBLES_PORT = process.env["VECTRA_E2E_PORT"] ?? "47180";
const ORIGIN = `http://127.0.0.1:${SPA_PORT}`;
const env = { VECTRA_E2E_SPA_PORT: SPA_PORT, VECTRA_E2E_PORT: DOUBLES_PORT, VECTRA_E2E_ORIGIN: ORIGIN };
const APP_PORT = process.env["VECTRA_E2E_APP_PORT"] ?? "47174";
const APP_DOUBLES_PORT = process.env["VECTRA_E2E_APP_DOUBLES_PORT"] ?? "47181";
const APP_ORIGIN = `http://127.0.0.1:${APP_PORT}`;
// El emisor de la SPA real recibe su origen en `VECTRA_E2E_ORIGIN`; el Vite real, sus puertos. `tests/e2e` lee `VECTRA_E2E_APP_ORIGIN`.
process.env["VECTRA_E2E_APP_ORIGIN"] = APP_ORIGIN;
// `VECTRA_E2E_DEMO=1`: el mundo del recorrido de U10-T04 (casos en cada estado, congelamiento con paquete, modelos con informe).
const appEnv = {
  VECTRA_E2E_DEMO: "1",
  VECTRA_E2E_PORT: APP_DOUBLES_PORT,
  VECTRA_E2E_ORIGIN: APP_ORIGIN,
  VECTRA_E2E_APP_PORT: APP_PORT,
  VECTRA_E2E_APP_DOUBLES_PORT: APP_DOUBLES_PORT,
};

// P-2 (a): el bloqueador de ventanas emergentes se **enciende** (Playwright lo apaga por omision) para probar que un
// `window.open` fuera del clic queda bloqueado.
export default defineConfig({
  testDir: "tests",
  testMatch: "**/*.spec.ts",
  timeout: 60_000,
  workers: 1,
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: "list",
  use: { baseURL: ORIGIN, trace: "off" },
  webServer: [
    {
      command: "uv run python console/bff/tests/doubles/bff_e2e_server.py",
      cwd: REPO,
      env,
      url: `http://127.0.0.1:${DOUBLES_PORT}/auth/realms/vectra/.well-known/openid-configuration`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npx vite -c console/spa/tests/poc/vite.poc.config.ts",
      cwd: REPO,
      env,
      url: `${ORIGIN}/tests/poc/index.html`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "uv run python console/bff/tests/doubles/bff_e2e_server.py",
      cwd: REPO,
      env: appEnv,
      url: `http://127.0.0.1:${APP_DOUBLES_PORT}/auth/realms/vectra/.well-known/openid-configuration`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npx vite build -c console/spa/tests/e2e/vite.e2e.config.ts && npx vite preview -c console/spa/tests/e2e/vite.e2e.config.ts",
      cwd: REPO,
      env: appEnv,
      url: `${APP_ORIGIN}/config.json`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium", channel: "chromium", launchOptions: { ignoreDefaultArgs: ["--disable-popup-blocking"] } },
    },
    {
      name: "firefox",
      use: { browserName: "firefox", launchOptions: { firefoxUserPrefs: { "dom.disable_open_during_load": true } } },
    },
  ],
});
