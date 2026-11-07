"""Regresiones de la revisión de C2 (orquestación), C1 (API) y T1 (métricas)."""
import pytest
from fastapi.testclient import TestClient

from servicio.composicion import crear_aplicacion
from servicio.datos.falsos import ChatFalso
from servicio.dominio import ArchivoSubido, ErrorInterno, ModeloNoDisponible
from servicio.guardrails.salida import AVISOS
from servicio.observabilidad.metricas import calcular_metricas
from tests.mallas.generar import generar
from tests.utiles import contenedor_de_prueba

MALLAS = generar()


def malla(nombre, como=None):
    return ArchivoSubido(como or f"{nombre}.obj", MALLAS[nombre].read_bytes())


def test_modelos_caidos_no_dejan_un_sin_norma_en_cache(tmp_path):
    caidos = {"rapido": ChatFalso("r", falla="timeout"), "completo": ChatFalso("c", falla="timeout")}
    c = contenedor_de_prueba(tmp_path, chats=caidos)
    try:
        inf = c.auditor.auditar(malla("cubo_abierto"), "impresion_3d")
    except ModeloNoDisponible:
        inf = None
    if inf is not None:   # ningún modelo explicó: plantilla y aviso automático
        assert inf["modelo"] == "plantilla" and inf["aviso"] == AVISOS[("informe", False)]
    c.extras["chats"]["rapido"].falla = c.extras["chats"]["completo"].falla = None
    assert c.auditor.auditar(malla("cubo_abierto"), "impresion_3d")["cache"] != "exacta"


def test_sin_norma_sin_modelo_es_plantilla(tmp_path):
    c = contenedor_de_prueba(tmp_path)
    inf = c.auditor.auditar(malla("prisma_ngon"), "animacion")   # V1 sin norma en el corpus falso
    assert inf["modelo"] == "plantilla" and not inf["uso_respaldo"]
    assert inf["aviso"] == AVISOS[("informe", False)]


def test_respaldo_solo_cuenta_si_explico_y_no_se_guarda(tmp_path):
    c = contenedor_de_prueba(tmp_path, chats={"rapido": ChatFalso("r", falla="timeout")})
    inf = c.auditor.auditar(malla("cubo_aleta"), "animacion")      # ruta rápida con explicación
    assert inf["uso_respaldo"] and inf["modelo"] == "falso-gpt-oss:20b"
    c.extras["chats"]["rapido"].falla = None
    otra = c.auditor.auditar(malla("cubo_aleta"), "animacion")
    assert otra["cache"] == "ninguna" and not otra["uso_respaldo"]


def test_cache_exacta_usa_el_nombre_actual_y_sin_respaldo_heredado(tmp_path):
    c = contenedor_de_prueba(tmp_path)
    c.auditor.auditar(malla("cubo_aleta", "personaje_final.obj"), "impresion_3d")
    inf = c.auditor.auditar(malla("cubo_aleta", "otro_archivo.obj"), "impresion_3d")
    assert inf["cache"] == "exacta" and inf["archivo"] == "otro_archivo.obj"
    assert inf["uso_respaldo"] is False


def test_pregunta_vacia_es_422(tmp_path):
    c = contenedor_de_prueba(tmp_path)
    cli = TestClient(crear_aplicacion(c))
    inf = cli.post("/auditorias", files={"archivo": ("a.obj", MALLAS["cubo_aleta"].read_bytes())},
                   data={"perfil": "impresion_3d"}).json()
    antes = len(c.gateway.registro)
    r = cli.post(f"/auditorias/{inf['auditoria_id']}/preguntas", json={"pregunta": "   "})
    assert r.status_code == 422 and "detalle" in r.json() and len(c.gateway.registro) == antes


def test_error_inesperado_responde_con_traza_y_aviso(tmp_path, monkeypatch):
    c = contenedor_de_prueba(tmp_path)

    def roto(*a, **k):
        raise RuntimeError("fallo imprevisto")
    monkeypatch.setattr(c.auditor.analizador, "analizar_malla", roto)
    with pytest.raises(ErrorInterno):
        c.auditor.auditar(malla("cubo_aleta"), "impresion_3d")
    r = TestClient(crear_aplicacion(c)).post(
        "/auditorias", files={"archivo": ("a.obj", MALLAS["cubo_aleta"].read_bytes())},
        data={"perfil": "impresion_3d"})
    assert r.status_code == 500 and r.json()["traza_id"] and r.json()["aviso"]
    assert c.trazas.buscar(r.json()["traza_id"])["estado"] == "error"


def test_cita_del_informe_en_cache_apunta_a_la_auditoria_actual(tmp_path):
    c = contenedor_de_prueba(tmp_path)
    a1 = c.auditor.auditar(malla("cubo_aleta"), "impresion_3d")
    c.preguntas.preguntar(a1["auditoria_id"], "¿Por qué el informe salió en rojo?")
    a2 = c.auditor.auditar(malla("cubo_aleta"), "impresion_3d")
    r = c.preguntas.preguntar(a2["auditoria_id"], "¿Por qué el informe salió en rojo?")
    assert a1["auditoria_id"] not in str(r)


def test_latencia_por_capa_se_suma_por_traza():
    traza = {"tipo": "auditoria", "tiempos_ms": {"guardrails_entrada": 12, "guardrails_salida": 6,
                                                  "contexto_rag": 50},
             "llamadas": [{"ruta": "agente", "duracion_ms": 30, "ok": True, "modelo": "m"}]}
    m = calcular_metricas([traza])
    assert m["latencia_ms"]["por_capa"]["C3"] == {"n": 1, "media": 18.0, "p50": 18.0, "p95": 18.0}
    assert m["latencia_ms"]["por_capa"]["C5"]["media"] == 20.0
    assert m["latencia_ms"]["por_capa"]["C6"]["media"] == 30.0
