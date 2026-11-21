// El selector de tema (enmienda del 2026-11-21 a NFR-U10-51): «Sistema» (por omision), «Claro» u «Oscuro», junto al de idioma. El icono del
// boton es el del tema elegido y acompana al texto, no lo sustituye. Elegir cambia el tema ya, sin recargar, y guarda la preferencia
// (`theme/theme.ts`).
import { ui } from "../../i18n";
import { chooseTheme, THEMES } from "../../theme/theme";
import { useTheme } from "../../theme/useTheme";
import { IconMoon, IconSun, IconSystem } from "./icons";
import { PreferenceSelect } from "./PreferenceSelect";

const NAMES = { system: "theme_system", light: "theme_light", dark: "theme_dark" } as const;
const ICONS = { system: IconSystem, light: IconSun, dark: IconMoon } as const;

export function ThemeSelect({ onBrand = false }: { readonly onBrand?: boolean }) {
  const theme = useTheme();
  const CurrentIcon = ICONS[theme];
  return (
    <PreferenceSelect
      label={ui("theme_label")}
      icon={<CurrentIcon />}
      options={THEMES.map((id) => ({ id, text: ui(NAMES[id]) }))}
      selected={theme}
      onChange={chooseTheme}
      onBrand={onBrand}
    />
  );
}
