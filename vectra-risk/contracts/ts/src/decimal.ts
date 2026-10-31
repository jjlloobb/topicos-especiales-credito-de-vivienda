import Decimal from "decimal.js";

/** Decimal con 4 decimales exactos (BR-U0-15): siempre una cadena, nunca `number`. */
export type Decimal4 = string & { readonly __decimal4: unique symbol };

const PATTERN = /^-?\d+\.\d{4}$/;

export function parseDecimal4(value: string): Decimal4 {
  if (!PATTERN.test(value)) {
    throw new Error("Decimal4 invalido");
  }
  return value as Decimal4;
}

export function toDecimal(value: Decimal4): Decimal {
  return new Decimal(value);
}

export function fromDecimal(value: Decimal): Decimal4 {
  return value.toFixed(4, Decimal.ROUND_HALF_UP) as Decimal4;
}
