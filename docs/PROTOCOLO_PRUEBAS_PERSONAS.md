# Protocolos de las pruebas con personas (fase 9)

Son tres pruebas que no se pueden automatizar. Cada una indica qué preparar, qué hacer, qué anotar y adónde va el dato en el informe.

---

## 1. Valor: revisor independiente frente a MeshAudit (sección 9.2)

**Quién:** otro docente o un técnico que no diseñó las reglas de `config/perfiles.yaml` y que no haya visto los resultados de MeshAudit.

**Qué preparar:** ya está listo en `prueba_revisor/`:

| Archivo | Perfil que debe revisar | Origen (no se lo digas al revisor) |
|---|---|---|
| `malla1.obj` | Animación | base1 + M1 (escala ×1000, n-gons y triángulos) |
| `malla2.obj` | Juego móvil | base2 + M2 (malla abierta y sin UV) |
| `malla3.obj` | Juego móvil | base3 + M3 (normales invertidas y vértices duplicados) |
| `malla4.glb` | Web/AR | base4 + M4 (más de 100 000 triángulos, no manifold y texturas de 15 MB) |
| `malla5.obj` | Impresión 3D | base5 + M5 (malla abierta y caras degeneradas) |

Si borras la carpeta, se regenera copiando desde `evaluacion/mallas_generadas/`; los nombres de origen están en la tabla.

### Pasos

1. Dale al revisor las cinco mallas y una hoja con los requisitos de cada perfil. Sirve la tabla 11 del informe o la guía de entrega, pero **no** los resultados de MeshAudit.
2. Pídele que revise cada malla en Blender (o la herramienta que prefiera) y anote cada problema que encuentre. Cronometra cada malla por separado, desde que la abre hasta que termina su lista.
3. Después, audita tú cada malla con MeshAudit (`app_mac/MeshAudit.app`) en el mismo perfil. Anota el tiempo hasta que aparece el informe; está en las trazas como `tiempo_ms`, o puedes cronometrarlo.
4. Compara las listas. Un hallazgo coincide si el revisor y MeshAudit señalan el mismo problema, aunque lo llamen distinto.

**Qué anotar:** en `prueba_revisor/registro.csv`, por malla:
- Tiempo manual (min) y tiempo de MeshAudit (s).
- Número de hallazgos del revisor y cuántos de ellos encontró MeshAudit.
- Hallazgos que MeshAudit dio y el revisor no; pon cada uno en notas, porque puede ser un falso positivo o algo que el revisor pasó por alto.

**Al informe** (sección 9.2, plantilla en `evaluacion/resultados/INSUMOS_INFORME.md`):

> «El revisor tardó en promedio X min por malla; MeshAudit, Y s. De los N hallazgos del revisor, la herramienta encontró M (P %); los restantes eran aspectos que las reglas no miden, como …».

---

## 2. Reproducibilidad: instalación por un tercero (tabla 5)

**Quién:** un compañero que no haya visto el proyecto funcionando, con un Mac con Apple Silicon y al menos 32 GB de memoria.

### Antes de empezar

- Deja que descargue los modelos de Ollama por su cuenta. **El tiempo de descarga no cuenta**; anótalo aparte si quieres.
- Dale solo la URL del repositorio. Los documentos del corpus los descarga según `corpus/README.md`, o dale `corpus/` por separado y anótalo.

### Pasos

1. Pide que siga **solo el README**, sin preguntarte. Tú solo observas.
2. Cronometra desde `git clone` hasta que audita una malla en la web, sin contar las descargas.
3. Anota cada lugar donde se atoró: el paso del README, qué esperaba y qué pasó.

**Meta:** ≤ 30 min. Si no se cumple, el motivo va al informe y el arreglo, al README.

**Al informe:** tabla 5, fila «Reproducibilidad» (tiempo y si cumple), y una línea en la sección 9.2 con los atascos.

---

## 3. Demostración sin red (sección 4.5)

**Estado:** la revisión del código ya está hecha. La web y la API solo usan `localhost`, y Ollama corre con `OLLAMA_NO_CLOUD=1`. La única descarga externa posible es la de los decodificadores Draco/KTX2 del visor 3D, y solo se usaría con un GLB comprimido; las mallas de prueba no lo están.

### Pasos (con la app ya abierta una vez y los modelos descargados)

1. Apaga el Wi-Fi y desconecta el cable de red.
2. Abre `MeshAudit.app`.
3. Audita `prueba_revisor/malla5.obj` en Impresión 3D. Debe salir en rojo por la ruta completa, con explicación y cita.
4. Haz una pregunta sobre el informe, por ejemplo «¿Cómo cierro los huecos de la malla?».
5. Anota si todo funcionó y el tiempo de cada paso.

**Al informe:** sección 4.5 (o 9.2): «Se verificó una auditoría completa y una pregunta con el equipo desconectado de la red».
