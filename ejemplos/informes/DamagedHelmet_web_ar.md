# Informe de auditoría MeshAudit — DamagedHelmet.glb

- **Perfil:** Web/AR
- **Semáforo:** amarillo
- **Ruta:** rapida · **Modelo:** gemma4:e2b · **Caché:** exacta
- **Dimensión máxima:** 2.0 m · **Caras:** 15452 · **Triángulos:** 15452

Web/AR: 1 hallazgo (1 menor); 1 informativo

## Hallazgos

### h1 · V4 · Aristas no manifold (compartidas por más de dos caras) (menor)

- Medido: `7 aristas` · Límite: `0`

Se detectaron aristas no manifold (compartidas por más de dos caras). Esto es importante para la limpieza de la malla [blender_manual_seleccion:non-manifold#1].

**Pasos de corrección:**
1. Seleccionar la geometría no manifold [blender_manual_seleccion:non-manifold#1].

> **Fuente:** blender_manual_limpieza — Limpiar (`blender_manual_limpieza:limpiar#1`, puntaje 0.5849)
>
> These operators can automatically clean up certain types of messy geometry.

### h2 · V10 · Vértices duplicados (informativo)

- Medido: `205 vértices` · Límite: `0`

---
_Informe generado por un modelo; puede contener errores._

Traza: `24989f955e884b0981e3b21f79b4d3d5`