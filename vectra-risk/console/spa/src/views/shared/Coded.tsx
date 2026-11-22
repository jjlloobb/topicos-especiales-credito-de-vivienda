// Un codigo del servidor mostrado con un texto legible (pasada de usabilidad del 2026-11-21): se ve el texto y el codigo original queda en
// el `title`, para quien lo necesite (soporte, una consulta al registro). Si el texto ES el codigo, no hay `title` que repetir.
interface Props {
  readonly text: string;
  readonly code: string;
}

export function Coded({ text, code }: Props) {
  return text === code ? <>{text}</> : <span title={code}>{text}</span>;
}
