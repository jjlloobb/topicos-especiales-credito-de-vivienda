// La lista de frases prohibidas de U0 (`contracts/forbidden-phrases.yaml`) con la MISMA normalizacion que `contracts/tools/forbidden_phrases.py`:
// sin tildes (NFD) y en minusculas, frase completa entre limites de palabra.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const VECTRA_RISK = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");

export function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Mn}/gu, "")
    .toLowerCase();
}

export function forbiddenPatterns(): [string, RegExp][] {
  const phrases = (parse(readFileSync(resolve(VECTRA_RISK, "contracts", "forbidden-phrases.yaml"), "utf-8")) as { phrases: string[] }).phrases;
  return phrases.map((phrase) => [phrase, new RegExp(`\\b${normalize(phrase).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`)]);
}

/** Todas las cadenas de un catalogo JSON, con su ruta. */
export function allStrings(node: unknown, path = ""): [string, string][] {
  if (typeof node === "string") return [[path, node]];
  if (typeof node !== "object" || node === null) return [];
  return Object.entries(node).flatMap(([key, child]) => allStrings(child, path === "" ? key : `${path}.${key}`));
}

export function violations(text: string, patterns = forbiddenPatterns()): string[] {
  const normalized = normalize(text);
  return patterns.filter(([, pattern]) => pattern.test(normalized)).map(([phrase]) => phrase);
}
