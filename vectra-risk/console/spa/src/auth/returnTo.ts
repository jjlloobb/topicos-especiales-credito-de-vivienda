// El destino al que vuelve la SPA despues del login por redireccion (H-12: «los enlaces directos no se conservan»). Los tokens viven en
// memoria, asi que toda carga completa de una ruta (`/casos?state=no_disponible`, F5 en un detalle) pasa por el emisor y vuelve por
// `/callback`; el destino viaja en los datos del flujo de `oidc-client-ts` (los mismos que ya llevan `mode`), que la libreria guarda en la
// clave transitoria del login y BORRA al leer la respuesta: es de un solo uso y no anade ninguna clave al almacenamiento.
//
// Solo se restaura una ruta INTERNA y CONOCIDA (nada de redireccion abierta): una cadena que empieza por una sola `/`, sin `\`, sin
// caracteres de control, sin fragmento, que el analizador de URL deja identica (sin `..`, sin esquema ni host) y cuya ruta es una de las
// plantillas declaradas en `routes.ts`. `/`, `/callback` y `/stepup-callback` no son destinos. Al restaurar se exige, ademas, que el rol de
// la sesion llegue a esa ruta; si no, la SPA va al inicio del rol, como siempre.
import { type Role, ROUTES, routeTemplate } from "../views/shared/routes";

const MAX_LENGTH = 2048;
const BASE = "https://spa.invalid";
const CONTROL = /[\u0000-\u001f\u007f]/;

/** La ruta declarada a la que pertenece `raw` si es un destino interno valido; si no, `null`. */
function knownRoute(raw: unknown) {
  if (typeof raw !== "string" || raw.length === 0 || raw.length > MAX_LENGTH) return null;
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.includes("\\") || raw.includes("#") || CONTROL.test(raw)) return null;
  let url: URL;
  try {
    url = new URL(raw, BASE);
  } catch {
    return null;
  }
  // El analizador no cambio nada: mismo origen y la misma cadena (ni `..`, ni saltos de host, ni codificaciones raras).
  if (url.origin !== BASE || `${url.pathname}${url.search}` !== raw) return null;
  const template = routeTemplate(url.pathname);
  return ROUTES.find((route) => route.path === template) ?? null;
}

/** `raw` (ruta + query) si es un destino interno y conocido; si no, `null`. Se usa al guardar y otra vez al leer. */
export function restorablePath(raw: unknown): string | null {
  return knownRoute(raw) === null ? null : (raw as string);
}

/** Como `restorablePath`, y ademas el rol de la sesion llega a esa ruta. */
export function restorablePathFor(raw: unknown, role: Role): string | null {
  const route = knownRoute(raw);
  return route !== null && route.roles.includes(role) ? (raw as string) : null;
}
