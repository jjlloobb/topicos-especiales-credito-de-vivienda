// `StepUpDialog` (BR-U10-06): el BFF respondio 403 `mfa_required` de todos modos (por ejemplo, el plazo vencio entre la lectura y el
// envio). El boton «Verificar identidad» abre la ventana **en su propio clic**: `onVerify` se llama dentro del manejador de `onPress`.
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import { ui } from "../i18n";

interface Props {
  readonly open: boolean;
  /** Se llama dentro del clic: aqui sale `window.open`. */
  readonly onVerify: () => void;
  readonly onCancel: () => void;
}

export function StepUpDialog({ open, onVerify, onCancel }: Props) {
  return (
    <ModalOverlay isOpen={open} onOpenChange={onCancel}>
      <Modal>
        <Dialog>
          <Heading slot="title">{ui("stepup_dialog_title")}</Heading>
          <p>{ui("stepup_dialog_body")}</p>
          <Button onPress={onVerify}>{ui("verify_identity")}</Button>
          <Button onPress={onCancel}>{ui("stepup_dialog_cancel")}</Button>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
