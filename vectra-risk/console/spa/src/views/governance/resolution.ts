// La justificacion de una resolucion (BR-U10-13): obligatoria en las tres acciones, de 1 a 2000 caracteres (`FrozenResolutionIn`:
// `min_length = 1`, `max_length = 2000`, contados en puntos de codigo). La SPA ademas pide que no sea solo espacios.
export const RESOLUTION_MAX = 2000;

export function justificationOk(text: string): boolean {
  return text.trim() !== "" && [...text].length <= RESOLUTION_MAX;
}
