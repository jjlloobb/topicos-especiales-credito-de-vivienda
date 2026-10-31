// NFR-U0-34: los decimales del contrato son cadenas; prohibido convertirlos a number.
import parser from "@typescript-eslint/parser";

export default [
  {
    files: ["src/**/*.ts", "test/**/*.ts"],
    ignores: ["src/generated/**"],
    languageOptions: { parser },
    rules: {
      "no-restricted-globals": ["error", { name: "parseFloat", message: "Usa decimal.js con Decimal4." }],
      "no-restricted-syntax": [
        "error",
        { selector: "CallExpression[callee.name='Number']", message: "Prohibido Number() sobre tipos Decimal*." },
        { selector: "MemberExpression[object.name='Number'][property.name='parseFloat']", message: "Usa decimal.js con Decimal4." },
      ],
    },
  },
];
