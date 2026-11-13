// CA-3 de U10-T04 (Paso 15; NFR-U10-51; US-611): `@axe-core/playwright` en cada parada del recorrido de las vistas y dialogos que entran, con los
// cuatro roles, en Chromium y Firefox: cero hallazgos `serious` o `critical`. (La lista de chequeo manual y NVDA son del Paso 22, diferidos.)
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { walk } from "../e2e/tour";
import { ORIGIN, type Role } from "../e2e/support";

test.use({ baseURL: ORIGIN });

const ROLES: Role[] = ["analista", "ingeniero_riesgo", "cro", "cumplimiento"];

for (const role of ROLES) {
  test(`recorrido de ${role}: axe sin hallazgos serious ni critical en cada parada`, async ({ page, context }) => {
    const names: string[] = [];
    await walk(page, context, role, async (name) => {
      const results = await new AxeBuilder({ page }).analyze();
      const serious = results.violations
        .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
        .map((violation) => `${violation.id} (${violation.impact}): ${violation.nodes.map((node) => node.target.join(" ")).join(" | ")}`);
      expect(serious, `axe en «${name}»`).toEqual([]);
      names.push(name);
    });
    expect(names.length).toBeGreaterThan(2);
  });
}
