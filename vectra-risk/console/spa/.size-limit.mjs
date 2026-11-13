// NFR-U10-03: el JavaScript **inicial** (lo que `dist/index.html` carga al entrar) pesa <= 250 KiB comprimido con **gzip**. `size-limit` usa
// brotli por omision, que da un numero menor: se fija gzip a proposito (es lo que sirve nginx).
//
// «Inicial» = el cierre de `dist/index.html` por `imports` y por los `import()` de arranque (`main.tsx` carga `App`, `wiring` y la configuracion
// a demanda, pero siempre antes de pintar), SIN los fragmentos de las vistas (`src/views/**`, que se cargan al entrar a cada ruta, con
// `React.lazy`) y sin `stepup-callback` (otra entrada de la pagina). Sale del manifiesto de Vite (`build.manifest`), no de una lista a mano:
// una vista nueva o un fragmento nuevo se miden solos. Hay que construir antes (`npm run -w console/spa build`).
import { readFileSync } from "node:fs";

const manifest = JSON.parse(readFileSync(new URL("./dist/.vite/manifest.json", import.meta.url), "utf-8"));
const isLazy = (key) => key.startsWith("src/views/") || key === "src/stepup-callback.ts";

const initial = new Set();
const visit = (key) => {
  if (initial.has(key) || isLazy(key)) return;
  initial.add(key);
  const chunk = manifest[key];
  for (const next of [...(chunk.imports ?? []), ...(chunk.dynamicImports ?? [])]) visit(next);
};
visit("index.html");

const files = [...initial].map((key) => `dist/${manifest[key].file}`).filter((file) => file.endsWith(".js"));

export default [{ name: "JavaScript inicial (gzip)", path: files, gzip: true, brotli: false, limit: "250 KiB" }];
