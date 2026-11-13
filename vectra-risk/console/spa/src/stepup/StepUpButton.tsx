// `StepUpButton`: el boton de confirmacion de una accion con MFA (BR-U10-06). Con la sesion sin MFA reciente dice «Verificar y
// confirmar» y abre la ventana en el mismo clic; con MFA reciente dice `label` (el texto de la accion, del catalogo) y envia ya.
import { Button } from "react-aria-components";
import { ui } from "../i18n";
import { type StepUpAction, useStepUp } from "./StepUpProvider";

interface Props<B> extends StepUpAction<B> {
  readonly label: string;
  readonly isDisabled: boolean;
}

export function StepUpButton<B>({ body, send, label, isDisabled }: Props<B>) {
  const stepUp = useStepUp();
  return (
    <Button
      isDisabled={isDisabled || stepUp.busy}
      onPress={(event) => {
        stepUp.confirm({ body, send }, event.target as HTMLElement);
      }}
    >
      {stepUp.needsStepUp ? ui("verify_and_confirm") : label}
    </Button>
  );
}
