// `CaseDetail` (BR-U10-07, 08, 10, 11; US-102, 104, 106, 107, 108, 109, 110, 501, 502): el caso con su recomendacion, la explicacion (panel),
// la solicitud, el estado del credito y, solo para `analista` y con el caso `listo`, el formulario de decision. Mientras el caso esta
// `en_evaluacion` o `en_sincronizacion` se vuelve a pedir cada 3 s, hasta 2 min (D1). Un identificador que no es un UUID no llama al BFF.
import { useState } from "react";
import { Link, useParams } from "react-router";
import { useCase } from "../../api/hooks";
import { useAuth } from "../../auth/AuthProvider";
import { formatDate, label, notice, ui } from "../../i18n";
import { ProblemMessage } from "../shared/ProblemMessage";
import { ApplicationView } from "./ApplicationView";
import { CaseStateBadge } from "./CaseStateBadge";
import { CreditStatusBadge } from "./CreditStatusBadge";
import { DecisionForm } from "./DecisionForm";
import { ExplanationPanel } from "./ExplanationPanel";
import { isCaseId } from "./filters";
import { RecommendationSummary } from "./RecommendationSummary";

function Detail({ caseId }: { readonly caseId: string }) {
  const role = useAuth().session?.role;
  const query = useCase(caseId);
  const [saved, setSaved] = useState(false);
  if (query.isPending) return <p role="status">{ui("loading")}</p>;
  if (query.isError) return <ProblemMessage error={query.error} />;
  const detail = query.data;
  const recommendation = detail.recommendation ?? null; // el BFF puede omitir un campo nulo
  const processing = detail.state === "en_evaluacion" || detail.state === "en_sincronizacion";
  return (
    <>
      <p>
        <CaseStateBadge state={detail.state} /> {detail.applicant_display}
      </p>
      <p>{formatDate(detail.created_at)}</p>
      <ul>
        {detail.model_frozen_after_recommendation ? <li className="mark mark-frozen">{notice("model_frozen_after_recommendation")}</li> : null}
        {detail.anonymized ? <li className="mark">{notice("case_anonymized")}</li> : null}
      </ul>
      {processing ? <p role="status">{query.refreshStopped ? ui("case_refresh_stopped") : ui("case_refreshing")}</p> : null}
      {saved ? <p role="status">{ui("decision_saved")}</p> : null}
      <RecommendationSummary detail={detail} />
      {detail.credit_status == null ? null : <CreditStatusBadge status={detail.credit_status} />}
      {recommendation !== null && role !== undefined && (detail.state === "listo" || detail.state === "decidido") ? (
        <ExplanationPanel key={`explanation-${caseId}`} caseId={caseId} explanation={recommendation.explanation} role={role} />
      ) : null}
      <ApplicationView application={detail.application} />
      {detail.decision == null ? null : (
        <section aria-labelledby="decision-recorded-title">
          <h3 id="decision-recorded-title">{ui("decision_recorded_title")}</h3>
          <p>
            {label("DECISIONS", detail.decision.decision)} {label("FINAL_OUTCOMES", detail.decision.final_outcome)}
          </p>
          <p>{ui("decision_recorded_by", { by: detail.decision.decided_by, at: formatDate(detail.decision.decided_at) })}</p>
          <p>
            {ui("decision_used_factors")} {detail.decision.used_factors.join(", ")}
          </p>
          {detail.decision.justification === "" ? null : <p>{ui("decision_justification")} {detail.decision.justification}</p>}
        </section>
      )}
      {role === "analista" && detail.state === "listo" && recommendation !== null ? (
        <DecisionForm
          key={`decision-${caseId}`}
          caseId={caseId}
          outcome={recommendation.outcome}
          shapFeatureIds={recommendation.explanation.shap_vector.map((factor) => factor.feature_id)}
          onRecorded={() => {
            setSaved(true);
          }}
        />
      ) : null}
    </>
  );
}

export function CaseDetail() {
  const { caseId } = useParams();
  return (
    <section>
      <h2>{ui("view_case_detail")}</h2>
      <Link to="/casos">{ui("back_to_inbox")}</Link>
      {caseId !== undefined && isCaseId(caseId) ? <Detail caseId={caseId} /> : <p role="alert">{ui("go_to_case_invalid")}</p>}
    </section>
  );
}
