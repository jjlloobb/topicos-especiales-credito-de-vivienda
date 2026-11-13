// «Sin acceso» (BR-U10-12): la ruta existe pero el rol no llega a ella. Se muestra sin llamar al BFF; cada endpoint valida igual.
import { Link } from "react-router";
import { ui } from "../../i18n";

export function NoAccess() {
  return (
    <section>
      <h2>{ui("no_access_title")}</h2>
      <p>{ui("no_access_body")}</p>
      <Link to="/">{ui("back_home")}</Link>
    </section>
  );
}

/** Una direccion que no es ninguna ruta de la SPA. */
export function UnknownRoute() {
  return (
    <section>
      <h2>{ui("not_found_title")}</h2>
      <p>{ui("route_unknown")}</p>
      <Link to="/">{ui("back_home")}</Link>
    </section>
  );
}
