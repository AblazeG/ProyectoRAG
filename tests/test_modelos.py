"""C6: enrutador y gateway con dobles que fallan."""
import pytest

from servicio.datos.falsos import ChatFalso
from servicio.dominio import Hallazgo, ModeloNoDisponible
from servicio.modelos.enrutador import Enrutador
from servicio.modelos.gateway import Gateway


def h(gravedad, v="V4"):
    return Hallazgo(f"h-{v}", v, "t", gravedad, 1, "0", "d", "q")


@pytest.mark.parametrize("gravedades,ruta,alias", [
    ([], "sin_modelo", None),
    (["informativo", "informativo"], "sin_modelo", None),
    (["menor"], "rapida", "rapido"),
    (["menor", "menor", "menor", "informativo"], "rapida", "rapido"),
    (["menor"] * 4, "completa", "completo"),
    (["grave"], "completa", "completo"),
    (["grave", "menor"], "completa", "completo"),
])
def test_enrutador(gravedades, ruta, alias):
    d = Enrutador().clasificar([h(g) for g in gravedades])
    assert (d.ruta, d.alias) == (ruta, alias)


def test_enrutador_devuelve_alias_y_preguntas_van_a_rapida():
    e = Enrutador()
    assert e.clasificar(tipo="pregunta").alias == "rapido"
    assert e.alias_respaldo("rapido") == "completo" and e.alias_respaldo("completo") == "rapido"


def gateway(rapido, completo):
    esperas = []
    g = Gateway({"rapido": rapido, "completo": completo}, {"rapido": 45, "completo": 90},
                dormir=esperas.append)
    return g, esperas


def test_tiempo_limite_por_ruta():
    r, c = ChatFalso("gemma4:e2b"), ChatFalso("gpt-oss:20b")
    g, _ = gateway(r, c)
    assert g.generar("rapido", [], None).modelo == "gemma4:e2b"
    g.generar("completo", [], None)
    assert r.llamadas[0]["tiempo_limite_s"] == 45 and c.llamadas[0]["tiempo_limite_s"] == 90


@pytest.mark.parametrize("falla", ["conexion", "5xx"])
def test_reintenta_conexion_y_5xx_con_espera_1_y_2(falla):
    r, c = ChatFalso("r", falla=falla, fallas=2), ChatFalso("c")
    g, esperas = gateway(r, c)
    res = g.generar("rapido", [], None)
    assert res.alias == "rapido" and not res.uso_respaldo and res.intentos == 3
    assert esperas == [1.0, 2.0] and len(r.llamadas) == 3 and not c.llamadas


def test_tras_reintentos_va_al_respaldo():
    r, c = ChatFalso("r", falla="conexion"), ChatFalso("c")
    g, esperas = gateway(r, c)
    res = g.generar("rapido", [], None)
    assert res.uso_respaldo and res.alias == "completo" and len(r.llamadas) == 3
    assert esperas == [1.0, 2.0]


@pytest.mark.parametrize("falla", ["timeout", "404"])
def test_timeout_y_404_no_se_reintentan(falla):
    r, c = ChatFalso("r", falla=falla), ChatFalso("c")
    g, esperas = gateway(r, c)
    res = g.generar("rapido", [], None)
    assert len(r.llamadas) == 1 and esperas == [] and res.uso_respaldo
    assert res.modelo == "c"


def test_si_el_respaldo_falla_modelo_no_disponible():
    r, c = ChatFalso("r", falla="timeout"), ChatFalso("c", falla="404")
    g, _ = gateway(r, c)
    with pytest.raises(ModeloNoDisponible) as e:
        g.generar("completo", [], None)
    assert e.value.codigo_http == 503


def test_sin_respaldo_para_el_clasificador():
    r, c = ChatFalso("r", falla="timeout"), ChatFalso("c")
    g, _ = gateway(r, c)
    with pytest.raises(ModeloNoDisponible):
        g.generar("rapido", [], None, permitir_respaldo=False)
    assert not c.llamadas


def test_registra_modelo_tokens_duracion_ruta_y_respaldo():
    class Traza:
        def __init__(self):
            self.llamadas = []

        def registrar_llamada(self, d):
            self.llamadas.append(d)

    t = Traza()
    r, c = ChatFalso("r", falla="timeout"), ChatFalso("c")
    g, _ = gateway(r, c)
    g.generar("rapido", [{"role": "user", "content": "hola mundo"}], None, ruta="rapida", traza=t)
    assert [x["ok"] for x in t.llamadas] == [False, True]
    ultimo = t.llamadas[-1]
    assert ultimo["modelo"] == "c" and ultimo["ruta"] == "rapida" and ultimo["uso_respaldo"]
    assert ultimo["tokens_entrada"] > 0 and ultimo["tokens_salida"] > 0 and "duracion_ms" in ultimo
