# Diseño de un agente inteligente con PEAS: MeshAudit

**Proyecto base:** MeshAudit, auditor técnico de modelos 3D con normas citadas, ejecutado de forma local.
**Marco:** descripción PEAS y propiedades del entorno de Russell y Norvig (2021, cap. 2).

---

## 1. El proyecto y el problema que resuelve el agente

Antes de entregar un modelo 3D, alguien tiene que comprobar que sirve para su destino:

- un personaje para animación necesita topología de cuadriláteros;
- una pieza para impresión 3D debe ser cerrada y medir en milímetros;
- un modelo para un juego móvil debe respetar un presupuesto de triángulos;
- un archivo glTF para la web debe estar en metros y pesar poco.

Hoy esa revisión la hace un experto (un docente o un supervisor técnico) consultando normas
repartidas en el manual de Blender, la documentación de Godot y la especificación glTF. Los errores
se descubren tarde, cuando corregirlos es más caro.

**MeshAudit** es un agente que recibe un archivo de malla (OBJ, GLB, STL o PLY) y un perfil de
destino, y entrega un **informe de auditoría**. El informe trae:

- un semáforo (rojo, amarillo o verde);
- cada hallazgo con su gravedad y el valor medido frente al límite del perfil;
- la norma que lo respalda, citada con documento y sección;
- los pasos de corrección.

Como función secundaria, responde preguntas de seguimiento sobre un informe ya generado.

Su decisión de diseño central es que **el modelo de lenguaje nunca mide**:

- un analizador determinista calcula todas las métricas de la geometría;
- un sistema RAG recupera la norma que aplica a cada hallazgo;
- el modelo de lenguaje solo explica y redacta la corrección a partir de esa norma.

Así el informe no contiene cifras inventadas. Todo corre en un equipo local (un Mac con Apple M4 Max
y Ollama), sin servicios en la nube.

---

## 2. Matriz PEAS

| | Elemento | Contenido en MeshAudit |
|---|---|---|
| **P** | **Medida de desempeño** | **Exactitud:** recall y precisión de los hallazgos ≥ 0.95. **Fundamentación:** la sección de norma correcta entre los 5 primeros fragmentos en ≥ 85 % de los casos; fidelidad al contexto ≥ 4 de 5; citas inventadas ≤ 5 %. **Seguridad:** ≥ 90 % de entradas maliciosas o problemáticas bien manejadas, con ≤ 10 % de falsos positivos. **Latencia:** p95 ≤ 15 s en la ruta rápida, ≤ 45 s en la completa y ≤ 300 ms si el informe sale de la caché. **Privacidad:** 0 datos personales guardados. **Disponibilidad:** 0 errores 500 cuando falla un modelo. **Valor para el usuario:** tiempo ahorrado frente a un revisor humano y proporción de hallazgos calificados como útiles. |
| **E** | **Entorno** | **Usuarios:** estudiantes de animación 3D, técnicos de estudios 3D y el administrador del corpus (incluidos usuarios que intentan manipular al agente con inyección de instrucciones). **Lo que se audita:** archivos de malla en cuatro formatos, cada uno con sus limitaciones (OBJ, STL y PLY no declaran unidades). **Reglas:** cuatro perfiles de destino con sus límites (`perfiles.yaml`). **Conocimiento:** el corpus normativo (Blender, Godot, glTF, guía de entrega y rúbrica) indexado en una base vectorial. **Infraestructura:** el equipo local con Ollama, ChromaDB, SQLite y la aplicación web. |
| **A** | **Actuadores** | Entregar el informe (semáforo, hallazgos, mediciones, citas y correcciones) y exportarlo a Markdown. Responder preguntas de seguimiento con fuentes. Elegir la ruta (sin modelo, modelo rápido o modelo completo) y pedir la explicación al modelo. Reformular una consulta de búsqueda cuando la recuperación es pobre. Rechazar una entrada (HTTP 413, 415 o 422) con un mensaje seguro, enmascarar datos personales o poner en cuarentena un documento. Quitar citas inventadas y frases con cifras sin respaldo. Guardar resultados verificados en caché. Registrar trazas y métricas. Indexar o retirar normas del corpus. |
| **S** | **Sensores** | La API HTTP, que recibe el archivo, el perfil, las notas, las preguntas, los documentos y la retroalimentación del usuario. El lector de mallas (trimesh y un lector propio de caras OBJ), que convierte el archivo en vértices, caras, UV y normales. El analizador, que traduce esos datos en métricas (porcentaje de n-gons, aristas no manifold, malla cerrada, escala, etc.). El recuperador, que mide la similitud entre la consulta y los fragmentos del corpus. La respuesta del modelo, que los guardrails de salida inspeccionan. Las sondas de salud de Ollama, ChromaDB y SQLite, y el reloj (tiempos límite de 45 y 90 s). |

---

## 3. Las siete propiedades del entorno

| Propiedad | Clasificación | Justificación |
|---|---|---|
| **1. Observabilidad** | **Parcialmente observable** | La geometría sí es totalmente observable: el agente lee el archivo completo y mide cada vértice y cada cara. Pero varias cosas relevantes no las percibe. OBJ, STL y PLY no dicen en qué unidad están, así que el agente supone la del perfil, y una malla en la unidad equivocada que cae dentro del rango plausible pasa sin hallazgo. En GLB, STL y PLY no puede contar n-gons, porque esos formatos solo guardan triángulos, y marca esas verificaciones como «no medible». Tampoco observa si la norma que recuperó es la que de verdad aplica (solo ve una similitud), ni si la explicación del modelo es fiel. Por eso el informe siempre muestra el fragmento citado. |
| **2. Número de agentes** | **Un solo agente** | Ningún otro agente actúa en el mismo entorno ni compite por un objetivo propio. El usuario no es un agente con el que se negocie. Un matiz: algunos usuarios pueden comportarse de forma **adversarial** (inyección de instrucciones en las notas o en un documento del corpus). Esa amenaza se trata como entrada hostil con los guardrails E2 y E5, no como un juego entre agentes. |
| **3. Determinismo** | **Estocástico** | La parte de medición es determinista: la misma malla da siempre las mismas métricas y el mismo semáforo. Pero el resultado de una acción no está fijado por el estado: el modelo de lenguaje puede redactar distinto o inventar una cita (se reduce con temperature 0.1 y semilla 42, sin eliminarse), y Ollama puede agotar el tiempo o no tener el modelo. Por eso el agente verifica cada respuesta (S1–S3), reintenta y tiene un modelo de respaldo. |
| **4. Episódico o secuencial** | **Episódico** | Cada auditoría es un episodio completo e independiente: percibir la malla, decidir y entregar el informe. La decisión sobre una malla no cambia la siguiente. Dentro de un episodio sí hay pasos encadenados (el ciclo de agente reformula hasta 3 veces por consulta y 6 por informe, y las preguntas de seguimiento se apoyan en el informe anterior). Entre episodios solo persiste la caché, que ahorra trabajo sin alterar la decisión. |
| **5. Estático o dinámico** | **Semidinámico** | La malla no cambia mientras el agente delibera, y el corpus tampoco. Pero el desempeño sí depende del tiempo: hay metas de latencia (15 s y 45 s) y tiempos límite. Esa combinación de entorno estático y desempeño que se degrada con el tiempo es la definición de semidinámico. Además, entre episodios el administrador puede agregar o retirar normas. El agente lo detecta por la versión del corpus e invalida la caché. |
| **6. Discreto o continuo** | **Discreto** | Las percepciones son finitas: un archivo con un número finito de vértices y caras en coma flotante, un perfil de cuatro posibles y un texto acotado. El conjunto de acciones también es finito: tres rutas, tres gravedades, aprobar o rechazar, citar o declarar «sin norma». Aunque las coordenadas son reales, el agente las trata como valores medidos contra umbrales, no como un espacio continuo que recorrer. |
| **7. Conocido o desconocido** | **Conocido** | El diseñador conoce las «reglas» del entorno y el efecto de cada acción: los límites de cada perfil, las 11 verificaciones (V1–V11), qué hace cada guardrail y qué devuelve cada ruta. Lo que no se conoce de antemano (qué tan bien recupera el modelo de embeddings, qué umbral separa bien una paráfrasis de una pregunta distinta) se mide y se calibra con experimentos antes de usar el agente. No lo aprende el agente en operación. |

**Resumen:** parcialmente observable, de un solo agente, estocástico, episódico, semidinámico,
discreto y conocido.

---

## 4. Tipo de agente

### Elección: agente basado en objetivos (con modelo del entorno)

MeshAudit es un **agente basado en objetivos** que mantiene un **modelo interno del entorno**. Su
objetivo, en cada episodio, es entregar un informe en el que **cada hallazgo grave o menor quede
explicado con una norma verificada o declarado explícitamente «sin norma aplicable»**, sin una sola
cifra que no provenga de la medición.

### Por qué no es un agente más simple

- **No es reactivo simple.** Una tabla de condición-acción alcanza para partes aisladas (el enrutador aplica una regla fija: sin hallazgos, sin modelo; hasta tres menores, ruta rápida; si no, ruta completa). Pero no alcanza para el agente completo, que necesita recordar cosas que no están en la percepción actual:
  - cuántas reformulaciones le quedan en el informe (presupuesto de 6);
  - qué versión del corpus generó cada entrada de caché;
  - qué fragmentos entregó al modelo, para saber si una cita es inventada.
- **Tiene modelo del entorno.** Ese estado interno es la traza, el presupuesto del agente, la caché versionada y el manifiesto del índice. Además, como el entorno es parcialmente observable, el agente se representa lo que no ve. Por ejemplo, supone la unidad del perfil cuando el archivo no la declara.
- **Usa un objetivo explícito para decidir.** El ciclo de agente pregunta en cada paso si ya alcanzó su meta: ¿el mejor fragmento supera 0.55 y hay al menos dos sobre el umbral? Si no, actúa para acercarse (reformula la consulta) y vuelve a comprobar, hasta lograrlo o agotar el presupuesto. Lo mismo hacen los guardrails de salida: si la respuesta no cumple el objetivo (formato válido, citas reales, cifras con respaldo), el agente reintenta o corrige.

### Por qué no se eligió un agente basado en utilidad

- Hay compromisos de utilidad (calidad frente a latencia en el enrutador, precisión frente a recall en la caché semántica). Pero el agente no calcula en ejecución una función de utilidad para comparar alternativas.
- Esos compromisos se resolvieron **antes**, en el diseño (registros de decisión ADR-01 a ADR-08), y quedaron fijos como umbrales.
- Un agente basado en utilidad sería una extensión natural. Por ejemplo, elegir el modelo según la latencia esperada y la calidad medida de cada uno para ese tipo de hallazgo.

### Por qué todavía no es un agente que aprende

- El agente recibe retroalimentación (útil o no útil, por informe y por hallazgo), pero esa señal no cambia su comportamiento de forma automática.
- La revisa una persona y la convierte en nuevos casos de prueba o en ajustes de `perfiles.yaml`.
- Darle un componente de aprendizaje queda como trabajo futuro. Por ejemplo, recalibrar los umbrales con la retroalimentación acumulada.

---

## 5. Funcionamiento: percepciones, decisiones y acciones

### 5.1 Ciclo de una auditoría

| Paso | Percepción | Decisión | Acción |
|---|---|---|---|
| 1 | Llega un archivo, un perfil y unas notas por la API | ¿El archivo es válido (formato, tamaño, se puede leer)? ¿Las notas traen inyección o datos personales? | Rechazar con mensaje seguro (413, 415 o 422), o enmascarar los datos personales y continuar |
| 2 | Huella del archivo, perfil, notas y versiones activas | ¿Ya existe un informe verificado con esa misma clave? | Si existe, entregarlo desde la caché (menos de 300 ms) y terminar |
| 3 | Vértices, caras, UV y normales que entrega el lector | ¿Qué reglas del perfil se violan y con qué gravedad? | Calcular las métricas V1–V11, generar los hallazgos y fijar el semáforo |
| 4 | Número y gravedad de los hallazgos | ¿Qué ruta conviene? | Sin hallazgos: armar el informe con una plantilla. De 1 a 3 menores: modelo rápido (gemma4:e2b). Un grave o 4 o más: modelo completo (gpt-oss:20b) |
| 5 | Similitud de los fragmentos del corpus con la consulta de cada hallazgo | ¿La recuperación es suficiente (top‑1 ≥ 0.55 y al menos 2 fragmentos sobre el umbral)? | Si no, pedir al modelo rápido que reformule la consulta y buscar otra vez; al agotar el presupuesto, declarar «sin norma aplicable» |
| 6 | Estado de Ollama y reloj | ¿El modelo respondió a tiempo? | Si no, reintentar (1 y 2 s) o usar el modelo de la otra ruta como respaldo; si los dos fallan, responder 503 |
| 7 | Texto que devolvió el modelo | ¿Respeta el esquema? ¿Cada cita pertenece a los fragmentos entregados? ¿Cada cifra aparece en la norma citada? | Reintentar una vez si el formato falla, quitar citas inventadas, eliminar frases con cifras sin respaldo y añadir el aviso de contenido generado |
| 8 | Informe ya verificado | ¿Se puede guardar? (solo si superó las verificaciones y no vino del respaldo) | Guardarlo en caché, registrar la traza y las métricas, y entregarlo al usuario |
| 9 | Calificación del usuario | — | Guardar la retroalimentación ligada a la traza |

### 5.2 Ejemplo

Un estudiante sube `pieza.obj` con el perfil **Impresión 3D**:

1. **Percibe** que el archivo es un OBJ válido y que las notas no traen nada sospechoso.
2. **Mide** que la malla no es cerrada (V5) y que tiene una arista compartida por tres caras (V4). En Impresión 3D ambos hallazgos son **graves**: el semáforo es **rojo**.
3. **Decide** la ruta completa, porque hay al menos un hallazgo grave.
4. **Recupera** la norma de cada hallazgo. Para V5 encuentra la sección de la guía de entrega sobre mallas cerradas con similitud 0.78, que es suficiente. Para V4, la consulta en español recupera mal (top‑1 = 0.41), así que **reformula** a «non-manifold edge, arista compartida por más de dos caras» y obtiene 0.72.
5. **Pide** a gpt-oss:20b la explicación de los dos hallazgos en una sola llamada.
6. **Verifica** la respuesta. Una cita apunta a un fragmento que no se le entregó: la **quita** y marca ese hallazgo como «sin norma verificada».
7. **Entrega** el informe: semáforo rojo, las dos mediciones (insertadas por la plantilla, no por el modelo), la norma citada y los pasos para cerrar la malla y disolver la arista en Blender.

Los puntajes de similitud del ejemplo son ilustrativos.

### 5.3 Programa del agente (pseudocódigo)

```text
función AGENTE-MESHAUDIT(archivo, perfil, notas) devuelve informe
    estado: caché, versión del corpus, presupuesto de reformulaciones

    si no VERIFICAR-ENTRADA(archivo, notas) entonces devolver RECHAZO-SEGURO
    clave ← HUELLA(archivo, perfil, notas, versiones)
    si clave ∈ caché entonces devolver AVISO(caché[clave])

    hallazgos ← ANALIZAR-MALLA(archivo, perfil)             // determinista
    ruta ← ELEGIR-RUTA(hallazgos)                            // reglas de condición-acción
    si ruta = sin_modelo entonces devolver AVISO(PLANTILLA(hallazgos))

    para cada h en hallazgos graves o menores:
        consulta ← CONSULTA-CANÓNICA(h, perfil)
        repetir                                              // ciclo dirigido por el objetivo
            normas[h] ← RECUPERAR(consulta, k=5, perfil)
            si SUFICIENTE(normas[h]) entonces salir
            si presupuesto agotado entonces normas[h] ← SIN_NORMA; salir
            consulta ← REFORMULAR(consulta)                  // modelo rápido
    respuesta ← GENERAR(ruta, hallazgos, normas)             // con reintentos y respaldo
    respuesta ← VERIFICAR-SALIDA(respuesta, normas)          // formato, citas y cifras
    informe ← ENSAMBLAR(hallazgos, respuesta)                // las mediciones las pone la plantilla
    si informe verificado entonces caché[clave] ← informe
    devolver AVISO(informe)
```

---

## Referencias

Russell, S. y Norvig, P. (2021). *Artificial Intelligence: A Modern Approach* (4.ª ed.). Pearson. Capítulo 2, «Intelligent Agents».

Rincón Grajales, I. A. (2026). *MeshAudit: auditor técnico de modelos 3D con normas citadas, ejecutado de forma local*. Informe técnico, Universidad Politécnica de Chiapas.
