"""C7: adaptadores de Ollama probados con httpx.MockTransport."""
import json

import httpx
import pytest

from servicio.datos.ollama import ChatOllama, EmbeddingsOllama, SondaOllama
from servicio.dominio import (ErrorConexion, ErrorRespuestaModelo, ErrorServidorModelo,
                              ErrorTiempoLimite, ModeloInexistente)


def cliente(manejador):
    return httpx.Client(transport=httpx.MockTransport(manejador))


def test_chat_envia_opciones_y_lee_tokens():
    recibido = {}

    def manejador(peticion):
        recibido.update(json.loads(peticion.content))
        return httpx.Response(200, json={
            "model": "gemma4:e2b", "message": {"role": "assistant", "content": '{"a":1}'},
            "prompt_eval_count": 120, "eval_count": 30, "total_duration": 2_000_000})

    chat = ChatOllama("gemma4:e2b", cliente=cliente(manejador))
    esquema = {"title": "X", "type": "object"}
    g = chat.generar([{"role": "user", "content": "hola"}], esquema, 45)
    assert g.texto == '{"a":1}' and g.tokens_entrada == 120 and g.tokens_salida == 30
    assert g.duracion_ms == pytest.approx(2.0)
    assert recibido["options"] == {"temperature": 0.1, "seed": 42, "num_ctx": 8192}
    assert recibido["format"] == esquema
    assert recibido["think"] is False
    assert recibido["keep_alive"] == "30m"
    assert recibido["stream"] is False


@pytest.mark.parametrize("modelo,think", [("gpt-oss:20b", "low"), ("qwen3:8b", False),
                                          ("mistral-small3.2:24b", None)])
def test_nivel_de_razonamiento(modelo, think):
    cuerpo = ChatOllama(modelo, cliente=cliente(lambda p: None)).cuerpo([], None)
    assert cuerpo.get("think") == think
    assert "format" not in cuerpo


@pytest.mark.parametrize("respuesta,error", [
    (lambda p: httpx.Response(404, json={"error": "model not found"}), ModeloInexistente),
    (lambda p: httpx.Response(500), ErrorServidorModelo),
    (lambda p: httpx.Response(503), ErrorServidorModelo),
    (lambda p: httpx.Response(400), ErrorRespuestaModelo),
    (lambda p: httpx.Response(200, text="no json"), ErrorRespuestaModelo),
])
def test_chat_traduce_errores_http(respuesta, error):
    with pytest.raises(error):
        ChatOllama("m", cliente=cliente(respuesta)).generar([], None, 1)


def test_chat_traduce_timeout_y_conexion():
    def timeout(p):
        raise httpx.ReadTimeout("lento", request=p)

    def caida(p):
        raise httpx.ConnectError("rechazada", request=p)

    with pytest.raises(ErrorTiempoLimite):
        ChatOllama("m", cliente=cliente(timeout)).generar([], None, 1)
    with pytest.raises(ErrorConexion):
        ChatOllama("m", cliente=cliente(caida)).generar([], None, 1)


def test_embeddings_prefijos_nomic_y_lotes():
    entradas = []

    def manejador(p):
        cuerpo = json.loads(p.content)
        entradas.append(cuerpo["input"])
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2]] * len(cuerpo["input"])})

    emb = EmbeddingsOllama("nomic-embed-text", cliente=cliente(manejador), lote=2)
    v = emb.vectorizar(["a", "b", "c"], "documento")
    assert len(v) == 3 and len(entradas) == 2
    assert entradas[0] == ["search_document: a", "search_document: b"]
    emb.vectorizar(["q"], "consulta")
    assert entradas[-1] == ["search_query: q"]


def test_embeddings_sin_prefijo_en_otros_modelos_y_errores():
    vistos = []

    def manejador(p):
        vistos.append(json.loads(p.content)["input"])
        return httpx.Response(200, json={"embeddings": [[1.0]]})

    EmbeddingsOllama("bge-m3", cliente=cliente(manejador)).vectorizar(["x"], "consulta")
    assert vistos == [["x"]]
    with pytest.raises(ModeloInexistente):
        EmbeddingsOllama("m", cliente=cliente(lambda p: httpx.Response(404))).vectorizar(["x"], "consulta")
    with pytest.raises(ValueError):
        EmbeddingsOllama("m", cliente=cliente(manejador)).vectorizar(["x"], "otro")


def test_sonda_ollama():
    ok = cliente(lambda p: httpx.Response(200, json={"models": [
        {"name": "gemma4:e2b"}, {"name": "nomic-embed-text:latest"}]}))
    estado = SondaOllama("http://x", ["gemma4:e2b", "nomic-embed-text"], cliente=ok).comprobar()
    assert estado["ok"] is True
    falta = SondaOllama("http://x", ["gpt-oss:20b"], cliente=ok).comprobar()
    assert falta["ok"] is False and falta["modelos"]["gpt-oss:20b"] is False

    def caida(p):
        raise httpx.ConnectError("x", request=p)
    assert SondaOllama("http://x", ["a"], cliente=cliente(caida)).comprobar()["ok"] is False
