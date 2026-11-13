// @vitest-environment node
// BR-U10-12, BR-U10-19; US-602 (la prueba de ejemplo obligatoria de PBT-10): las rutas de la SPA por rol coinciden, **ruta por ruta**, con la columna
// «Roles» de C03 (`component-methods.md`), que se LEE del archivo (nunca con `REGISTRY` ni con la propia tabla). `cro` no ve el paquete de contexto;
// `cumplimiento` no ve la bandeja; se declaran TODAS las vistas de frontend-components §1.
import { ROLES } from "@vectra/contracts";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { HOME, homeFor, ROUTES, routeTemplate, routesFor } from "../../../../src/views/shared/routes";

const VECTRA_RISK = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..", "..", "..");
const C03 = readFileSync(resolve(VECTRA_RISK, "aidlc-docs", "inception", "application-design", "component-methods.md"), "utf-8");
const FRONTEND = readFileSync(resolve(VECTRA_RISK, "aidlc-docs", "construction", "console", "functional-design", "frontend-components.md"), "utf-8");

/** La columna «Roles» de cada operacion de la seccion C03: `operacion -> roles` (`todos` = los cuatro). */
function c03Roles(): Map<string, string[]> {
  const section = C03.slice(C03.indexOf("## C03 `console-bff`"), C03.indexOf("## C04 `case-service`"));
  const found = new Map<string, string[]>();
  for (const line of section.split("\n")) {
    const cells = line.split("|").map((cell) => cell.trim());
    const operation = /^`(\w+)\(/.exec(cells[1] ?? "")?.[1];
    if (operation === undefined || cells.length < 6) continue;
    const roles = (cells[3] ?? "").replace(/\*/g, "");
    found.set(operation, roles === "todos" ? [...ROLES] : roles.split(",").map((role) => role.trim()));
  }
  return found;
}

describe("la tabla de rutas por rol contra C03", () => {
  const c03 = c03Roles();

  it("la lectura de C03 encuentra las operaciones de la consola (si el formato cambia, esta prueba lo dice)", () => {
    expect(c03.size).toBeGreaterThanOrEqual(30);
    expect(c03.get("get_freeze")).toEqual(["cumplimiento"]);
    expect(c03.get("list_cases")).toEqual(["analista", "cro"]);
  });

  it.each(ROUTES.map((route) => [route.view, route] as const))("%s: sus roles son los de la operacion de C03", (_view, route) => {
    const expected = c03.get(route.operation);
    expect(expected, `${route.operation} no esta en C03`).toBeDefined();
    expect([...route.roles].sort(), `${route.path}: roles de ${route.operation}`).toEqual([...(expected as string[])].sort());
  });

  it("declara TODAS las vistas de frontend-components §1, tambien las diferidas, y cada ruta tiene un `operation_id` distinto o compartido a proposito", () => {
    const declared = ROUTES.map((route) => route.view);
    for (const view of ["CasesInbox", "CaseDetail", "ManualApplicationForm", "PersistentFailures", "Dossier", "IntegrityCheck", "Models", "ModelDetail", "Policies", "DataSources", "BiasDashboard", "Freezes", "FreezeContextView"]) {
      expect(declared).toContain(view);
      expect(FRONTEND, `${view} no esta en frontend-components §1`).toContain(view);
    }
    expect(new Set(declared).size).toBe(declared.length);
    expect(new Set(ROUTES.map((route) => route.path)).size).toBe(ROUTES.length);
  });

  it("`cro` no ve el paquete de contexto y `cumplimiento` no ve la bandeja", () => {
    const paths = (role: (typeof ROLES)[number]) => routesFor(role).map((route) => route.path);
    expect(paths("cro")).not.toContain("/congelamientos/:freezeId");
    expect(paths("cro")).toContain("/congelamientos");
    expect(paths("cumplimiento")).not.toContain("/casos");
    expect(paths("cumplimiento")).toContain("/congelamientos/:freezeId");
    expect(paths("analista")).not.toContain("/modelos");
  });

  it("las vistas diferidas llevan el marcador (`entry: false`) y las que entran no", () => {
    const deferred = ROUTES.filter((route) => !route.entry).map((route) => route.view).sort();
    expect(deferred).toEqual(["BiasDashboard", "DataSources", "Dossier", "IntegrityCheck", "ManualApplicationForm", "PersistentFailures", "Policies"]);
  });

  it("el inicio de cada rol es una ruta a la que ese rol llega y que aparece en su menu", () => {
    for (const role of ROLES) {
      const home = ROUTES.find((route) => route.path === homeFor(role));
      expect(home?.roles).toContain(role);
      expect(home?.inMenu).toBe(true);
      expect(HOME[role]).toBe(homeFor(role));
    }
  });
});

describe("routeTemplate (la plantilla que ve el reporter, nunca la URL)", () => {
  it.each([
    ["/", "/"],
    ["/callback", "/callback"],
    ["/stepup-callback", "/stepup-callback"],
    ["/casos", "/casos"],
    ["/casos/nuevo", "/casos/nuevo"],
    ["/casos/3fa85f64-5717-4562-b3fc-2c963f66afa6", "/casos/:caseId"],
    ["/modelos/mv-123", "/modelos/:modelId"],
    ["/congelamientos/freeze-mv-1", "/congelamientos/:freezeId"],
    ["/otra/cosa?x=1", "/{ruta}"],
  ])("%s -> %s", (path, template) => {
    expect(routeTemplate(path)).toBe(template);
  });
});
