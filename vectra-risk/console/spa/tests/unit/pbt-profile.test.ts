// NFR-U10-62: el perfil `nightly` corre mas casos que `ci` y la linea impresa dice los casos que de verdad se corren (F-05, ronda 1).
import fc from "fast-check";
import { afterEach, describe, expect, it, vi } from "vitest";
import { pbtOptions, profile } from "../support/pbt";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("perfiles de las PBT", () => {
  it("`ci` es el perfil por omision y `nightly` lo elige VECTRA_PBT_PROFILE", () => {
    expect(profile({})).toBe("ci");
    expect(profile({ VECTRA_PBT_PROFILE: "nightly" })).toBe("nightly");
  });

  it("nightly corre 10000 casos aunque el piso sea menor; ci corre 300, o el piso si es mayor", () => {
    vi.spyOn(console, "log").mockImplementation(() => undefined);
    expect(pbtOptions("x", { VECTRA_PBT_PROFILE: "nightly" }, 350).numRuns).toBe(10_000);
    expect(pbtOptions("x", {}, 175).numRuns).toBe(300);
    expect(pbtOptions("x", {}, 350).numRuns).toBe(350);
  });

  it("la linea impresa dice los casos que fast-check corre de verdad, con la semilla", () => {
    const log = vi.spyOn(console, "log").mockImplementation(() => undefined);
    for (const [env, floor] of [[{ VECTRA_PBT_PROFILE: "nightly" }, 350], [{}, 350], [{}, 0]] as const) {
      log.mockClear();
      let runs = 0;
      const options = pbtOptions("PBT", { ...env, VECTRA_PBT_SEED: "7" }, floor);
      fc.assert(fc.property(fc.nat(), () => (runs += 1) > 0), { ...options, verbose: 0 });
      expect(runs).toBe(options.numRuns);
      expect(String(log.mock.calls[0]?.[0])).toBe(`fast-check PBT: perfil=${profile(env)} numRuns=${runs} seed=7`);
    }
  });
});
