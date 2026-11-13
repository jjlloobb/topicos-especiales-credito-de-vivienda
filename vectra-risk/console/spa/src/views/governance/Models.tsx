// `Models` (BR-U10-12; US-602): la lista de versiones de modelo, **de lectura**: sin `RegisterModelForm`, `ApproveModelDialog` ni retiro (diferidos).
import { Link } from "react-router";
import { useModels } from "../../api/hooks";
import { formatDate, label, ui } from "../../i18n";
import { ProblemMessage } from "../shared/ProblemMessage";

export function Models() {
  const query = useModels();
  return (
    <section>
      <h2>{ui("view_models")}</h2>
      <p>{ui("models_intro")}</p>
      {query.isPending ? <p role="status">{ui("loading")}</p> : null}
      {query.isError ? <ProblemMessage error={query.error} /> : null}
      {query.data === undefined ? null : query.data.items.length === 0 ? (
        <p>{ui("models_empty")}</p>
      ) : (
        <table>
          <caption>{ui("view_models")}</caption>
          <thead>
            <tr>
              <th scope="col">{ui("col_model")}</th>
              <th scope="col">{ui("col_model_state")}</th>
              <th scope="col">{ui("col_registered_by")}</th>
              <th scope="col">{ui("col_updated")}</th>
            </tr>
          </thead>
          <tbody>
            {query.data.items.map((model) => (
              <tr key={model.model_version_id}>
                <td>
                  <Link to={`/modelos/${encodeURIComponent(model.model_version_id)}`}>{model.model_version_id}</Link>
                </td>
                <td>
                  <span className={`badge badge-model-${model.state}`}>{label("MODEL_STATES", model.state)}</span>
                </td>
                <td>{model.registered_by}</td>
                <td>{formatDate(model.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
