// La raiz de la SPA (frontend-components §1): `AuthProvider` > `StepUpProvider` > `InactivityProvider` > enrutador, dentro de
// `ErrorBoundary` y TanStack Query. U10-T04 agrega el enrutador, `Layout`, `RoleMenu` y las rutas por rol (`views/shared`).
import { QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useCallback, useEffect } from "react";
import { Button } from "react-aria-components";
import { BrowserRouter } from "react-router";
import { ApiProvider } from "./api/ApiProvider";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { ui } from "./i18n";
import { InactivityProvider } from "./inactivity/InactivityProvider";
import { ErrorBoundary } from "./reporter/ErrorBoundary";
import { StepUpProvider } from "./stepup/StepUpProvider";
import { AppRoutes } from "./views/shared/AppRoutes";
import type { Wiring } from "./wiring";

function Content({ wiring }: { readonly wiring: Wiring }) {
  const auth = useAuth();
  const onChunkFailure = useCallback(() => {
    wiring.reporter.reportChunkLoadFailure();
  }, [wiring.reporter]);
  if (auth.status === "loading") return <p>{ui("loading_session")}</p>;
  if (auth.session === null) {
    return (
      <main>
        <h1>{ui("login_title")}</h1>
        {auth.loginFailed ? <p role="alert">{ui("login_failed")}</p> : null}
        <Button onPress={auth.login}>{ui("login_button")}</Button>
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
  return (
    <StepUpProvider session={auth.session} env={wiring.stepUpEnv}>
      <InactivityProvider env={wiring.inactivityEnv} onLogout={auth.logout}>
        {children}
      </InactivityProvider>
    </StepUpProvider>
  );
}

export function App({ wiring }: { readonly wiring: Wiring }) {
  return (
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
  );
}
