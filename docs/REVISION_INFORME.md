# Revisión del informe técnico contra el producto

Revisión de `docs/Informe_tecnico_MeshAudit.pdf` (35 páginas) contra el código de esta rama. Tiene
cuatro partes:

1. Lo que se comprobó y coincide.
2. Los pasajes del informe que ya no describen al producto, con el texto propuesto.
3. La declaración de uso de asistentes de IA (sección 10.3), que hay que corregir.
4. Cómo se llenan los «[Pendiente]» y las tablas con «?».

## 1. Lo que coincide

Se revisó cada cifra y cada nombre que el informe da como parte del diseño:

- **Arquitectura (sección 4):** capas C1–C7, T1 y T2, `PERMITIDOS` del código 2, puertos del código 1, raíz de composición y segundo adaptador vectorial en memoria. La prueba de arquitectura lo verifica por importaciones y en ejecución.
- **Flujos (sección 5, figuras 6–10):** orden de la auditoría (análisis antes del enrutador; caché de hallazgos después), ingesta con E5 antes y después de extraer, pregunta servida por la caché semántica, rechazo por inyección y ciclo de agente.
- **Parámetros:** `num_ctx` 8192, `keep_alive` 30m, tiempos límite de 45 y 90 s, 2 reintentos con esperas de 1 y 2 s, k = 5, umbral 0.55, fragmentos de 800 con solape 120, lotes de hasta 4 hallazgos, 3 reformulaciones por consulta y 6 por informe, E4 0.30, caché semántica 0.92, expiraciones de 7 días y 24 horas, 50 MB por malla, 2 000 000 de caras.
- **Tablas 10, 11, 13 y 14:** rutas del enrutador, límites y gravedades de V1–V11 por perfil (`config/perfiles.yaml`), verificaciones E1–E5 y S1–S4, y claves de la caché.
- **Conjuntos de prueba (tabla 15):** 20 casos de producto; 40 consultas de recuperación (30 relevantes y 10 sin respaldo); 23 de guardrails (4 de inyección, 3 fuera de dominio, 3 con datos personales, 3 documentos y 10 normales, 3 de ellas sobre el propio informe); 8 preguntas coloquiales del agente; 40 casos del enrutador; 5 fallas.
- **Código 4 (agente), código 5 (traza) y código 8 (respuesta de `POST /auditorias`):** mismos campos y nombres.

## 2. Pasajes que hay que actualizar

Cada punto da la ubicación en el informe, lo que dice, lo que hace el producto y un texto
propuesto. Si prefieres cambiar el producto en lugar del texto, dímelo y lo ajusto.

### 2.1 Quién prioriza los hallazgos (tabla 1 y ADR-08)
- **Dice:** «Un modelo de lenguaje prioriza, explica y redacta la corrección» (tabla 1) y «el modelo solo explica y prioriza» (ADR-08).
- **Producto:** el orden lo fija el analizador (graves, menores, informativos y, dentro de cada gravedad, por número de verificación). El modelo no lo cambia.
- **Propuesta (tabla 1):** «Un modelo de lenguaje explica cada hallazgo y redacta la corrección citando la fuente; el orden por gravedad lo fija el analizador.»
- **Propuesta (ADR-08):** «…el modelo solo explica y redacta, el orden de los hallazgos sale de su gravedad y las mediciones las inserta una plantilla.»

### 2.2 Escenas con varias mallas (tabla 4, RF9, y sección 10.1, «Formatos»)
- **Dice:** RF9 «Aceptar archivos FBX y escenas con varias mallas y rig: No tendrá»; «No se aceptan FBX ni escenas con varias mallas, esqueletos o animación».
- **Producto:** un GLB con varios nodos se acepta: C7 combina las mallas aplicando la transformación de cada nodo (y corrige el orden de las caras si es un espejo). Rechazarlos dejaría fuera casi todos los GLB exportados desde Blender.
- **Propuesta (RF9):** «Aceptar FBX y escenas con rig o animación.» (No tendrá.)
- **Propuesta (10.1):** «No se aceptan FBX, esqueletos ni animación. Un GLB con varias mallas se audita como un solo objeto, con las transformaciones de sus nodos aplicadas.»

### 2.3 Persistencia de las mallas (sección 10.1, «Privacidad»)
- **Dice:** «las mallas subidas se borran tras la auditoría salvo que el usuario pida conservarlas».
- **Producto:** se borran siempre; la API del anexo B no tiene una opción para conservarlas.
- **Propuesta:** «las mallas subidas se borran al terminar cada auditoría, y las trazas no guardan el contenido del archivo, solo su hash.»

### 2.4 Tabla 13 (verificaciones)
- **E1, política:** dice «Bloquear (HTTP 413 o 415)». El producto también responde **422** cuando el archivo no se puede leer o su contenido es inválido: más de 2 millones de caras (ya lo dice la sección 7.1.1), índices de cara fuera de rango o coordenadas NaN/infinitas.
  - **Propuesta:** «Bloquear (HTTP 413, 415 o 422).»
- **E3, detección:** dice «correo, teléfono, CURP y matrícula». El producto también reconoce RFC y números de tarjeta (con verificación de Luhn). Los teléfonos de 10 dígitos seguidos se enmascaran salvo que vayan seguidos de una unidad («1234567890 mm»).
  - **Propuesta:** «Expresiones regulares para correo, teléfono, CURP, RFC, matrícula y tarjeta; una cifra seguida de una unidad no se toma por teléfono.»
- **E5, detección:** añadir «tamaño ≤ 20 MB» y «el HTML oculto (`hidden`, `display:none`) se descarta antes de buscar patrones».
- **S3, detección:** el producto solo evalúa cifras seguidas de una unidad o de un sustantivo de conteo; versiones («glTF 2.0»), años y números de sección no cuentan.
  - **Propuesta:** añadir «…; tampoco cuentan versiones, años ni números de sección».

### 2.5 Tabla 11 (V9 y V10)
- **V9:** el producto exige volumen con signo positivo **en cada componente cerrado**, no solo en el total, para que un cuerpo pequeño invertido no quede compensado por otro grande.
  - **Propuesta:** «`is_winding_consistent` y volumen con signo > 0 en cada componente cerrado».
- **V10:** el producto cuenta vértices a distancia < 10⁻⁶ que además tienen las mismas UV y normales. Así una arista dura (`f v//vn`) o una costura de UV no cuenta como duplicado.
  - **Propuesta:** «Vértices a distancia < 10⁻⁶ con las mismas UV y normales, sobre la malla sin procesar».

### 2.6 Tabla 24 (anexo B)
- **`POST /documentos`:**
  - Añadir los códigos **409**, para un `doc_id` que ya pertenece a otro archivo, y **403**.
  - Añadir el campo de formulario `reemplazar=true`, que permite reemplazarlo a propósito.
  - Subir el mismo archivo otra vez no sube la versión del corpus.
- **`DELETE /documentos/{id}`, `POST /auditorias`, `POST /auditorias/{id}/preguntas` y `POST /retroalimentacion`:** añadir **403**. Toda petición que modifica datos con una cabecera `Origin` que no sea la de la aplicación web se rechaza. Esto impide que otra página abierta en el navegador suba o borre documentos en `127.0.0.1:8000`.
- **Sección 10.1, «Seguridad y despliegue»:** añadir al final «Las peticiones que modifican datos desde un origen distinto del de la aplicación web se rechazan (HTTP 403).»

### 2.7 Figura 4 y código 6 (módulos que no aparecen)
- **Añadir a la figura 4:**
  - `cache/informes.py` (`ArchivoInformes`, el repositorio de informes que usa C2 a través de C4);
  - `orquestacion/estado.py` (`ServicioEstado`: salud, configuración y perfiles).
- **Añadir al código 6:**
  - `config/servicio.yaml` (modelos, umbrales y tiempos límite);
  - `servicio/datos/memoria.py` (segundo adaptador vectorial) y `servicio/datos/falsos.py` (dobles de prueba);
  - `restricciones.txt` (versiones probadas);
  - `evaluacion/{comun,juez,sinteticas,plantillas,mutar_blender,insumos_informe}.py`.
- **Código 1:** el puerto `LectorMalla` tiene además `probar(ruta)`, una lectura ligera que usa E1. Como el código 1 es un «extracto», basta con dejarlo así o añadir la línea.

### 2.8 Código 7 (README)
Cambios para que coincida con el README del repositorio:
- `pip install -r requirements.txt -c restricciones.txt`. numpy 2.5 exige Python 3.12, y el archivo fija la 2.4 para 3.11.
- Un paso para las mallas de evaluación: `blender -b -P evaluacion/mutar_blender.py -- evaluacion/mallas_base evaluacion/mallas_generadas` (requiere Blender 4.2 o posterior).
- Los experimentos van **antes** que `run_eval.py`, y la evaluación se corre con `--juez`. `experimento_llm` escribe la muestra de 15 casos que el autor califica a mano para validar al juez.

### 2.9 Método de evaluación (sección 9.1 y tablas 9 y 16)
- **Juez–autor:** se reportan la diferencia media y el % de casos con diferencia ≤ 1 punto. La tabla 16 tiene una sola fila; añade «Acuerdo juez–autor (≤ 1 punto)» o pon el porcentaje en el texto.
- **«Sin RAG»:** a la salida sin contexto se le aplican los mismos S1–S3. La columna «Sin RAG» de «Cifras eliminadas por S3» sí tiene valor.
  - **Propuesta:** añadir al final de 9.1 «…pero sin fragmentos de contexto; a su salida se le aplican los mismos S1 a S3».
- **Tabla 9:** acierto y MRR se miden sin umbral, porque cada modelo tiene su propia escala de similitud.
  - **Propuesta (pie de la tabla 9):** «Acierto y MRR se calculan sobre el orden, sin umbral; el umbral 0.55 está calibrado para bge-m3.»

### 2.10 Tabla 2 (licencia de glTF)
El «[Pendiente: verificar]» depende del archivo que ingieras:
- El HTML y el PDF del registro de Khronos están bajo la **Khronos Specification License**. Permite usar y reproducir la especificación sin modificarla y sin costo, y no concede patentes ni marcas.
- Las fuentes AsciiDoc del repositorio de Khronos en GitHub están bajo **CC BY 4.0**.

El servicio ya acepta `Khronos-Specification` como licencia; antes, E5 habría puesto en cuarentena el HTML oficial. Confirma el texto vigente en el registro antes de entregar.

Fuentes consultadas:
- [Prólogo de la especificación glTF 2.0 en el registro de Khronos](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
- [Archivo de licencia de una copia del repositorio](https://github.com/javagl/glTF/blob/main/LICENSE.adoc)
- [Archivo COPYING de otra copia](https://github.com/facebook/glTF/blob/main/COPYING.adoc)

Las dos últimas son copias del repositorio oficial; contrasta con el `COPYING.adoc` de KhronosGroup/glTF.

## 3. Declaración de uso de asistentes de IA (sección 10.3)

El borrador del informe dice que Claude se usó para «generar el esqueleto del código a partir del
proyecto de ejemplo del curso». No es exacto: el código del repositorio lo escribió casi completo
Claude Code, el agente de programación de Anthropic. Eso incluye el servicio, la aplicación web, las
pruebas, la evaluación, los experimentos, los conjuntos de casos (`evaluacion/casos_*.json`), el
corpus de prueba sintético (`tests/corpus/`), los ADR, `DESVIACIONES.md` y el README. Lo escribió a
partir de la especificación del proyecto y de este informe, en sesiones en la nube, sin acceso a
Ollama, a Blender ni al Mac.

El borrador también dice que «la construcción del corpus y de los casos de prueba» es del autor. Si
usas los casos tal como están, hay que decirlo. Texto propuesto, para que lo ajustes a lo que tú
hiciste:

> Conforme a los lineamientos del proyecto, se declara el uso de asistentes de IA. Se usó Claude
> (Anthropic) para estructurar el informe, redactar borradores de secciones y dibujar los diagramas
> en TikZ. La implementación del repositorio (servicio, aplicación web, pruebas, scripts de
> evaluación y de experimentos, conjuntos de casos y documentación) la escribió Claude Code, el
> agente de programación de Anthropic, a partir de la especificación del proyecto y de este informe;
> el autor revisó el código, corrigió [qué] y ejecutó las pruebas. La idea, el dominio, las decisiones
> de arquitectura, la selección y depuración del corpus normativo, la revisión de los casos de prueba
> y de la línea base de las mallas, la ejecución de los experimentos en el equipo local y la revisión
> final son del autor, quien verificó el contenido y responde por él.

Quita o cambia lo que no corresponda; en especial, «revisó el código», «corrigió [qué]» y «revisión
de los casos de prueba» solo deben quedar si de verdad los hiciste.

## 4. «[Pendiente]» y tablas con «?»

`evaluacion/insumos_informe.py` lee los CSV de una corrida y el corpus, y escribe:

- **`INSUMOS_INFORME.md`:** un apartado por cada «[Pendiente]» del informe, en orden, con el texto propuesto y todas las tablas con «?» llenas (2, 8, 9 y 16–23). Incluye el estado de cada meta de la tabla 5, la conclusión de la sección 6.4.1, la evidencia de cada ADR, el análisis de errores (9.3) y las mejoras (9.4).
- **`tablas_informe.tex`:** las mismas filas en LaTeX, para pegarlas en los `tabular`.

Ya hay una versión **provisional** en `evaluacion/resultados/provisional_nube/`, generada con el
proveedor falso. Tras la corrida en el Mac:

```bash
python -m evaluacion.insumos_informe --resultados evaluacion/resultados/ --corpus corpus/
```

Lo que ningún script puede llenar queda marcado «DATO MANUAL»:

| Pendiente | Qué hace falta |
|---|---|
| Portada | Nombre del docente |
| 9.2, valor | Prueba del revisor independiente con cinco mallas (el archivo trae la tabla para llenarla) |
| Tabla 5, reproducibilidad | Prueba de instalación con un compañero (≤ 30 min) |
| Tabla 16, juez–autor | Calificar a mano `muestra_revision_manual.csv` (columnas `nota_autor_*`) |
| Referencias | Versión del manual de Blender que descargaste (o `version:` en `corpus/fuentes.yaml`) |
| Sección 8 | Cambiar cada ADR de «Propuesta» a «Aceptada» cuando su evidencia lo confirme |
| 10.3 | Ajustar la declaración de la sección 3 de este documento |
