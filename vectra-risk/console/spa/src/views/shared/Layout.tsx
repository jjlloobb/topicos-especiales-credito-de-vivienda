// `Layout` (frontend-components §1): el encabezado con el rol, los selectores de idioma y de tema y «Cerrar sesion», el menu por rol y el contenido de la ruta.
import { Suspense, useEffect, useRef, useState } from "react";
import { Button } from "react-aria-components";
import { Outlet, useLocation } from "react-router";
import { useAuth } from "../../auth/AuthProvider";
import { MFA_MAX_AGE_SECONDS } from "../../config/constants";
import { label, ui } from "../../i18n";
import { useLanguage } from "../../i18n/useLanguage";
import { useStepUp } from "../../stepup/StepUpProvider";
import { IconBrand } from "./icons";
import { sectionMotif, Watermark } from "./illustrations";
import { LanguageSelect } from "./LanguageSelect";
import { ThemeSelect } from "./ThemeSelect";
import { RoleMenu } from "./RoleMenu";
import { screenTitle } from "./routes";

export function Layout() {
  const auth = useAuth();
  const session = auth.session;
  const { pathname } = useLocation();
  const motif = sectionMotif(pathname);
  const language = useLanguage();
  const role = session?.role;
  const main = useRef<HTMLElement>(null);
  const shownPath = useRef<string | null>(null);
  const [announcement, setAnnouncement] = useState<string | null>(null);
  const screen = role === undefined ? null : screenTitle(pathname, role);

  // El titulo del documento dice la pantalla (pestanas, historial, marcadores), en el idioma en curso. Al cerrar la sesion vuelve el general.
  useEffect(() => {
    if (screen !== null) document.title = ui("document_title_view", { view: ui(screen) });
    return () => {
      document.title = ui("document_title");
    };
  }, [screen, language]);

  // Al cambiar de pantalla (no en la primera, ni al cambiar filtros o de idioma): la pagina vuelve arriba, el foco pasa al contenido y un
  // lector de pantalla oye a que pantalla se llego. Sin esto, tras «Abrir» un caso el foco quedaba en un enlace que ya no existe.
  useEffect(() => {
    if (screen === null) return;
    const first = shownPath.current === null;
    const changed = shownPath.current !== pathname;
    shownPath.current = pathname;
    if (first || !changed) return;
    document.documentElement.scrollTop = 0;
    main.current?.focus({ preventScroll: true });
    setAnnouncement(ui("route_announcement", { view: ui(screen) }));
  }, [pathname, screen]);

  // Lo mismo que decide el boton de una accion sensible («Verificar y confirmar» o el texto de la accion): la cabecera y el boton no se contradicen.
  const needsStepUp = useStepUp().needsStepUp;
  if (session === null) return null;
  return (
    <>
      <a
        className="skip-link"
        href="#contenido"
        onClick={(event) => {
          event.preventDefault(); // sin tocar la URL (el enrutador la observa): solo se mueve el foco
          main.current?.focus();
        }}
      >
        {ui("skip_to_content")}
      </a>
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
            <p className="session-mfa" title={ui("session_mfa_help", { minutes: String(MFA_MAX_AGE_SECONDS / 60) })}>
              {needsStepUp ? ui("session_without_mfa") : ui("session_with_mfa")}
            </p>
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
      <p className="visually-hidden" aria-live="polite">
        {announcement}
      </p>
      <main className="page" id="contenido" ref={main} tabIndex={-1} aria-label={ui("main_label")}>
        <Suspense fallback={<p className="loading" role="status">{ui("loading")}</p>}>
          <Outlet />
        </Suspense>
        {motif === null ? null : <Watermark motif={motif} place="page" />}
      </main>
    </>
  );
}
