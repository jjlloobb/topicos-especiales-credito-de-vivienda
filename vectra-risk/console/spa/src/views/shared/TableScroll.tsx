// La region desplazable de una tabla: en una pantalla estrecha (o con el zoom al 200 %) la tabla se desplaza dentro de su region y la pagina
// no se desplaza en horizontal. La region tiene nombre y foco de teclado (WCAG 2.1.1; la regla `scrollable-region-focusable` de axe): la
// tabla de dentro conserva su semantica (`table`, `caption`, `th scope`).
import type { ReactNode } from "react";
import { ui } from "../../i18n";

interface Props {
  /** El nombre de la tabla (el de su `caption`). */
  readonly name: string;
  /** `true`: con altura suficiente, la tabla se desplaza dentro de la region y su cabecera queda fija. */
  readonly tall?: boolean;
  /** `true` mientras la tabla se vuelve a pedir tras una accion (no en un refresco periodico): la region lleva `aria-busy` y una barra de progreso. */
  readonly busy?: boolean;
  readonly children: ReactNode;
}

export function TableScroll({ name, tall = false, busy = false, children }: Props) {
  return (
    // La unica excepcion de lint de `src/`: `no-noninteractive-tabindex` solo admite `tabIndex` en elementos interactivos (y en `tabpanel`), pero
    // una region con scroll propio DEBE recibir el foco para desplazarse con el teclado (WCAG 2.1.1; `scrollable-region-focusable` de axe). La
    // alternativa seria relajar la regla para todo `role="region"` en `eslint.config.mjs`, que es mas amplia que esta linea.
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- region desplazable: necesita foco de teclado
    <div className={tall ? "table-scroll table-scroll-tall" : "table-scroll"} role="region" aria-label={ui("table_scroll_label", { name })} aria-busy={busy ? true : undefined} tabIndex={0}>
      {children}
    </div>
  );
}
