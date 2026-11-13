// La entrada de la SPA (BR-U10-05, 06): detecta `/stepup-callback` **antes** de montar React y de crear el `UserManager`.
// `/callback` (el retorno del login por redireccion) NO es una entrada aparte: es la propia SPA, que canjea el codigo en memoria
// (`AuthProvider`) y sigue en la misma pagina, porque los tokens viven en memoria y una recarga los perderia.
export type EntryKind = "stepup-callback" | "app";

export function entryKind(pathname: string): EntryKind {
  return pathname === "/stepup-callback" ? "stepup-callback" : "app";
}
