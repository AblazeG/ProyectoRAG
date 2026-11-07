"""Juez LLM (mistral-small3.2:24b) con rúbrica 0–5 de fidelidad y relevancia.

Se llama a Ollama directamente: es una herramienta de evaluación, no parte del
servicio. En modo falso no hay juez y las columnas quedan vacías.
"""
from __future__ import annotations

import json

RUBRICA = """Evalúa la respuesta de un auditor de modelos 3D. Devuelve JSON con tres enteros de 0 a 5:
- fidelidad: 5 si toda afirmación está respaldada por los fragmentos entregados; penaliza
  cualquier afirmación que no esté en ellos (0 si inventa).
- relevancia: 5 si explica el hallazgo y da pasos útiles para corregirlo; 0 si no responde.
- espanol: 5 si está en un español correcto y natural; 0 si no está en español.
No premies la longitud. Responde solo el JSON."""

_ENTERO = {"type": "integer", "minimum": 0, "maximum": 5}
ESQUEMA = {"type": "object",
           "properties": {"fidelidad": _ENTERO, "relevancia": _ENTERO, "espanol": _ENTERO},
           "required": ["fidelidad", "relevancia", "espanol"]}


class Juez:
    def __init__(self, modelo: str = "mistral-small3.2:24b", url: str = "http://127.0.0.1:11434"):
        import httpx
        self.modelo = modelo
        self.url = url.rstrip("/")
        self.http = httpx.Client(timeout=180, trust_env=False)

    def calificar(self, tarea: str, respuesta: str, fragmentos: list[str]) -> dict | None:
        contexto = "\n\n".join(f"[{i + 1}] {f}" for i, f in enumerate(fragmentos)) or "(sin fragmentos)"
        mensajes = [{"role": "system", "content": RUBRICA},
                    {"role": "user", "content": f"Tarea: {tarea}\n\nFragmentos:\n{contexto}\n\n"
                                                f"Respuesta a evaluar:\n{respuesta}"}]
        try:
            r = self.http.post(f"{self.url}/api/chat", json={
                "model": self.modelo, "messages": mensajes, "stream": False, "format": ESQUEMA,
                "options": {"temperature": 0, "seed": 42, "num_ctx": 8192}, "keep_alive": "30m"})
            r.raise_for_status()
            return json.loads(r.json()["message"]["content"])
        except Exception:  # noqa: BLE001
            return None


class SinJuez:
    modelo = None

    def calificar(self, *args, **kwargs):
        return None


def crear_juez(activo: bool, modelo: str, url: str):
    return Juez(modelo, url) if activo else SinJuez()
