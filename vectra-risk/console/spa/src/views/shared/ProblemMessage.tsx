// `ProblemMessage` (BR-U10-17; SECURITY-15): el texto del catalogo de un error de la API y, si el servidor lo dio, el codigo de soporte
// (`correlation_id`). Nunca el `detail` ni una traza. Un fallo de transporte (timeout, sin red) tiene su propio texto.
import { Button } from "react-aria-components";
import { ApiError, TransportError } from "../../api/client";
import { useAuth } from "../../auth/AuthProvider";
import { type Problem, problemText, ui } from "../../i18n";
import { CopyButton } from "./CopyButton";
import { IconError } from "./icons";

const GENERIC: Problem = { code: "internal_error" };

export function problemOf(error: unknown): Problem {
  return error instanceof ApiError ? error.problem : GENERIC;
}

/** El mensaje de cualquier error que llega a una vista. */
export function errorText(error: unknown): string {
  if (error instanceof TransportError) return error.kind === "timeout" ? ui("api_timeout") : ui("api_network");
  return problemText(problemOf(error));
}

interface Props {
  readonly error: unknown;
  /** Un texto propio de la vista para este error (por ejemplo, que significa un 409 en ESTA accion), en vez del general del catalogo. */
  readonly text?: string;
}

/**
 * Pasada de usabilidad del 2026-11-21: el codigo de soporte lleva un boton «Copiar» (tambien cuando va dentro del mensaje generico), y un
 * `unauthenticated` (la sesion vencio sin aviso: el refresco del token fallo y el siguiente 401 lo descubre) ofrece «Iniciar sesion de nuevo»,
 * que es el mismo `login` de la pantalla de inicio y vuelve a esta ruta.
 */
export function ProblemMessage({ error, text: own }: Props) {
  const auth = useAuth();
  const text = own ?? errorText(error);
  const problem = error instanceof ApiError ? error.problem : null;
  const correlation = problem?.correlation_id ?? null;
  const hasCode = correlation != null && correlation !== "";
  return (
    <div role="alert">
      <p>
        <IconError />
        {text}
      </p>
      {hasCode ? (
        <p className="support-code">
          {text.includes(correlation) ? null : <span>{ui("support_code", { correlation_id: correlation })}</span>}
          <CopyButton value={correlation} label={ui("support_code_copy")} />
        </p>
      ) : null}
      {problem?.code === "unauthenticated" ? (
        <p>
          <Button onPress={auth.login}>{ui("login_again_button")}</Button>
        </p>
      ) : null}
    </div>
  );
}
