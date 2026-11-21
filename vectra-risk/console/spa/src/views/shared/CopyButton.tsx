// «Copiar» (pasada de usabilidad del 2026-11-21): copia `value` al portapapeles **dentro del clic** (`navigator.clipboard.writeText`; la CSP no
// interviene y el perfil `spa` de U2 no trae `Permissions-Policy`) y lo confirma con un texto visible que tambien se anuncia (`role="status"`).
// Si el navegador no deja copiar (sin permiso, contexto no seguro, API ausente), no se relaja nada: el valor completo se muestra y queda
// seleccionado para copiarlo con el teclado. Sirve para identificadores que no son datos personales (`case_id`, el codigo de soporte).
import { useEffect, useRef, useState } from "react";
import { Button } from "react-aria-components";
import { ui } from "../../i18n";
import { IconCopy } from "./icons";

/** Cuanto dura a la vista la confirmacion «Copiado». */
export const COPIED_MS = 4000;

type State = "idle" | "copied" | "manual";

interface Props {
  /** El texto que se copia, completo. */
  readonly value: string;
  /** El nombre accesible del boton: dice QUE se copia («Copiar el identificador del caso»). */
  readonly label: string;
}

export function CopyButton({ value, label }: Props) {
  const [state, setState] = useState<State>("idle");
  const fallback = useRef<HTMLElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current !== null) clearTimeout(timer.current);
    },
    [],
  );

  // Con el valor ya a la vista: se selecciona entero, para que Ctrl+C lo copie.
  useEffect(() => {
    if (state !== "manual" || fallback.current === null) return;
    const selection = window.getSelection();
    if (selection === null) return;
    const range = document.createRange();
    range.selectNodeContents(fallback.current);
    selection.removeAllRanges();
    selection.addRange(range);
  }, [state]);

  const copied = (): void => {
    setState("copied");
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      setState("idle");
    }, COPIED_MS);
  };
  const manual = (): void => {
    if (timer.current !== null) clearTimeout(timer.current);
    setState("manual");
  };

  return (
    <span className="copy">
      <Button
        className="button-compact"
        aria-label={label}
        onPress={() => {
          try {
            navigator.clipboard.writeText(value).then(copied, manual);
          } catch {
            manual(); // sin API de portapapeles
          }
        }}
      >
        <IconCopy />
        {ui("copy_button")}
      </Button>
      <span className="copy-status" role="status">
        {state === "copied" ? ui("copy_done") : state === "manual" ? ui("copy_manual") : null}
      </span>
      {state === "manual" ? (
        <code className="copy-fallback" ref={fallback}>
          {value}
        </code>
      ) : null}
    </span>
  );
}
