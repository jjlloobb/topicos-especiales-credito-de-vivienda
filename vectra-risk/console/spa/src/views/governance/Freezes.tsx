// `Freezes` (BR-U10-12; US-304): la lista de congelamientos. `cumplimiento` abre el paquete de contexto de cada uno; `cro` ve la lista
// **sin** el paquete (C03: `get_freeze` es solo de `cumplimiento`), asi que a `cro` no se le ofrece el enlace.
import { Link } from "react-router";
import { useFreezes } from "../../api/hooks";
import { useAuth } from "../../auth/AuthProvider";
import { formatDate, label, safeDecimal, ui } from "../../i18n";
import { ProblemMessage } from "../shared/ProblemMessage";

export function Freezes() {
  const query = useFreezes();
  const role = useAuth().session?.role;
  return (
    <section>
      <h2>{ui("view_freezes")}</h2>
      <p>{ui("freezes_intro")}</p>
      {role === "cumplimiento" ? null : <p>{ui("freeze_context_hidden")}</p>}
      {query.isPending ? <p role="status">{ui("loading")}</p> : null}
      {query.isError ? <ProblemMessage error={query.error} /> : null}
      {query.data === undefined ? null : query.data.length === 0 ? (
        <p>{ui("freezes_empty")}</p>
      ) : (
        <table>
          <caption>{ui("view_freezes")}</caption>
          <thead>
            <tr>
              <th scope="col">{ui("col_freeze")}</th>
              <th scope="col">{ui("col_model")}</th>
              <th scope="col">{ui("col_frozen_at")}</th>
              <th scope="col">{ui("col_trigger")}</th>
              <th scope="col">{ui("col_aggregate")}</th>
              <th scope="col">{ui("col_resolution")}</th>
            </tr>
          </thead>
          <tbody>
            {query.data.map((freeze) => (
              <tr key={freeze.freeze_id}>
                <td>
                  {role === "cumplimiento" ? (
                    <Link to={`/congelamientos/${encodeURIComponent(freeze.freeze_id)}`} aria-label={ui("freeze_open_context", { id: freeze.freeze_id })}>
                      {freeze.freeze_id}
                    </Link>
                  ) : (
                    freeze.freeze_id
                  )}
                </td>
                <td>{freeze.model_version_id}</td>
                <td>{formatDate(freeze.frozen_at)}</td>
                <td>{label("ATTRIBUTES", freeze.trigger_attribute)}</td>
                <td>{freeze.model_aggregate == null ? ui("no_value") : safeDecimal(freeze.model_aggregate)}</td>
                <td>{freeze.resolution == null ? ui("no_resolution") : label("RESOLUTION_ACTIONS", freeze.resolution.action)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
