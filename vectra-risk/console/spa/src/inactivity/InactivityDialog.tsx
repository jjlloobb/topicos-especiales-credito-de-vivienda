// `InactivityDialog` (BR-U10-20): aviso a los 25 min, «tu sesion se cerrara en 5 min», con «seguir».
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import { ui } from "../i18n";

interface Props {
  readonly open: boolean;
  readonly onContinue: () => void;
}

export function InactivityDialog({ open, onContinue }: Props) {
  return (
    <ModalOverlay isOpen={open} isDismissable={false} isKeyboardDismissDisabled>
      <Modal>
        <Dialog role="alertdialog">
          <Heading slot="title">{ui("idle_title")}</Heading>
          <p>{ui("idle_body")}</p>
          <Button onPress={onContinue}>{ui("idle_continue")}</Button>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
