// El estado de un caso con color **y** texto, nunca solo con color (BR-U10-10; NFR-U10-51). El color es una clase de `styles.css`.
import { label } from "../../i18n";
import type { CaseState } from "../../api/endpoints";

export function CaseStateBadge({ state }: { readonly state: CaseState }) {
  return <span className={`badge badge-${state}`}>{label("CASE_STATES", state)}</span>;
}
