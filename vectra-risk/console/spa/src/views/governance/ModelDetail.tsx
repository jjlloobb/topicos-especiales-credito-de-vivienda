// `ModelDetail` (BR-U10-12; P-1 (a) de U10-T04): una version de modelo, de lectura, con el informe de validacion que trae `get_model` (C03).
// El resumen del informe (AUC, meta, conjunto de datos, aviso) y la disparidad inicial en la misma tabla de celdas del paquete de contexto.
import { Link, useParams } from "react-router";
import type { ModelVersionDetail } from "../../api/endpoints";
import { useModel } from "../../api/hooks";
import { formatDate, label, safeDecimal, ui } from "../../i18n";
import { AttributeTable } from "../bias/DisparityTables";
import { ProblemMessage } from "../shared/ProblemMessage";

function Report({ report }: { readonly report: ModelVersionDetail["validation_report"] }) {
  if (report == null) return <p>{ui("validation_none")}</p>;
  return (
    <>
      <ul>
        <li>{ui("validation_auc", { value: safeDecimal(report.auc_roc), target: safeDecimal(report.auc_target) })}</li>
        <li>{report.auc_meets_target ? ui("validation_auc_met") : ui("validation_auc_unmet")}</li>
        <li>{ui("validation_dataset", { ref: report.dataset_ref })}</li>
      </ul>
      <p>{ui("validation_disclaimer", { text: report.disclaimer })}</p>
      {report.initial_disparity.attributes.map((attribute) => (
        <AttributeTable key={attribute.attribute} attribute={attribute} />
      ))}
    </>
  );
}

export function ModelDetail() {
  const { modelId } = useParams();
  const query = useModel(modelId ?? "");
  return (
    <section>
      <h2>{ui("view_model_detail")}</h2>
      <Link to="/modelos">{ui("view_models")}</Link>
      {query.isPending ? <p role="status">{ui("loading")}</p> : null}
      {query.isError ? <ProblemMessage error={query.error} /> : null}
      {query.data === undefined ? null : (
        <>
          <h3>{query.data.model_version_id}</h3>
          <ul>
            <li>{ui("model_state", { state: label("MODEL_STATES", query.data.state) })}</li>
            <li>{ui("model_created", { at: formatDate(query.data.created_at) })}</li>
            <li>{ui("model_registered_by", { by: query.data.registered_by })}</li>
            <li>{ui("model_feature_dictionary", { version: query.data.feature_dictionary_version })}</li>
            {query.data.investigation ? <li>{ui("model_investigation")}</li> : null}
          </ul>
          <h3>{ui("validation_title")}</h3>
          <Report report={query.data.validation_report} />
        </>
      )}
    </section>
  );
}
