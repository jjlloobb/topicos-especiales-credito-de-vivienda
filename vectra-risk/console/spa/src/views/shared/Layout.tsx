// `Layout` (frontend-components §1): el encabezado con el rol, los selectores de idioma y de tema y «Cerrar sesion», el menu por rol y el contenido de la ruta.
import { Suspense } from "react";
import { Button } from "react-aria-components";
import { Outlet, useLocation } from "react-router";
import { useAuth } from "../../auth/AuthProvider";
import { label, ui } from "../../i18n";
import { IconBrand } from "./icons";
import { sectionMotif, Watermark } from "./illustrations";
import { LanguageSelect } from "./LanguageSelect";
import { ThemeSelect } from "./ThemeSelect";
import { RoleMenu } from "./RoleMenu";

export function Layout() {
  const auth = useAuth();
  const session = auth.session;
  const motif = sectionMotif(useLocation().pathname);
  if (session === null) return null;
  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand">
            <IconBrand className="brand-mark" />
            <div>
              <h1 className="brand-name">{ui("app_title")}</h1>
              <p className="brand-tag">{ui("app_tagline")}</p>
            </div>
          </div>
          <div className="session">
            <p className="session-role">{ui("session_role", { role: label("ROLES", session.role) })}</p>
            <p className="session-mfa">{session.mfa ? ui("session_with_mfa") : ui("session_without_mfa")}</p>
            <div className="prefs" role="group" aria-label={ui("preferences_label")}>
              <LanguageSelect onBrand />
              <ThemeSelect onBrand />
            </div>
            <Button className="button-on-brand" onPress={auth.logout}>
              {ui("logout_button")}
            </Button>
          </div>
        </div>
      </header>
      <RoleMenu role={session.role} />
      <main className="page" aria-label={ui("main_label")}>
        <Suspense fallback={<p className="loading" role="status">{ui("loading")}</p>}>
          <Outlet />
        </Suspense>
        {motif === null ? null : <Watermark motif={motif} place="page" />}
      </main>
    </>
  );
}
