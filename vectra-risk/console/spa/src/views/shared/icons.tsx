// La familia de iconos de la consola: SVG propios dentro del codigo (la CSP de U2 no deja cargar imagenes ni fuentes de otro origen, y no hay
// paquetes de iconos). Todos comparten la caja de 24 px, el trazo de 2 px con extremos y esquinas redondeados, sin relleno y con el color del
// texto (`currentColor`). Son decorativos (`aria-hidden`): acompanan a un texto, nunca lo sustituyen, asi que los nombres accesibles no cambian.
import type { ReactNode } from "react";

function Icon({ className, children }: { readonly className?: string | undefined; readonly children: ReactNode }) {
  return (
    <svg
      className={className === undefined ? "icon" : `icon ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

interface Props {
  readonly className?: string;
}

/** La marca: una casa con una marca de verificacion (credito de vivienda). */
export function IconBrand({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="M3 11.5 12 4l9 7.5" />
      <path d="M5.5 10v9.5h13V10" />
      <path d="m9 14.5 2.2 2.2 3.8-4.2" />
    </Icon>
  );
}

/** Abrir un elemento (ir a su detalle). */
export function IconOpen({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
    </Icon>
  );
}

/** Volver a la lista. */
export function IconBack({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="M19 12H5" />
      <path d="m11 6-6 6 6 6" />
    </Icon>
  );
}

export function IconFilter({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="M4 6h16" />
      <path d="M7 12h10" />
      <path d="M10 18h4" />
    </Icon>
  );
}

export function IconFirst({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="M6 6v12" />
      <path d="m17 6-6 6 6 6" />
    </Icon>
  );
}

export function IconPrevious({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="m14 6-6 6 6 6" />
    </Icon>
  );
}

export function IconNext({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="m10 6 6 6-6 6" />
    </Icon>
  );
}

export function IconLast({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="M18 6v12" />
      <path d="m7 6 6 6-6 6" />
    </Icon>
  );
}

/** Exito: una accion quedo registrada. */
export function IconSuccess({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z" />
      <path d="m8 12.5 2.8 2.8L16 9.5" />
    </Icon>
  );
}

/** Aviso: algo que mirar con cautela. */
export function IconWarning({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="M12 4 3 19.5h18L12 4Z" />
      <path d="M12 10v4.5" />
      <path d="M12 17v.2" />
    </Icon>
  );
}

/** Error: algo fallo o un campo no es valido. */
export function IconError({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z" />
      <path d="M12 7.5v5.5" />
      <path d="M12 16.3v.2" />
    </Icon>
  );
}

/** Idioma: un globo con un meridiano y el ecuador. */
export function IconLanguage({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z" />
      <path d="M3 12h18" />
      <path d="M12 3c2.4 2.5 3.6 5.5 3.6 9s-1.2 6.5-3.6 9c-2.4-2.5-3.6-5.5-3.6-9S9.6 5.5 12 3Z" />
    </Icon>
  );
}

/** Un control que despliega una lista. */
export function IconExpand({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="m7 10 5 5 5-5" />
    </Icon>
  );
}

/** Tema claro: un sol. */
export function IconSun({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" />
      <path d="M12 3v2" />
      <path d="M12 19v2" />
      <path d="M3 12h2" />
      <path d="M19 12h2" />
      <path d="m5.6 5.6 1.4 1.4" />
      <path d="m17 17 1.4 1.4" />
      <path d="m5.6 18.4 1.4-1.4" />
      <path d="m17 7 1.4-1.4" />
    </Icon>
  );
}

/** Tema oscuro: una luna. */
export function IconMoon({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
    </Icon>
  );
}

/** Tema del sistema: una pantalla. */
export function IconSystem({ className }: Props) {
  return (
    <Icon className={className}>
      <path d="M4 5h16v11H4z" />
      <path d="M9 20h6" />
      <path d="M12 16v4" />
    </Icon>
  );
}
