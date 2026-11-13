// `app_version` de `ClientErrorReport` (BR-U10-22): el `version` de `package.json`, inyectado en el build por `vite.config.ts`.
// Con `version` (BR-U10-21) diferido, es la unica fuente. Tiene que ser SemVer (`^\d+\.\d+\.\d+$`).
export const APP_VERSION: string = __APP_VERSION__;
