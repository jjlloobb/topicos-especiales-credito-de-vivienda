// `RoleMenu` (BR-U10-12): el menu sale de `get_me` (el rol de la sesion) y de la tabla de rutas por rol. Incluye las vistas diferidas,
// que llevan al marcador «no disponible».
import { NavLink } from "react-router";
import { ui } from "../../i18n";
import { type Role, routesFor } from "./routes";

export function RoleMenu({ role }: { readonly role: Role }) {
  return (
    <nav aria-label={ui("nav_label")}>
      <ul>
        {routesFor(role)
          .filter((route) => route.inMenu)
          .map((route) => (
            <li key={route.path}>
              <NavLink to={route.path} end>
                {ui(route.title)}
              </NavLink>
            </li>
          ))}
      </ul>
    </nav>
  );
}
