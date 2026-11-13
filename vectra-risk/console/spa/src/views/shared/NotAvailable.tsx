// El marcador de una vista diferida por el recorte de la demo (P-17 del recorte funcional): un texto del catalogo y nada mas. No llama al BFF.
import { type UiKey, ui } from "../../i18n";

export function NotAvailable({ title }: { readonly title: UiKey }) {
  return (
    <section>
      <h2>{ui(title)}</h2>
      <p>{ui("not_available_body")}</p>
    </section>
  );
}
