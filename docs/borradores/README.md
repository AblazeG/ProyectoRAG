# Borradores de los documentos propios del corpus

`guia_entrega.md` y `rubrica_animacion.md` son **borradores redactados por Claude Code**. Su
propósito es que tengas la estructura y las secciones que esperan los punteros `norma` de
`config/perfiles.yaml`. No son documentos tuyos todavía: revísalos, corrige lo que no coincida con
tu curso o tu taller y reescríbelos con tus palabras antes de ingerirlos.

## Qué conservar

- **Los títulos de sección (`##`) exactos.** Son los que buscan la evaluación y los punteros:
  - Guía: Mallas cerradas, Geometría no manifold, Escala y volumen de impresión, Caras degeneradas, Normales invertidas y Tamaño de archivo para web.
  - Rúbrica: Topología para deformación.
- **Los límites, para que coincidan con `perfiles.yaml`:**
  - Impresión: 1–300 mm.
  - Web: 10 MB.
  - Móvil: 20 000 triángulos (y 100 000 en web).
  - Animación: 0 n-gons y como máximo 10 % de triángulos.

  Si cambias un límite en el texto, cámbialo también en `perfiles.yaml`.
- **El front matter** (`doc_id`, `licencia: propio`, `perfiles`).

## Secciones nuevas

- **Guía, «Presupuesto de triángulos para juego móvil»:** respalda el límite de 20 000 de V3, que la documentación de Godot no da. Puedes apuntar V3 a esta sección en `perfiles.yaml` (perfiles `juego_movil` y `web_ar`).
- **Rúbrica, «Bucles de aristas en articulaciones», «Escala, orientación y origen» y «Mapa UV y nombres»:** ninguna verificación apunta a ellas. Son contexto adicional; quítalas si no aplican.

## Cómo ingerirlos

```bash
cp docs/borradores/guia_entrega.md docs/borradores/rubrica_animacion.md corpus/
python -m servicio.ingestar corpus/
```

Después repite las fases 6–8 de `docs/PRUEBAS_LOCALES.md` y vuelve a generar los insumos con
`python -m evaluacion.insumos_informe --resultados evaluacion/resultados/ --corpus corpus/`.

## Efecto medido con los borradores

La medición se hizo con bge-m3 en un índice temporal; el corpus real no se tocó. El acierto@5 de las 30 consultas sube de 0.23 a 0.60, y en las 14 consultas que apuntan a estos dos documentos llega a 0.93.

**La cifra es optimista:** los borradores se escribieron conociendo las consultas de prueba. Cuando los reescribas con tus palabras, mide de nuevo. Si los usas tal como están, decláralo en la sección 10.3 del informe.
