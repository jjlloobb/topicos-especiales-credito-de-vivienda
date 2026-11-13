// Servidor de la PoC del Paso 10 (solo pruebas). Sirve `tests/poc/` desde la raiz de la SPA, pasa `/auth/**` y `/api/**` al proceso
// de dobles (un solo origen, BR-U10-06) y responde `/stepup-callback` con la pagina de la PoC. Los puertos llegan por entorno.
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const SPA_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const port = Number(process.env["VECTRA_E2E_SPA_PORT"]);
const doubles = `http://127.0.0.1:${process.env["VECTRA_E2E_PORT"]}`;

export default defineConfig({
  root: SPA_ROOT,
  server: {
    host: "127.0.0.1",
    port,
    strictPort: true,
    proxy: { "/auth": doubles, "/api": doubles },
  },
  plugins: [
    {
      name: "poc-stepup-callback",
      configureServer(server) {
        server.middlewares.use((request, _response, next) => {
          const [path = "", query] = (request.url ?? "").split("?");
          if (path === "/stepup-callback") {
            request.url = `/tests/poc/stepup-callback.html${query === undefined ? "" : `?${query}`}`;
          }
          next();
        });
      },
    },
  ],
});
