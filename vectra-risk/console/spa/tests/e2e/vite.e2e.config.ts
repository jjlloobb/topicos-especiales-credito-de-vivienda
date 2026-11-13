// Servidor de las pruebas con navegador de la SPA REAL (U10-T03, F-03 de la ronda 1; solo pruebas). Compila `console/spa/` (el
// `index.html` y `src/main.tsx` de verdad, con el `UserManager` real) y lo sirve con `vite preview` (el bundle de produccion, sin la
// optimizacion de dependencias en caliente del modo de desarrollo, que recargaba la pagina a media prueba). Responde `/config.json`
// apuntando al emisor de prueba y pasa `/auth/**` y `/api/**` al proceso de dobles (un solo origen, BR-U10-06). Sin CSP: `vite preview`
// no la aplica. Puertos por entorno.
import { readFileSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const SPA_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const pkg = JSON.parse(readFileSync(resolve(SPA_ROOT, "package.json"), "utf-8")) as { version: string };
const port = Number(process.env["VECTRA_E2E_APP_PORT"]);
const doubles = `http://127.0.0.1:${process.env["VECTRA_E2E_APP_DOUBLES_PORT"]}`;
const origin = `http://127.0.0.1:${port}`;

const CONFIG = {
  oidc: { authority: `${origin}/auth/realms/vectra`, client_id: "vectra-console" },
  redirect_uri: `${origin}/callback`,
  stepup_redirect_uri: `${origin}/stepup-callback`,
  grafana: { bias_dashboard_uid: "bias" },
};

const configJson = {
  name: "e2e-config-json",
  configurePreviewServer(server: { middlewares: { use: (handler: (request: IncomingMessage, response: ServerResponse, next: () => void) => void) => void } }) {
    server.middlewares.use((request, response, next) => {
      if (request.url?.split("?")[0] !== "/config.json") {
        next();
        return;
      }
      response.setHeader("content-type", "application/json");
      response.end(JSON.stringify(CONFIG));
    });
  },
};

export default defineConfig({
  root: SPA_ROOT,
  build: { outDir: resolve(SPA_ROOT, "test-results", "e2e-dist"), emptyOutDir: true },
  define: { __APP_VERSION__: JSON.stringify(pkg.version) }, // como `vite.config.ts`
  preview: {
    host: "127.0.0.1",
    port,
    strictPort: true,
    proxy: { "/auth": doubles, "/api": doubles },
  },
  plugins: [configJson],
});
