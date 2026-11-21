// Las marcas de agua de la consola (pedido del dueno del proyecto, 2026-11-21): ilustraciones PROPIAS del mundo del credito de vivienda, con el
// lenguaje de la familia de iconos (`icons.tsx`): solo trazo, de 2 px, con extremos y esquinas redondeados, sin relleno y sin texto. Van dentro
// del codigo como SVG (la CSP de U2 no deja cargar imagenes de otro origen, y no hay imagenes de terceros ni licencias que revisar).
// Son decorativas: `aria-hidden`, sin rol ni nombre, sin foco y sin capturar clics (`pointer-events: none` en `styles.css`), siempre en una zona
// sin texto (el pie de la pagina y el fondo de la pantalla de inicio de sesion). El color es el token `--watermark`
// del tema y la opacidad `--watermark-opacity`; se ocultan con mas contraste, con colores forzados, al imprimir y, las de las vistas, en movil.
import type { ReactNode } from "react";

export type Motif = "skyline";

const BOXES: Readonly<Record<Motif, string>> = { skyline: "0 0 320 80" };

/** Un barrio en el horizonte: casas, dos edificios de apartamentos y arboles; la casa del centro lleva la marca de verificacion de la marca. */
const SKYLINE = (
  <>
    <path d="M4 74h312" />
    <path d="M12 48 34 30l22 18" />
    <path d="M17 44v30M51 44v30" />
    <path d="M30 74V60h8v14" />
    <path d="M70 74V18h40v56" />
    <path d="M80 30h6M94 30h6M80 42h6M94 42h6M80 54h6M94 54h6" />
    <path d="M86 74v-8h8v8" />
    <path d="M124 46 152 24l28 22" />
    <path d="M130 42v32M174 42v32" />
    <path d="m142 58 7 7 12-13" />
    <path d="M196 74V60" />
    <path d="M196 60a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z" />
    <path d="M212 50 232 34l20 16" />
    <path d="M217 46v28M247 46v28" />
    <path d="M227 56h10v8h-10z" />
    <path d="M264 74V28h30v46" />
    <path d="M272 38h4M282 38h4M272 48h4M282 48h4M272 58h4M282 58h4" />
    <path d="M306 74V62" />
    <path d="M306 62a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z" />
  </>
);

const DRAWINGS: Readonly<Record<Motif, ReactNode>> = { skyline: SKYLINE };

interface Props {
  readonly motif: Motif;
  /** Donde va: decide el tamano y el anclaje (`styles.css`). */
  readonly place: "page" | "auth";
}

export function Watermark({ motif, place }: Props) {
  return (
    <svg
      className={`watermark watermark-${place} watermark-${motif}`}
      viewBox={BOXES[motif]}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {DRAWINGS[motif]}
    </svg>
  );
}

const SECTIONS = ["/casos", "/congelamientos", "/modelos"] as const;

/**
 * El motivo del pie de la pagina: el horizonte del barrio en las vistas de las demos (casos, congelamientos y modelos, con sus detalles); las
 * demas pantallas no llevan marca en el pie. (Se probaron y se descartaron un motivo distinto por seccion —una escritura, un plano— y unas llaves en
 * los estados vacios: un dibujo suelto de menos de 100 px se leia como un icono fuera de sitio.)
 */
export function sectionMotif(pathname: string): Motif | null {
  return SECTIONS.some((section) => pathname === section || pathname.startsWith(`${section}/`)) ? "skyline" : null;
}
