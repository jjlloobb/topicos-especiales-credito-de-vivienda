// Perfiles de las PBT de la SPA (NFR-U10-62): `ci` (por omision) y `nightly`, elegidos con `VECTRA_PBT_PROFILE`. Imprimen su semilla
// (como `contracts/ts/test/client.test.ts`); con `VECTRA_PBT_SEED` se repite una corrida.
export const PROFILES = { ci: 300, nightly: 10_000 } as const;

export type Profile = keyof typeof PROFILES;

export function profile(env: NodeJS.ProcessEnv = process.env): Profile {
  return env["VECTRA_PBT_PROFILE"] === "nightly" ? "nightly" : "ci";
}

/**
 * Opciones de `fc.assert`. `atLeast` es un PISO (p. ej. el tamano de lo que se muestrea), no un techo: el perfil `nightly` nunca corre menos
 * casos que `ci`, y la linea impresa dice los casos que de verdad se corren.
 */
export function pbtOptions(
  name: string,
  env: NodeJS.ProcessEnv = process.env,
  atLeast = 0,
): { seed: number; numRuns: number; verbose: 1 } {
  const seed = env["VECTRA_PBT_SEED"] === undefined ? Date.now() % 2147483647 : Number(env["VECTRA_PBT_SEED"]);
  const chosen = profile(env);
  const numRuns = Math.max(PROFILES[chosen], atLeast);
  console.log(`fast-check ${name}: perfil=${chosen} numRuns=${numRuns} seed=${seed}`);
  return { seed, numRuns, verbose: 1 };
}
