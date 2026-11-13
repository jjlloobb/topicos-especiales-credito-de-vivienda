// `ProblemMessage` (BR-U10-17; SECURITY-15): el texto del catalogo de un error de la API y, si el servidor lo dio, el codigo de soporte
// (`correlation_id`). Nunca el `detail` ni una traza. Un fallo de transporte (timeout, sin red) tiene su propio texto.
import { ApiError, TransportError } from "../../api/client";
import { type Problem, problemText, ui } from "../../i18n";

const GENERIC: Problem = { code: "internal_error" };

export function problemOf(error: unknown): Problem {
  return error instanceof ApiError ? error.problem : GENERIC;
}

/** El mensaje de cualquier error que llega a una vista. */
export function errorText(error: unknown): string {
  if (error instanceof TransportError) return error.kind === "timeout" ? ui("api_timeout") : ui("api_network");
  return problemText(problemOf(error));
}

export function ProblemMessage({ error }: { readonly error: unknown }) {
  const text = errorText(error);
  const correlation = error instanceof ApiError ? error.problem.correlation_id : null;
  const showCode = correlation != null && correlation !== "" && !text.includes(correlation);
  return (
    <div role="alert">
      <p>{text}</p>
      {showCode ? <p>{ui("support_code", { correlation_id: correlation })}</p> : null}
    </div>
  );
}
