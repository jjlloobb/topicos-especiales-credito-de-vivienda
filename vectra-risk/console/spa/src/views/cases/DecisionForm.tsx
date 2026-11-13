// `DecisionForm` (BR-U10-09; US-108, US-502): decision, factores usados (o «Ninguno»), resultado final y justificacion, con la misma
// validacion que el servidor (`decision-validation.ts`), un dialogo de confirmacion y el boton deshabilitado mientras la solicitud esta en curso.
// Errores del servidor: 422 -> en su campo (`invalid_params`); 409 `decision_already_recorded` -> aviso y recarga del caso;
// 409 `conflict_state` -> error general y recarga; 503 -> «el registro no responde; la decision quedo pendiente» (U8 BR-U8-18).
// Solo `analista` ve este formulario (lo decide `CaseDetail`).
import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type ReactElement, useRef, useState } from "react";
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import { useApi } from "../../api/ApiProvider";
import { ApiError } from "../../api/client";
import { recordDecision } from "../../api/endpoints";
import { label, problemText, ui, type UiKey } from "../../i18n";
import { Choice } from "../shared/Choice";
import { ProblemMessage } from "../shared/ProblemMessage";
import {
  type Decision,
  type DecisionField,
  type FinalOutcome,
  NO_FACTORS,
  type Outcome,
  justificationLength,
  validateDecision,
} from "./decision-validation";

interface Props {
  readonly caseId: string;
  readonly outcome: Outcome;
  readonly shapFeatureIds: readonly string[];
  readonly onRecorded: () => void;
}

const FINALS: readonly FinalOutcome[] = ["favorable", "desfavorable"];

/** Las decisiones que ofrece cada resultado (BR-U0-35): `resuelve_revision` solo si es `revision_requerida`. */
export function decisionsFor(outcome: Outcome): readonly Decision[] {
  return outcome === "revision_requerida" ? ["resuelve_revision"] : ["sigue", "se_aparta"];
}

/** El resultado final que se propone al elegir una decision: el mismo en `sigue`, el otro en `se_aparta`, ninguno al resolver una revision. */
export function suggestedFinal(decision: Decision, outcome: Outcome): FinalOutcome | null {
  if (outcome === "revision_requerida") return null;
  if (decision === "sigue") return outcome;
  return outcome === "favorable" ? "desfavorable" : "favorable";
}

type Errors = Partial<Record<DecisionField | "decision" | "final" | "general", UiKey>>;

const FIELD_OF_PARAM: Record<string, DecisionField | "decision" | "final"> = {
  justification: "justification",
  used_factors: "used_factors",
  decision: "decision",
  final_outcome: "final",
};

export function DecisionForm({ caseId, outcome, shapFeatureIds, onRecorded }: Props) {
  const api = useApi();
  const queryClient = useQueryClient();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [final, setFinal] = useState<FinalOutcome | null>(null);
  const [factors, setFactors] = useState<readonly string[]>([]);
  const [justification, setJustification] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<unknown>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inFlight = useRef(false);

  const chooseDecision = (value: Decision): void => {
    setDecision(value);
    setFinal(suggestedFinal(value, outcome));
  };

  const toggleFactor = (id: string): void => {
    if (id === NO_FACTORS) setFactors(factors.includes(NO_FACTORS) ? [] : [NO_FACTORS]);
    else setFactors((current) => (current.includes(id) ? current.filter((f) => f !== id) : [...current.filter((f) => f !== NO_FACTORS), id]));
  };

  const reload = (): void => {
    void queryClient.invalidateQueries({ queryKey: ["case", caseId] });
    void queryClient.invalidateQueries({ queryKey: ["cases"] });
  };

  const review = (event: FormEvent): void => {
    event.preventDefault();
    setServerError(null);
    setNotice(null);
    const next: Errors = {};
    if (decision === null) next.decision = "decision_error_choose_decision";
    if (final === null) next.final = "decision_error_choose_final";
    if (decision !== null && final !== null) {
      const check = validateDecision({ decision, finalOutcome: final, usedFactors: factors, justification }, { outcome, shapFeatureIds });
      if (check.status === 422) for (const error of check.errors) next[error.field] = error.message;
      if (check.status === 409) next.general = "decision_error_incoherent";
    }
    setErrors(next);
    if (Object.keys(next).length === 0) setConfirming(true);
  };

  const submit = async (): Promise<void> => {
    if (inFlight.current || decision === null || final === null) return; // un solo envio por clic
    inFlight.current = true;
    setSubmitting(true);
    try {
      await recordDecision(api, caseId, { decision, final_outcome: final, used_factors: [...factors], justification });
      setConfirming(false);
      onRecorded();
      reload();
    } catch (error) {
      setConfirming(false);
      handleError(error);
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  };

  const handleError = (error: unknown): void => {
    if (!(error instanceof ApiError)) {
      setServerError(error);
      return;
    }
    if (error.status === 422 && error.problem.invalid_params != null && error.problem.invalid_params.length > 0) {
      const next: Errors = {};
      for (const param of error.problem.invalid_params) {
        const field = FIELD_OF_PARAM[param.name];
        if (field !== undefined) next[field] = "decision_error_general";
      }
      setErrors(next);
      setServerError(error);
    } else if (error.problem.reason === "decision_already_recorded") {
      setNotice(problemText(error.problem));
      reload();
    } else if (error.problem.code === "conflict_state") {
      setNotice(problemText(error.problem));
      reload();
    } else if (error.status === 503) {
      setNotice(ui("decision_pending_registry"));
    } else {
      setServerError(error);
    }
  };

  const length = justificationLength(justification);
  const fieldError = (key: keyof Errors): ReactElement | null => {
    const message = errors[key];
    return message === undefined ? null : <p role="alert" id={`error-${key}`}>{ui(message)}</p>;
  };

  return (
    <section aria-labelledby="decision-title">
      <h3 id="decision-title">{ui("decision_form_title")}</h3>
      <form onSubmit={review} noValidate>
        <fieldset>
          <legend>{ui("decision_field_decision")}</legend>
          {decisionsFor(outcome).map((value) => (
            <Choice key={value} type="radio" name="decision" value={value} checked={decision === value} onChange={() => { chooseDecision(value); }} text={label("DECISIONS", value)} />
          ))}
          {fieldError("decision")}
        </fieldset>
        <fieldset>
          <legend>{ui("decision_field_final")}</legend>
          {FINALS.map((value) => (
            <Choice key={value} type="radio" name="final" value={value} checked={final === value} onChange={() => { setFinal(value); }} text={label("FINAL_OUTCOMES", value)} />
          ))}
          {fieldError("final")}
        </fieldset>
        <fieldset>
          <legend>{ui("decision_field_factors")}</legend>
          {shapFeatureIds.map((id) => (
            <Choice key={id} type="checkbox" checked={factors.includes(id)} onChange={() => { toggleFactor(id); }} text={id} />
          ))}
          <Choice type="checkbox" checked={factors.includes(NO_FACTORS)} onChange={() => { toggleFactor(NO_FACTORS); }} text={ui("decision_field_none")} />
          {fieldError("used_factors")}
        </fieldset>
        <label htmlFor="justification">{ui("decision_field_justification")}</label>
        <textarea
          id="justification"
          value={justification}
          onChange={(event) => { setJustification(event.target.value); }}
          aria-describedby="justification-counter"
          rows={5}
        />
        <p id="justification-counter" aria-live="polite">
          {ui("decision_counter", { count: String(length) })}
        </p>
        {fieldError("justification")}
        {fieldError("general")}
        <Button type="submit" isDisabled={submitting}>
          {ui("decision_submit")}
        </Button>
      </form>
      {notice === null ? null : <p role="alert">{notice}</p>}
      {serverError === null ? null : <ProblemMessage error={serverError} />}
      <ModalOverlay isOpen={confirming} onOpenChange={setConfirming} isDismissable={!submitting}>
        <Modal>
          <Dialog>
            <Heading slot="title">{ui("decision_confirm_title")}</Heading>
            <p>
              {ui("decision_confirm_summary", {
                decision: decision === null ? "" : label("DECISIONS", decision),
                final: final === null ? "" : label("FINAL_OUTCOMES", final),
              })}
            </p>
            <Button isDisabled={submitting} onPress={() => void submit()}>
              {submitting ? ui("decision_sending") : ui("decision_confirm_button")}
            </Button>
            <Button isDisabled={submitting} onPress={() => { setConfirming(false); }}>
              {ui("decision_confirm_cancel")}
            </Button>
          </Dialog>
        </Modal>
      </ModalOverlay>
    </section>
  );
}
