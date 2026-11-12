// La entrada de la SPA (BR-U10-05, 06): detecta `/stepup-callback` y `/callback` **antes** de montar React y de crear el `UserManager`.
export type EntryKind = "stepup-callback" | "callback" | "app";

export function entryKind(pathname: string): EntryKind {
  if (pathname === "/stepup-callback") return "stepup-callback";
  return pathname === "/callback" ? "callback" : "app";
}
