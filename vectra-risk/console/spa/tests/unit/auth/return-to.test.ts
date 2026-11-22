// @vitest-environment node
// H-12 («los enlaces directos no se conservan»): el saneado del destino al que la SPA vuelve despues del login por redireccion. Solo una
// ruta interna y conocida (nada de redireccion abierta), nunca `/callback` ni `/stepup-callback`, y solo si el rol llega a ella.
import { describe, expect, it } from "vitest";
import { restorablePath, restorablePathFor } from "../../../src/auth/returnTo";
import { ROUTES } from "../../../src/views/shared/routes";

const CASE = "/casos/3fa85f64-5717-4562-b3fc-2c963f66afa6";

describe("restorablePath: solo rutas internas y conocidas", () => {
  it.each([
    "/casos",
    "/casos?state=no_disponible",
    "/casos?state=listo&page=2",
    "/casos?state=listo&state=vencido&channel=web&from=2026-11-01&to=2026-11-12&frozen=1",
    CASE,
    "/congelamientos",
    "/congelamientos/freeze-mv-congelado",
    "/modelos/mv-activo",
    "/casos/nuevo",
  ])("%s se conserva tal cual", (path) => {
    expect(restorablePath(path)).toBe(path);
  });

  it("todas las rutas declaradas (con un identificador de ejemplo) son destinos", () => {
    for (const route of ROUTES) {
      const path = route.path.replace(/:\w+/, "abc-123");
      expect(restorablePath(path), route.path).toBe(path);
    }
  });

  it.each([
    ["otro origen con //", "//evil.example/casos"],
    ["otro origen con ///", "///evil.example"],
    ["esquema https", "https://evil.example/casos"],
    ["esquema javascript", "javascript:alert(1)"],
    ["barra invertida tras la raiz", "/\\evil.example"],
    ["barra invertida en medio", "/casos\\..\\x"],
    ["sin barra inicial", "casos"],
    ["relativa", "./casos"],
    ["vacia", ""],
    ["la raiz", "/"],
    ["/callback", "/callback"],
    ["/callback con el codigo", "/callback?code=c&state=s"],
    ["/stepup-callback", "/stepup-callback?code=c&state=s"],
    ["ruta desconocida", "/no/existe"],
    ["prefijo que no es un segmento", "/casosx"],
    ["un segmento de mas", `${CASE}/extra`],
    ["subida con ..", "/casos/../callback"],
    ["subida codificada que el analizador resuelve", "/casos/%2e%2e/callback"],
    ["fragmento", "/casos#x"],
    ["salto de linea", "/casos\n//evil.example"],
    ["tabulador", "/\t/evil.example"],
    ["caracter nulo", "/casos\u0000"],
    ["usuario y host", "/@evil.example"],
    ["espacio sin codificar", "/casos?x=a b"],
  ])("descarta %s", (_name, hostile) => {
    expect(restorablePath(hostile)).toBeNull();
  });

  it("descarta lo que no es una cadena y lo que es demasiado largo", () => {
    for (const value of [null, undefined, 5, {}, ["/casos"], true]) expect(restorablePath(value)).toBeNull();
    expect(restorablePath(`/casos?state=${"a".repeat(2100)}`)).toBeNull();
  });
});

describe("restorablePathFor: ademas, el rol llega a la ruta", () => {
  it("la bandeja y el detalle de un caso son de analista y cro; no de cumplimiento ni de ingeniero", () => {
    for (const path of ["/casos?state=no_disponible", CASE]) {
      expect(restorablePathFor(path, "analista")).toBe(path);
      expect(restorablePathFor(path, "cro")).toBe(path);
      expect(restorablePathFor(path, "cumplimiento")).toBeNull();
      expect(restorablePathFor(path, "ingeniero_riesgo")).toBeNull();
    }
  });

  it("el paquete de un congelamiento es solo de cumplimiento; el detalle de un modelo no es del analista", () => {
    expect(restorablePathFor("/congelamientos/freeze-1", "cumplimiento")).toBe("/congelamientos/freeze-1");
    expect(restorablePathFor("/congelamientos/freeze-1", "cro")).toBeNull();
    expect(restorablePathFor("/modelos/mv-1", "ingeniero_riesgo")).toBe("/modelos/mv-1");
    expect(restorablePathFor("/modelos/mv-1", "analista")).toBeNull();
  });

  it("un destino hostil no se restaura con ningun rol", () => {
    for (const hostile of ["//evil.example", "https://evil.example", "/\\evil.example", "/callback", "/no/existe", null]) {
      for (const role of ["analista", "cro", "cumplimiento", "ingeniero_riesgo"] as const) expect(restorablePathFor(hostile, role)).toBeNull();
    }
  });
});
