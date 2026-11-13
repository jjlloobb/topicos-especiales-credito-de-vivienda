// BR-U10-10 (la prueba de ejemplo obligatoria de PBT-10, como propiedad): para toda combinacion de filtros, la URL de la bandeja no contiene
// datos del solicitante. Ninguna clave ni valor sale de `applicant_display` ni de la solicitud: las claves son un conjunto cerrado y los valores
// salen de un conjunto cerrado (estados, canales conocidos, fechas, un entero). Y la lectura de una URL arbitraria nunca deja entrar texto libre.
import { CASE_STATES } from "@vectra/contracts";
import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { type InboxFilter, KNOWN_CHANNELS, parseFilter, toQuery, toSearchParams } from "../../../../src/views/cases/filters";
import { pbtOptions } from "../../../support/pbt";

const KEYS = new Set(["state", "channel", "from", "to", "frozen", "page"]);
const isoDay = fc.integer({ min: 0, max: 20_000 }).map((days) => new Date(days * 86_400_000).toISOString().slice(0, 10));

const filters: fc.Arbitrary<InboxFilter> = fc.record({
  states: fc.option(fc.subarray([...CASE_STATES], { minLength: 1 }), { nil: null }),
  channel: fc.option(fc.constantFrom(...KNOWN_CHANNELS), { nil: null }),
  createdFrom: fc.option(isoDay, { nil: null }),
  createdTo: fc.option(isoDay, { nil: null }),
  frozenAfter: fc.boolean(),
  page: fc.integer({ min: 1, max: 10_000 }),
});

// El texto del solicitante: un nombre, un correo, un texto libre con `<script>`; nada de esto puede llegar a la URL.
const PERSONAL = fc.oneof(
  fc.constantFrom("Ana María Gómez", "ana.gomez@example.com", "1020304050", "<script>alert(1)</script>", "Cra 7 # 45-10"),
  fc.string({ minLength: 3, maxLength: 24 }).filter((text) => !/^[a-z_0-9-]+$/.test(text)),
);

describe("la URL de la bandeja (BR-U10-10)", () => {
  it("para toda combinacion de filtros: claves de un conjunto cerrado, valores de un conjunto cerrado, y ida y vuelta exacta", () => {
    fc.assert(
      fc.property(filters, PERSONAL, (filter, personal) => {
        const params = toSearchParams(filter);
        for (const [key, value] of params) {
          expect(KEYS.has(key), `clave ${key}`).toBe(true);
          expect(value).not.toContain(personal);
          expect(/^(?:[a-z_]+|\d{4}-\d{2}-\d{2}|\d{1,5}|1)$/.test(value), `valor ${value}`).toBe(true);
        }
        expect(toSearchParams(parseFilter(params)).toString()).toBe(params.toString());
        expect(Object.keys(toQuery(filter)).every((key) => ["state", "channel", "created_from", "created_to", "model_frozen_after_recommendation", "page", "page_size"].includes(key))).toBe(true);
      }),
      pbtOptions("PBT URL de la bandeja"),
    );
  });

  it("una URL arbitraria (con texto personal en cualquier clave o valor) se lee sin dejar entrar texto libre", () => {
    fc.assert(
      fc.property(fc.array(fc.tuple(fc.oneof(fc.constantFrom("state", "channel", "from", "to", "frozen", "page", "q", "nombre"), fc.string({ maxLength: 8 })), PERSONAL)), (pairs) => {
        const params = new URLSearchParams();
        for (const [key, value] of pairs) params.append(key, value);
        const filter = parseFilter(params);
        const out = toSearchParams(filter);
        for (const [key, value] of out) {
          expect(KEYS.has(key)).toBe(true);
          expect(pairs.some(([, personal]) => personal === value && !/^[a-z_0-9-]+$/.test(personal))).toBe(false);
        }
        expect(filter.page).toBeGreaterThanOrEqual(1);
        expect(filter.page).toBeLessThanOrEqual(10_000);
      }),
      pbtOptions("PBT URL de la bandeja (lectura)"),
    );
  });
});
