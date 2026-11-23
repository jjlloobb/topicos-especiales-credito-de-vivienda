# Mejoras previstas (no hechas)

Nada de esta lista está construido ni medido. Son mejoras decididas con su alcance y sus límites, para después de la sustentación.

## M-1 Dictar la justificación con un modelo de voz a texto

**Qué.** En la consola, un botón de dictado junto al campo «Justificación» del formulario de decisión de un caso y del diálogo «Resolver el congelamiento». La persona habla, un modelo de voz a texto (por ejemplo Whisper, de pesos abiertos, alojado en el clúster) escribe el borrador en el campo, y la persona lo corrige y confirma.

**Por qué encaja.** No cambia quién decide. La voz ayuda a redactar; la persona revisa el texto y firma, y lo que queda en el registro de decisiones es el texto que aprobó, no el audio. Es la misma regla del proyecto: la máquina propone, una persona aprueba.

**Límites que tendría, desde el diseño.**

- El audio no sale del clúster del banco y no se guarda: se transcribe y se descarta. El audio de una persona es un dato personal.
- Lo transcrito **no** entra al modelo de scoring ni a ninguna recomendación. Los modelos de voz aciertan menos con unos acentos que con otros; usarlos como entrada de una decisión de crédito crearía el sesgo que el monitoreo de este proyecto existe para detectar.
- El campo sigue siendo editable y obligatorio, con su límite de longitud; sin dictado, la consola funciona igual.
- El servicio de voz sería una pieza reemplazable: cambiar de modelo no toca permisos, registro ni aprobación. Tendría su propia prueba de cambio de modelo.

**Lo que falta saber antes de construirlo.** Cuánta memoria pide en CPU (el clúster kind de la demo no tiene margen: quedan entre 2,6 y 2,9 GiB libres con todo arriba; no se ha medido el modelo), la calidad con español de Colombia y vocabulario de crédito, y cómo pedir permiso de micrófono dentro de la CSP de la consola.

**Lo que se descarta.** Transcribir entrevistas o llamadas con solicitantes para llenar la solicitud (abre un frente de datos personales), y órdenes de voz al agente.
