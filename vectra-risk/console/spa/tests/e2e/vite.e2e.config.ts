// Servidor de las pruebas con navegador de la SPA REAL (U10-T03, F-03 de la ronda 1; solo pruebas). Compila `console/spa/` (el
// `index.html` y `src/main.tsx` de verdad, con el `UserManager` real, **con la misma configuracion de build de `vite.config.ts`**: objetivos,
// sin polyfill de `modulepreload`, manifiesto) y lo sirve con `vite preview` (el bundle de produccion, sin la optimizacion de dependencias
// en caliente del modo de desarrollo, que recargaba la pagina a media prueba). Responde `/config.json` apuntando al emisor de prueba y pasa
// `/auth/**` y `/api/**` al proceso de dobles (un solo origen, BR-U10-06).
//
// U10-T04 (P-3 (a)): cada respuesta lleva las cabeceras del perfil `spa` de U2 (`common` + `spa` de `identity-edge/gateway/routes.yaml`),
// **leidas** del archivo: la CSP que recibe el navegador es la de U2, caracter por caracter. El servidor de desarrollo de Vite no sirve para
// esto: inyecta codigo en linea (React Refresh y HMR) que la CSP bloquearia sin que sea un defecto de la SPA.
import { readFileSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";
import { defineConfig, mergeConfig } from "vite";
import base from "../../vite.config.ts";

const SPA_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const ROUTES_YAML = resolve(SPA_ROOT, "..", "..", "identity-edge", "gateway", "routes.yaml");
const port = Number(process.env["VECTRA_E2E_APP_PORT"]);
const doubles = `http://127.0.0.1:${process.env["VECTRA_E2E_APP_DOUBLES_PORT"]}`;
const origin = `http://127.0.0.1:${port}`;

/** Las cabeceras del perfil `spa` de U2: `profiles.common.set` mas `profiles.spa.set`. */
export function spaHeaders(): Record<string, string> {
  const profiles = (parse(readFileSync(ROUTES_YAML, "utf-8")) as { profiles: Record<string, { set: Record<string, string> }> }).profiles;
  return { ...(profiles["common"] as { set: Record<string, string> }).set, ...(profiles["spa"] as { set: Record<string, string> }).set };
}

const CONFIG = {
  oidc: { authority: `${origin}/auth/realms/vectra`, client_id: "vectra-console" },
  redirect_uri: `${origin}/callback`,
  stepup_redirect_uri: `${origin}/stepup-callback`,
  grafana: { bias_dashboard_uid: "bias" },
};

type Middlewares = { use: (handler: (request: IncomingMessage, response: ServerResponse, next: () => void) => void) => void };

const previewServer = {
  name: "e2e-config-json-and-spa-headers",
  configurePreviewServer(server: { middlewares: Middlewares }) {
    const headers = spaHeaders();
    server.middlewares.use((request, response, next) => {
      for (const [name, value] of Object.entries(headers)) response.setHeader(name, value);
      if (request.url?.split("?")[0] !== "/config.json") {
        next();
        return;
      }
      response.setHeader("content-type", "application/json");
      response.end(JSON.stringify(CONFIG));
    });
  },
};

export default mergeConfig(
  base,
  defineConfig({
    root: SPA_ROOT,
    build: { outDir: resolve(SPA_ROOT, "test-results", "e2e-dist"), emptyOutDir: true },
    preview: {
      host: "127.0.0.1",
      port,
      strictPort: true,
      proxy: { "/auth": doubles, "/api": doubles },
    },
    plugins: [previewServer],
  }),
);
