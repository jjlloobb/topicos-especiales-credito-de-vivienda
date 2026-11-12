// NFR-U10-43, 53 y 64; BR-U10-05 y 11. Configuracion plana (P-1 de U10-T01): ESLint 10 no admite `.eslintrc`.
import parser from "@typescript-eslint/parser";
import jsxA11y from "eslint-plugin-jsx-a11y";
import react from "eslint-plugin-react";

const restrictedStorage = ["localStorage", "sessionStorage"];
// Excepcion acotada (decision del usuario, 2026-11-12): UN solo archivo puede usar `sessionStorage`, el que crea el `stateStore` del login
// por redireccion (solo `state`, `code_verifier` y `nonce`; nunca tokens). `localStorage` sigue prohibido tambien ahi.
const LOGIN_STATE_FILE = "src/auth/loginStateStorage.ts";
const storageGlobals = (names) => names.map((name) => ({ name, message: "BR-U10-05: nada de almacenamiento del navegador." }));
const storageProperties = (names) =>
  ["window", "globalThis", "self"].flatMap((object) =>
    names.map((property) => ({ object, property, message: "BR-U10-05: nada de almacenamiento del navegador." })),
  );
// Atributos cuyo valor lo ve o lo lee una persona (o un lector de pantalla): no pueden ser literales (NFR-U10-53).
const VISIBLE_ATTRIBUTES = ["aria-label", "aria-description", "aria-placeholder", "aria-roledescription", "aria-valuetext", "title", "alt", "placeholder", "label"];

export default [
  {
    files: ["src/**/*.{ts,tsx}", "tests/**/*.{ts,tsx}", "vite.config.ts", "playwright.config.ts"],
    languageOptions: { parser, parserOptions: { ecmaFeatures: { jsx: true } } },
  },
  {
    // `eslint-fixtures` son entradas que **deben** fallar; `npm run lint` las excluye y `eslint.test.ts` las pasa por la API.
    files: ["src/**/*.{ts,tsx}", "tests/unit/eslint-fixtures/**/*.{ts,tsx}"],
    plugins: { react, "jsx-a11y": jsxA11y },
    settings: { react: { version: "19.3" } },
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
      // BR-U10-11: nada de HTML sin sanear.
      "react/no-danger": "error",
      // NFR-U10-53: todo texto visible viene del catalogo i18n, no de un literal en JSX.
      // `ignoreProps` deja pasar los atributos que no son texto (`role`, `id`, `htmlFor`, `href`): candidata U10-T01 F-01. Los atributos que
      // SI son texto visible o leido (`aria-label`, `title`, `alt`, `placeholder`) los cubre `no-restricted-syntax`, mas abajo.
      "react/jsx-no-literals": ["error", { noStrings: true, ignoreProps: true }],
      // BR-U10-05: los tokens solo viven en memoria.
      "no-restricted-globals": [
        "error",
        ...storageGlobals(restrictedStorage),
        { name: "parseFloat", message: "Usa decimal.js con Decimal4." },
      ],
      "no-restricted-properties": ["error", ...storageProperties(restrictedStorage)],
      // NFR-U0-34 (mismas reglas que `contracts/ts/eslint.config.mjs`): los decimales son cadenas.
      "no-restricted-syntax": [
        "error",
        { selector: "CallExpression[callee.name='Number']", message: "Prohibido Number() sobre tipos Decimal*." },
        {
          selector: `JSXAttribute[name.name=/^(${VISIBLE_ATTRIBUTES.join("|")})$/] > Literal`,
          message: "NFR-U10-53: un atributo que se lee o se ve (aria-label, title, alt, placeholder...) sale del catalogo i18n.",
        },
        {
          selector: "MemberExpression[object.name='Number'][property.name='parseFloat']",
          message: "Usa decimal.js con Decimal4.",
        },
      ],
    },
  },
  {
    // La excepcion: este archivo (y solo este) puede nombrar `sessionStorage`. Las demas reglas y `localStorage` siguen.
    files: [LOGIN_STATE_FILE],
    rules: {
      "no-restricted-globals": ["error", ...storageGlobals(["localStorage"]), { name: "parseFloat", message: "Usa decimal.js con Decimal4." }],
      "no-restricted-properties": ["error", ...storageProperties(["localStorage"])],
    },
  },
];
