// `ExplanationPanel` (BR-U10-08; US-501): la narrativa y los factores, tras el boton «Ver explicacion». Abrir el panel llama a
// `record_explanation_view` **una vez por vista del caso** y **solo con rol `analista`** (BR-U8-19: el CRO abre el panel sin esa llamada).
// Abrir el detalle sin abrir el panel no cuenta como consulta. Si la llamada falla, el panel se muestra igual y se avisa (la consulta
// queda pendiente en U8, BR-U8-18).
import { useRef, useState } from "react";
import { Button } from "react-aria-components";
import { useApi } from "../../api/ApiProvider";
import { type CaseDetail, recordExplanationView } from "../../api/endpoints";
import { safeDecimal, ui } from "../../i18n";
import type { Role } from "../shared/routes";

type Explanation = NonNullable<CaseDetail["recommendation"]>["explanation"];

interface Props {
  readonly caseId: string;
  readonly explanation: Explanation;
  readonly role: Role;
}

export function ExplanationPanel({ caseId, explanation, role }: Props) {
  const api = useApi();
  const [open, setOpen] = useState(false);
  const [recordFailed, setRecordFailed] = useState(false);
  const recorded = useRef(false);

  const toggle = (): void => {
    setOpen(!open);
    if (!open && role === "analista" && !recorded.current) {
      recorded.current = true;
      recordExplanationView(api, caseId).catch(() => {
        setRecordFailed(true);
      });
    }
  };

  return (
    <section aria-labelledby="explanation-title">
      <h3 id="explanation-title">{ui("explanation_title")}</h3>
      <Button onPress={toggle} aria-expanded={open} aria-controls="explanation-panel">
        {ui("explanation_button")}
      </Button>
      {recordFailed ? <p role="status">{ui("explanation_record_failed")}</p> : null}
      {open ? (
        <div id="explanation-panel">
          <h4>{ui("explanation_narrative")}</h4>
          <p>{explanation.narrative}</p>
          <h4>{ui("explanation_factors")}</h4>
          <ul>
            {explanation.shap_vector.map((factor) => (
              <li key={factor.feature_id}>
                {factor.feature_id} {ui("explanation_contribution", { value: safeDecimal(factor.contribution) })}
              </li>
            ))}
          </ul>
          <p>{explanation.posthoc_notice}</p>
        </div>
      ) : null}
    </section>
  );
}
