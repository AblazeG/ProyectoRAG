"""Regresiones de la revisión de C4 (caché) y C6 (gateway)."""
import pytest

from servicio.cache.exacta import CacheExacta
from servicio.cache.semantica import CacheSemantica
from servicio.datos.falsos import ChatFalso, EmbeddingsFalsos
from servicio.datos.sqlite import AlmacenCacheSQLite, BaseSQLite
from servicio.dominio import ModeloNoDisponible
from servicio.modelos.gateway import Gateway

V = {"perfiles": "1", "analizador": "1", "corpus": 1, "prompt": "v1", "modelos": {"rapido": "a"}}


def gateway(rapido, completo):
    return Gateway({"rapido": rapido, "completo": completo}, {"rapido": 45, "completo": 90},
                   dormir=lambda s: None)


def test_intentos_cuentan_todas_las_llamadas():
    g = gateway(ChatFalso("r", falla="conexion"), ChatFalso("c"))
    assert g.generar("rapido", [], None).intentos == 4          # 3 del principal + 1 del respaldo
    g = gateway(ChatFalso("r", falla="5xx"), ChatFalso("c", falla="conexion", fallas=1))
    assert g.generar("rapido", [], None).intentos == 5


def test_cada_intento_queda_registrado():
    class Traza:
        llamadas = []

        def registrar_llamada(self, d):
            self.llamadas.append(d)
    t = Traza()
    g = gateway(ChatFalso("r", falla="conexion", fallas=2), ChatFalso("c"))
    g.generar("rapido", [], None, traza=t)
    assert [x["ok"] for x in t.llamadas] == [False, False, True]


def test_adaptador_defectuoso_va_al_respaldo():
    class Roto:
        nombre = "roto"

        def generar(self, *a):
            raise ValueError("bug del adaptador")
    assert gateway(Roto(), ChatFalso("c")).generar("rapido", [], None).uso_respaldo
    with pytest.raises(ModeloNoDisponible):
        gateway(Roto(), Roto()).generar("rapido", [], None)


def test_semantica_ignora_otra_dimension_y_otro_modelo():
    almacen = AlmacenCacheSQLite(BaseSQLite(":memory:"))
    sem3 = CacheSemantica(almacen, EmbeddingsFalsos(dimension=64, nombre="m"))
    sem4 = CacheSemantica(almacen, EmbeddingsFalsos(dimension=128, nombre="m"))
    sem3.guardar("¿Cómo corrijo las normales?", "sha", "animacion", {"r": 1}, 1, True)
    assert sem4.buscar_similar("¿Cómo corrijo las normales?", "sha", "animacion", 1) is None
    otro = CacheSemantica(almacen, EmbeddingsFalsos(dimension=64, nombre="otro"))
    assert otro.buscar_similar("¿Cómo corrijo las normales?", "sha", "animacion", 1) is None
    assert sem3.buscar_similar("¿Cómo corrijo las normales?", "sha", "animacion", 1, "v2") is None
    assert sem3.buscar_similar("¿Cómo corrijo las normales?", "sha", "animacion", 1)


def test_clave_de_pregunta_cambia_con_analizador_y_perfiles():
    base = CacheExacta.clave_pregunta("sha", "animacion", "hola", V)
    assert base != CacheExacta.clave_pregunta("sha", "animacion", "hola", {**V, "analizador": "2"})
    assert base != CacheExacta.clave_pregunta("sha", "animacion", "hola", {**V, "perfiles": "2"})
