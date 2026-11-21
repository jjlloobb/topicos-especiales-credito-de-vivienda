// `RoleMenu` (BR-U10-12): el menu sale de `get_me` (el rol de la sesion) y de la tabla de rutas por rol. Incluye las vistas diferidas,
// que llevan al marcador «no disponible». La seccion activa se marca tambien dentro de un detalle: `/casos/:id` marca «Bandeja de casos» y
// `/congelamientos/:id`, «Congelamientos». Se marca UNA sola entrada, la de la ruta mas larga que es prefijo de la direccion (asi
// `/casos/nuevo` marca «Alta manual» y no la bandeja): `aria-current="page"` si es la pantalla misma, `"true"` si es un detalle suyo.
import { Link, useLocation } from "react-router";
import { ui } from "../../i18n";
import { type Role, routesFor } from "./routes";

/** La entrada del menu a la que pertenece `pathname`: la ruta mas larga que es igual o prefijo de un segmento completo; `null` si ninguna. */
export function activeMenuPath(paths: readonly string[], pathname: string): string | null {
  const matching = paths.filter((path) => pathname === path || pathname.startsWith(`${path}/`));
  return matching.reduce<string | null>((best, path) => (best === null || path.length > best.length ? path : best), null);
}

export function RoleMenu({ role }: { readonly role: Role }) {
  const { pathname } = useLocation();
  const routes = routesFor(role).filter((route) => route.inMenu);
  const active = activeMenuPath(
    routes.map((route) => route.path),
    pathname,
  );
  return (
    <nav className="app-nav" aria-label={ui("nav_label")}>
      <ul>
        {routes.map((route) => (
          <li key={route.path}>
            <Link to={route.path} aria-current={route.path !== active ? undefined : pathname === route.path ? "page" : "true"}>
              {ui(route.title)}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
