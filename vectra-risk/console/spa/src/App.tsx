// La raiz de la SPA (frontend-components §1): `AuthProvider` > `StepUpProvider` > `InactivityProvider` > contenido, dentro de
// `ErrorBoundary` y TanStack Query. Esta tarea (U10-T03) trae un contenido minimo; `Layout`, `RoleMenu`, las rutas y las vistas son de
// U10-T04, que reemplaza `Content`.
import { QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useEffect } from "react";
import { Button } from "react-aria-components";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { label, ui } from "./i18n";
import { InactivityProvider } from "./inactivity/InactivityProvider";
import { ErrorBoundary } from "./reporter/ErrorBoundary";
import { StepUpProvider } from "./stepup/StepUpProvider";
import type { Wiring } from "./wiring";

function Content() {
  const auth = useAuth();
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
  return (
    <main>
      <h1>{ui("app_title")}</h1>
      <p>{ui("session_role", { role: label("ROLES", auth.session.role) })}</p>
      <Button onPress={auth.logout}>{ui("logout_button")}</Button>
    </main>
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
        <AuthProvider manager={wiring.manager} loadSession={wiring.loadSession} tokens={wiring.tokens}>
          <Authed wiring={wiring}>
            <Content />
          </Authed>
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
