// U10-T03: `make -C console e2e-spa` falla con un mensaje claro si faltan los navegadores de Playwright (no se salta en silencio).
import { existsSync } from "node:fs";
import { chromium, firefox } from "@playwright/test";

const missing = [chromium, firefox].filter((browser) => !existsSync(browser.executablePath())).map((browser) => browser.name());
if (missing.length > 0) {
  console.error(`Faltan los navegadores de Playwright (${missing.join(", ")}). Instalalos, sin sudo, con: npx playwright install chromium firefox`);
  process.exit(1);
}
