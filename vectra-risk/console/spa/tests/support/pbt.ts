// Perfiles de las PBT de la SPA (NFR-U10-62): `ci` (por omision) y `nightly`, elegidos con `VECTRA_PBT_PROFILE`. Imprimen su semilla
// (como `contracts/ts/test/client.test.ts`); con `VECTRA_PBT_SEED` se repite una corrida.
export const PROFILES = { ci: 300, nightly: 10_000 } as const;

export type Profile = keyof typeof PROFILES;

export function profile(env: NodeJS.ProcessEnv = process.env): Profile {
  return env["VECTRA_PBT_PROFILE"] === "nightly" ? "nightly" : "ci";
}

export function pbtOptions(name: string, env: NodeJS.ProcessEnv = process.env): { seed: number; numRuns: number; verbose: 1 } {
  const seed = env["VECTRA_PBT_SEED"] === undefined ? Date.now() % 2147483647 : Number(env["VECTRA_PBT_SEED"]);
  const chosen = profile(env);
  console.log(`fast-check ${name}: perfil=${chosen} numRuns=${PROFILES[chosen]} seed=${seed}`);
  return { seed, numRuns: PROFILES[chosen], verbose: 1 };
}
