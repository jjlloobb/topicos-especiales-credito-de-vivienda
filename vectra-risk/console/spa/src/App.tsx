// La raiz de la SPA (frontend-components §1): `AuthProvider` > `StepUpProvider` > `InactivityProvider` > enrutador, dentro de
// `ErrorBoundary` y TanStack Query. U10-T04 agrega el enrutador, `Layout`, `RoleMenu` y las rutas por rol (`views/shared`).
import { QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useCallback, useEffect } from "react";
import { Button, I18nProvider } from "react-aria-components";
import { BrowserRouter } from "react-router";
import { ApiProvider } from "./api/ApiProvider";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { ui } from "./i18n";
import { adoptSessionLocale, LOCALES } from "./i18n/language";
import { useLanguage } from "./i18n/useLanguage";
import { InactivityProvider } from "./inactivity/InactivityProvider";
import { ErrorBoundary } from "./reporter/ErrorBoundary";
import { StepUpProvider } from "./stepup/StepUpProvider";
import { AppRoutes } from "./views/shared/AppRoutes";
import { IconBrand } from "./views/shared/icons";
import { Watermark } from "./views/shared/illustrations";
import { LanguageSelect } from "./views/shared/LanguageSelect";
import { ThemeSelect } from "./views/shared/ThemeSelect";
import type { Wiring } from "./wiring";

function Content({ wiring }: { readonly wiring: Wiring }) {
  const auth = useAuth();
  const onChunkFailure = useCallback(() => {
    wiring.reporter.reportChunkLoadFailure();
  }, [wiring.reporter]);
  if (auth.status === "loading") return <p className="app-loading">{ui("loading_session")}</p>;
  if (auth.session === null) {
    return (
      <main className="auth-screen">
        <div className="auth-card">
          <p className="auth-brand">
            <IconBrand className="brand-mark" />
            {ui("app_title")}
          </p>
          <h1>{ui("login_title")}</h1>
          {auth.loginFailed ? <p role="alert">{ui("login_failed")}</p> : null}
          <Button className="button-primary" onPress={auth.login}>
            {ui("login_button")}
          </Button>
          <div className="prefs" role="group" aria-label={ui("preferences_label")}>
            <LanguageSelect />
            <ThemeSelect />
          </div>
        </div>
        <Watermark motif="skyline" place="auth" />
      </main>
    );
  }
  // El enrutador se monta con la sesion: para entonces `AuthProvider` ya limpio `/callback` y la URL es la de la pantalla.
  return (
    <BrowserRouter>
      <AppRoutes onChunkFailure={onChunkFailure} />
    </BrowserRouter>
  );
}

function Authed({ wiring, children }: { readonly wiring: Wiring; readonly children: ReactNode }) {
  const auth = useAuth();
  useEffect(() => wiring.reporter.install(window), [wiring.reporter]);
  // El `locale` de `get_me` cuenta para el idioma solo si la persona no ha elegido uno (`i18n/language.ts`); sin sesion, deja de contar.
  const sessionLocale = auth.session?.locale ?? null;
  useEffect(() => {
    adoptSessionLocale(sessionLocale);
  }, [sessionLocale]);
  return (
    <StepUpProvider session={auth.session} env={wiring.stepUpEnv}>
      <InactivityProvider env={wiring.inactivityEnv} onLogout={auth.logout}>
        {children}
      </InactivityProvider>
    </StepUpProvider>
  );
}

export function App({ wiring }: { readonly wiring: Wiring }) {
  // El idioma se lee en la raiz: al cambiar, todo el arbol se repinta con los textos nuevos sin desmontarse (ni la sesion ni el estado de
  // las pantallas se pierden).
  // React Aria trae textos propios (el boton oculto «Descartar» de un dialogo, los avisos de una lista): los da en el idioma de la consola,
  // no en el del navegador.
  const language = useLanguage();
  return (
    <I18nProvider locale={LOCALES[language]}>
    <ErrorBoundary
      onError={() => {
        wiring.reporter.report("render_error");
      }}
    >
      <QueryClientProvider client={wiring.queryClient}>
        <ApiProvider api={wiring.api}>
        <AuthProvider manager={wiring.manager} loadSession={wiring.loadSession} tokens={wiring.tokens} page={wiring.authPage}>
          <Authed wiring={wiring}>
            <Content wiring={wiring} />
          </Authed>
        </AuthProvider>
        </ApiProvider>
      </QueryClientProvider>
    </ErrorBoundary>
    </I18nProvider>
  );
}
