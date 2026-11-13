// `ResolveFrozenDialog` (BR-U10-13; US-305): `reactivar`, `descartar` o `investigar`, con justificacion obligatoria (1 a 2000, el rango de
// `FrozenResolutionIn`) y MFA. Usa el boton de confirmacion y `StepUpDialog` de `stepup` (no hay otro flujo): sin MFA reciente el boton
// dice «Verificar y confirmar» y abre la ventana en ese clic; un 403 `mfa_required` inesperado abre `StepUpDialog`, y el reintento unico lleva
// la misma justificacion. `reactivar` avisa de la ventana de monitoreo. Es el flujo de D2.
import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import { useApi } from "../../api/ApiProvider";
import { MfaRequiredError } from "../../api/client";
import { type FrozenResolutionIn, resolveFrozen } from "../../api/endpoints";
import { label, ui } from "../../i18n";
import { StepUpButton } from "../../stepup/StepUpButton";
import type { ConfirmResult } from "../../stepup/StepUpProvider";
import { Choice } from "../shared/Choice";
import { ProblemMessage } from "../shared/ProblemMessage";
import { justificationOk } from "./resolution";

type Action = FrozenResolutionIn["action"];
const ACTIONS: readonly Action[] = ["reactivar", "descartar", "investigar"];

interface Props {
  readonly modelVersionId: string;
  readonly freezeId: string;
  readonly isOpen: boolean;
  readonly onClose: () => void;
  readonly onResolved: () => void;
}

export function ResolveFrozenDialog({ modelVersionId, freezeId, isOpen, onClose, onResolved }: Props) {
  const api = useApi();
  const queryClient = useQueryClient();
  const [action, setAction] = useState<Action>("reactivar");
  const [justification, setJustification] = useState("");
  const [error, setError] = useState<unknown>(null);
  const inFlight = useRef(false);
  const valid = justificationOk(justification);

  const send = async (body: FrozenResolutionIn): Promise<ConfirmResult> => {
    if (inFlight.current) return "failed";
    inFlight.current = true;
    setError(null);
    try {
      await resolveFrozen(api, modelVersionId, body);
      void queryClient.invalidateQueries({ queryKey: ["freeze", freezeId] });
      void queryClient.invalidateQueries({ queryKey: ["freezes"] });
      setJustification("");
      onResolved();
      return "ok";
    } catch (caught) {
      if (caught instanceof MfaRequiredError) return "mfa_required";
      setError(caught);
      return "failed";
    } finally {
      inFlight.current = false;
    }
  };

  return (
    <ModalOverlay isOpen={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <Modal>
        <Dialog>
          <Heading slot="title">{ui("resolve_title")}</Heading>
          <fieldset>
            <legend>{ui("resolve_action")}</legend>
            {ACTIONS.map((value) => (
              <Choice key={value} type="radio" name="resolve-action" value={value} checked={action === value} onChange={() => { setAction(value); }} text={label("RESOLUTION_ACTIONS", value)} />
            ))}
          </fieldset>
          {action === "reactivar" ? <p role="note">{ui("resolve_reactivate_warning")}</p> : null}
          <label htmlFor="resolve-justification">{ui("resolve_justification")}</label>
          <textarea
            id="resolve-justification"
            value={justification}
            rows={4}
            aria-describedby="resolve-hint"
            onChange={(event) => { setJustification(event.target.value); }}
          />
          <p id="resolve-hint" aria-live="polite">
            {justification.trim() === "" ? ui("resolve_error_required") : valid ? ui("resolve_counter", { count: String([...justification].length) }) : ui("resolve_error_too_long")}
          </p>
          {error === null ? null : <ProblemMessage error={error} />}
          <StepUpButton body={{ action, justification }} send={send} label={ui("resolve_submit")} isDisabled={!valid} />
          <Button onPress={onClose}>{ui("resolve_close")}</Button>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
