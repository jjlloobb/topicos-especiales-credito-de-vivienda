// `CreditStatusBadge` (BR-U10-07): el estado del credito. `no_integrado` (el core esta desactivado) dice «Estado de credito no integrado»;
// `no_disponible` (el core cayo o es lento) dice «no disponible por ahora»; los demas, su etiqueta. Siempre texto, ademas del color.
import { CREDIT_STATUSES } from "@vectra/contracts";
import { label, notice, ui } from "../../i18n";

type CreditStatus = (typeof CREDIT_STATUSES)[number];

export function creditStatusText(status: CreditStatus): string {
  if (status === "no_integrado") return notice("credit_not_integrated");
  if (status === "no_disponible") return notice("credit_unavailable");
  return label("CREDIT_STATUSES", status);
}

export function CreditStatusBadge({ status }: { readonly status: CreditStatus }) {
  return (
    <section aria-labelledby="credit-title">
      <h3 id="credit-title">{ui("credit_title")}</h3>
      <span className={`badge badge-credit-${status}`}>{creditStatusText(status)}</span>
    </section>
  );
}
