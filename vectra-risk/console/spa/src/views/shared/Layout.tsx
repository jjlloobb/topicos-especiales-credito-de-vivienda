// `Layout` (frontend-components §1): el encabezado con el rol y «Cerrar sesion», el menu por rol y el contenido de la ruta.
import { Suspense } from "react";
import { Button } from "react-aria-components";
import { Outlet } from "react-router";
import { useAuth } from "../../auth/AuthProvider";
import { label, ui } from "../../i18n";
import { RoleMenu } from "./RoleMenu";

export function Layout() {
  const auth = useAuth();
  const session = auth.session;
  if (session === null) return null;
  return (
    <>
      <header>
        <h1>{ui("app_title")}</h1>
        <p>{ui("session_role", { role: label("ROLES", session.role) })}</p>
        <p>{session.mfa ? ui("session_with_mfa") : ui("session_without_mfa")}</p>
        <Button onPress={auth.logout}>{ui("logout_button")}</Button>
      </header>
      <RoleMenu role={session.role} />
      <main aria-label={ui("main_label")}>
        <Suspense fallback={<p role="status">{ui("loading")}</p>}>
          <Outlet />
        </Suspense>
      </main>
    </>
  );
}
