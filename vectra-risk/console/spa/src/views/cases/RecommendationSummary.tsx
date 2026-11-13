// `RecommendationSummary` (BR-U10-08; US-106): el resultado del modelo (`outcome`, puntaje, confianza y razones) con las marcas de baja
// confianza y de `revision_requerida`. Los `Decimal4` son cadenas: se formatean con `Intl`, sin pasar por `Number(` ni `parseFloat`.
import type { CaseDetail } from "../../api/endpoints";
import { label, notice, safeDecimal, ui } from "../../i18n";

export function RecommendationSummary({ detail }: { readonly detail: CaseDetail }) {
  const recommendation = detail.recommendation ?? null; // el BFF puede omitir un campo nulo
  const outcome = detail.outcome ?? recommendation?.outcome ?? null;
  const score = detail.score ?? recommendation?.score ?? null;
  if (outcome === null && score === null) return <p>{ui("case_unavailable")}</p>;
  const lowConfidence = recommendation?.reasons.includes("baja_confianza") === true;
  return (
    <section aria-labelledby="recommendation-title">
      <h3 id="recommendation-title">{ui("recommendation_title")}</h3>
      <ul>
        {outcome === null ? null : <li>{ui("recommendation_outcome", { outcome: label("OUTCOMES", outcome) })}</li>}
        <li>{score === null ? ui("no_score") : ui("recommendation_score", { score: safeDecimal(score) })}</li>
        {recommendation === null ? null : <li>{ui("recommendation_confidence", { confidence: safeDecimal(recommendation.confidence) })}</li>}
      </ul>
      {outcome === "revision_requerida" ? <p className="mark mark-review">{notice("revision_requerida")}</p> : null}
      {lowConfidence ? <p className="mark mark-low">{notice("low_confidence")}</p> : null}
      {recommendation === null || recommendation.reasons.length === 0 ? null : (
        <>
          <h4>{ui("reasons_title")}</h4>
          <ul>
            {recommendation.reasons.map((reason) => (
              <li key={reason}>{label("REASON_CODES", reason)}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
