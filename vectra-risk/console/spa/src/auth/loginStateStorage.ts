// El unico modulo de la SPA que toca el almacenamiento de sesion del navegador (excepcion acotada de ESLint, `eslint.config.mjs`;
// decision del usuario, 2026-11-12). Guarda SOLO el estado transitorio del login por redireccion (`state`, `code_verifier`, `nonce`):
// una clave por flujo, que `oidc-client-ts` borra al leer la respuesta del callback, con exito o con error. Los tokens y el usuario
// NO pasan por aqui: viven en memoria (BR-U10-05; `manager.ts`).
export function createLoginStateStorage(win: Window = window): Storage {
  return win.sessionStorage;
}
