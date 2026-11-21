// Un selector de preferencia de la cabecera (idioma, tema): un `Select` de React Aria, es decir, un boton con el valor en curso que despliega
// una lista (`listbox`), operable con teclado (Enter, flechas, Escape) y con lector de pantalla (el nombre del boton incluye el valor elegido
// y la opcion elegida lleva `aria-selected`). El boton hereda el objetivo tactil de 44 px de `button`; las opciones tambien lo cumplen.
import type { ReactNode } from "react";
import { Button, ListBox, ListBoxItem, Popover, Select, SelectValue } from "react-aria-components";
import { IconExpand } from "./icons";

export interface PreferenceOption<T extends string> {
  readonly id: T;
  readonly text: string;
  /** El idioma del texto, si no es el de la pagina (los nombres de los idiomas van cada uno en el suyo). */
  readonly lang?: string;
}

interface Props<T extends string> {
  /** El nombre accesible del control. */
  readonly label: string;
  readonly icon: ReactNode;
  readonly options: readonly PreferenceOption<T>[];
  readonly selected: T;
  readonly onChange: (value: T) => void;
  /** Sobre el fondo verde de la cabecera (boton transparente con borde claro). */
  readonly onBrand: boolean;
}

export function PreferenceSelect<T extends string>({ label, icon, options, selected, onChange, onBrand }: Props<T>) {
  return (
    <Select
      className="pref-select"
      aria-label={label}
      selectedKey={selected}
      onSelectionChange={(key) => {
        const next = options.find((option) => option.id === key);
        if (next !== undefined) onChange(next.id);
      }}
    >
      <Button className={onBrand ? "pref-button button-on-brand" : "pref-button"}>
        {icon}
        <SelectValue />
        <IconExpand />
      </Button>
      <Popover className="pref-popover">
        <ListBox>
          {options.map((option) => (
            <ListBoxItem key={option.id} id={option.id} textValue={option.text} {...(option.lang === undefined ? {} : { lang: option.lang })}>
              {option.text}
            </ListBoxItem>
          ))}
        </ListBox>
      </Popover>
    </Select>
  );
}
