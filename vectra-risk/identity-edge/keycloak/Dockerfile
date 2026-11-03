# Imagen de Keycloak de U2 (INF-U2-08). Contexto de construccion: identity-edge/keycloak/.
# La construye, escanea y firma supply-chain.yml (U1); aqui no se construye.
FROM quay.io/keycloak/keycloak:26.8.1@sha256:3f3c5f8e03c614774b4bd9173b88391fefa4153bfc010d8012d59ad825377332

COPY --chown=keycloak:keycloak themes/vectra /opt/keycloak/themes/vectra

RUN /opt/keycloak/bin/kc.sh build \
    --db=postgres \
    --health-enabled=true \
    --metrics-enabled=true \
    --cache=ispn

# Usuario que ya declara la imagen base; lo exige el escaneo de supply-chain.yml (U1).
USER 1000

ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
CMD ["start", "--optimized"]
