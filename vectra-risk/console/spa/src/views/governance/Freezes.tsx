// `Freezes` (BR-U10-12; US-304): la lista de congelamientos. `cumplimiento` abre el paquete de contexto de cada uno; `cro` ve la lista
// **sin** el paquete (C03: `get_freeze` es solo de `cumplimiento`), asi que a `cro` no se le ofrece el enlace.
import { Link } from "react-router";
import { useFreezes } from "../../api/hooks";
import { useAuth } from "../../auth/AuthProvider";
import { formatDate, label, safeDecimal, ui } from "../../i18n";
import { ProblemMessage } from "../shared/ProblemMessage";
import { TableScroll } from "../shared/TableScroll";

/** La clase de la insignia de cada accion de resolucion (el texto lo dice siempre la etiqueta). */
const RESOLUTION_BADGE = { reactivar: "badge badge-ok", descartar: "badge badge-neutral", investigar: "badge badge-info" } as const;

export function Freezes() {
  const query = useFreezes();
  const role = useAuth().session?.role;
  return (
    <section>
      <h2>{ui("view_freezes")}</h2>
      <p className="hint">{ui("freezes_intro")}</p>
      {role === "cumplimiento" ? null : <p className="hint">{ui("freeze_context_hidden")}</p>}
      {query.isPending ? <p className="loading" role="status">{ui("loading")}</p> : null}
      {query.isError ? <ProblemMessage error={query.error} /> : null}
      {query.data === undefined ? null : query.data.length === 0 ? (
        <p className="empty">{ui("freezes_empty")}</p>
      ) : (
        <TableScroll name={ui("view_freezes")} busy={query.isFetching}>
        <table>
          <caption className="visually-hidden">{ui("view_freezes")}</caption>
          <thead>
            <tr>
              <th scope="col">{ui("col_freeze")}</th>
              <th scope="col">{ui("col_model")}</th>
              <th scope="col">{ui("col_frozen_at")}</th>
              <th scope="col">{ui("col_trigger")}</th>
              <th scope="col" className="num">{ui("col_aggregate")}</th>
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
                <td className="num">{freeze.model_aggregate == null ? ui("no_value") : safeDecimal(freeze.model_aggregate)}</td>
                <td>
                  {freeze.resolution == null ? (
                    <span className="badge badge-pending">{ui("no_resolution")}</span>
                  ) : (
                    <span className={RESOLUTION_BADGE[freeze.resolution.action]}>{label("RESOLUTION_ACTIONS", freeze.resolution.action)}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </TableScroll>
      )}
    </section>
  );
}
