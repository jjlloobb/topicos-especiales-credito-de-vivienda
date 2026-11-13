# Imagen de `console-spa` (U10, Paso 17; INF-U10-02; NFR-U10-44, NFR-U10-45): nginx sin privilegios que sirve el build de Vite en el 8080.
# Contexto de construccion: la raiz de vectra-risk/ (`make -C console image-spa`): el lockfile es el `package-lock.json` raiz y `console/spa` depende del workspace `contracts/ts`.
# Dos etapas: `build` (Node por digest; el build no depende del Node de la maquina) y la final (nginx-unprivileged por digest, sin Node, sin fuentes, sin mapas y sin `.vite/`).
# Sin firma, SBOM ni escaneo (T1 de la demo) y sin push (console/README.md, seccion «Imagenes»). Las etapas de versiones anteriores estan diferidas con `version` (recorte funcional, P-15).
FROM docker.io/library/node:22-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee AS build
WORKDIR /src
# Primero solo los manifiestos: `npm ci` se repite solo cuando cambia una dependencia. `--ignore-scripts`: ninguna dependencia ejecuta codigo al instalarse (NFR-U10-44).
COPY package.json package-lock.json ./
COPY contracts/ts/package.json contracts/ts/package.json
COPY console/spa/package.json console/spa/package.json
RUN npm ci --ignore-scripts
COPY contracts/ts contracts/ts
COPY console/spa console/spa
RUN npm run -w console/spa build \
    # `build.manifest` deja `dist/.vite/manifest.json`, que solo lee `.size-limit.mjs`: no va a la imagen (la raiz servida no lo expone).
    && rm -rf console/spa/dist/.vite

FROM docker.io/nginxinc/nginx-unprivileged:stable-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03
USER 0:0
# La pagina de ejemplo de la imagen base no es parte de la SPA: `index.html` y `assets/` son solo los del build.
RUN rm -rf /usr/share/nginx/html/* /etc/nginx/conf.d
COPY console/spa/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /src/console/spa/dist/ /usr/share/nginx/html/
# Usuario numerico distinto de root (require-run-as-non-root); el mismo `runAsUser`/`runAsGroup` del chart. `config.json` no esta en la imagen: lo monta el chart (ConfigMap).
USER 101:101
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
