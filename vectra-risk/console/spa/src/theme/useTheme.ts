// El tema elegido dentro de React (para el selector): quien lo usa se repinta cuando cambia. Los colores no pasan por React: son CSS.
import { useSyncExternalStore } from "react";
import { getTheme, subscribeTheme, type ThemeChoice } from "./theme";

export function useTheme(): ThemeChoice {
  return useSyncExternalStore(subscribeTheme, getTheme);
}
