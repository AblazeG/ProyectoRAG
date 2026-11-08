# Corrida provisional en la nube (2026-11-08)

Generada con el proveedor `falso` en un contenedor Linux sin GPU, sin Ollama, sin Blender y sin juez:

```bash
python -m experimentos.experimento_llm --proveedor falso --salida evaluacion/resultados/provisional_nube
for e in embeddings fragmentos cache; do
  python -m experimentos.experimento_$e --proveedor falso --salida evaluacion/resultados/provisional_nube
done
python evaluacion/run_eval.py --proveedor falso --corridas 5 --salida evaluacion/resultados/provisional_nube
```

**Estas cifras no son las del informe.** Los modelos y los embeddings son dobles de prueba
(`ChatFalso`, `EmbeddingsFalsos`), las mallas son las sintéticas de `evaluacion/sinteticas.py` y
el corpus es el de `tests/corpus/` (textos sintéticos). Son válidas para la lógica determinista
(analizador, patrones de los guardrails, caché exacta, respaldo del gateway, privacidad) y sirven
para comprobar que toda la evaluación corre de principio a fin. La calidad de las explicaciones,
la recuperación, el umbral semántico, el agente, el enrutador y las latencias de los modelos se
miden en el Mac con `--proveedor ollama --juez`.
