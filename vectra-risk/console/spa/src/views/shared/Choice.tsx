// Una casilla o un boton de radio con su etiqueta asociada por `htmlFor` (nunca anidada): la regla `label-has-associated-control` de
// `eslint-plugin-jsx-a11y` falla en este arbol (`minimatch` 11 por el `override` de la raiz) cuando una etiqueta contiene un elemento.
import { useId } from "react";

interface Props {
  readonly type: "checkbox" | "radio";
  readonly name?: string;
  readonly value?: string;
  readonly checked: boolean;
  readonly onChange: (checked: boolean) => void;
  readonly text: string;
}

export function Choice({ type, name, value, checked, onChange, text }: Props) {
  const id = useId();
  return (
    <div className="choice">
      <input
        id={id}
        type={type}
        {...(name === undefined ? {} : { name })}
        {...(value === undefined ? {} : { value })}
        checked={checked}
        onChange={(event) => {
          onChange(event.target.checked);
        }}
      />
      <label htmlFor={id}>{text}</label>
    </div>
  );
}
