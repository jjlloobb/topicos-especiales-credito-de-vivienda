// Genera los tipos de cada spec con openapi-typescript (NFR-U0-34).
import { execFileSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const specs = join(here, "..", "..", "openapi");
const out = join(here, "..", "src", "generated");
for (const file of readdirSync(specs).filter((name) => name.endsWith(".yaml"))) {
  const target = join(out, file.replace(".yaml", ".d.ts"));
  execFileSync("npx", ["openapi-typescript", join(specs, file), "-o", target], { stdio: "inherit" });
}
