F-05: Corregido: prueba con timeout real del POST (carpeta creada, respuesta tarde, reintento con 409, 2 POST leidos de vuelta); N3 muere (1 failed). La prueba previa se renombro a lo que prueba.
F-06: Corregido: `test_other_folder_errors_are_raised`; N1 muere (1 failed).
F-07: Corregido: `test_server_errors_are_not_retried`; N4 muere (1 failed).
F-08: Corregido: la prueba real cuenta peticiones (==1); `import socket` movido al inicio.
F-09: Corregido: `is_timeout` en lineas cortas; `ruff format --diff` ya no menciona `is_timeout`. El resto del archivo no se reformateo.
