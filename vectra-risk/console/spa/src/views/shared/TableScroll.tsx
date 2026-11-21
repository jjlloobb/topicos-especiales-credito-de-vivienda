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
  /** `true` mientras la tabla se vuelve a pedir (`isFetching`): la region lleva `aria-busy` y una barra de progreso. */
  readonly busy?: boolean;
  readonly children: ReactNode;
}

export function TableScroll({ name, tall = false, busy = false, children }: Props) {
  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- una region con scroll necesita foco de teclado para desplazarse
    <div className={tall ? "table-scroll table-scroll-tall" : "table-scroll"} role="region" aria-label={ui("table_scroll_label", { name })} aria-busy={busy ? true : undefined} tabIndex={0}>
      {children}
    </div>
  );
}
