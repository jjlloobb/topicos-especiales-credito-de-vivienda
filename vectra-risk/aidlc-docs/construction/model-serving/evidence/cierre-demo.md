# Cierre de U6 con alcance acotado a la demo

Esta tarea (U06-T02) crea el archivo solo con la sección «Diferido por la demo»; el resto del cierre (lo comprobado en kind, lo no comprobado, quién ejecutó) es de U06-T03.

## Diferido por la demo

Lista que acepta `platform/tests/test_traceability.py --unit model-serving --all` (P-4, `demo-recorte-funcional.md` §2.4 y §6). Cada fila lleva el identificador, el paso del plan que lo implementaría y la cita del recorte. Un identificador de esta lista **no** puede tener código ni prueba: si los tiene, la prueba falla y se quita de aquí. Los Pasos 6, 7, 8 y 10 no aparecen: son de U06-T02 y se trazan en el chart, las políticas, las pruebas y el `Makefile`. El Paso 9 (alertas, runbooks, `ServiceMonitor`) está diferido entero (T2), pero sus identificadores (P-U6-06, NFR-U6-03) ya los cita el código de U06-T01 y no necesitan fila.

| Identificador | Paso del plan | Cita del recorte | Qué falta |
|---|---|---|---|
| NFR-U6-10 | Paso 4 (benchmark local de p95 ≤ 30 ms) y Paso 11 (prueba de carga de U12 en kind) | Enmienda §3 U6; T3 | Benchmark de `:predict` (p95 ≤ 30 ms) y de `:explain` (p95 ≤ 150 ms); sin él, el valor no está medido |
| NFR-U6-12 | Paso 11 (escalado bajo 20 solicitudes/s) | Enmienda §3 U6; T3; T6 | Prueba de carga con `kubectl get hpa` en kind: los componentes escalan sin superar sus máximos. El HPA está declarado y probado sobre el render (P-U6-04, NFR-U6-11), no bajo carga |
| NFR-U6-30 | Paso 5 (firma Cosign, SBOM, Trivy) | Enmienda §3 U6, Paso 5; T1 | Firma de las imágenes, SBOM y escaneo con `supply-chain.yml` de U1; y el `kyverno test` de una imagen oficial sin firma. Las imágenes ya están pinneadas por digest, sin firmar |
