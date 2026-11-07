"""C4: cachés exactas, semántica, purga y expiración."""
from servicio.cache.exacta import CacheExacta, normalizar_pregunta
from servicio.cache.semantica import CacheSemantica
from servicio.datos.falsos import EmbeddingsFalsos
from servicio.datos.sqlite import AlmacenCacheSQLite, BaseSQLite

V = {"perfiles": "1.0.0", "analizador": "1.0.0", "corpus": 1, "prompt": "v1",
     "modelos": {"rapido": "a", "completo": "b"}}


class Reloj:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def nuevas(reloj=None, activa=True):
    almacen = AlmacenCacheSQLite(BaseSQLite(":memory:"))
    reloj = reloj or Reloj()
    return (CacheExacta(almacen, activa=activa, reloj=reloj),
            CacheSemantica(almacen, EmbeddingsFalsos(), activa=activa, reloj=reloj), reloj)


def test_clave_de_informe_depende_de_todas_las_versiones():
    base = CacheExacta.clave_informe("sha", "animacion", "notas", V)
    assert base == CacheExacta.clave_informe("sha", "animacion", "notas", dict(V))
    for cambio in ({"perfiles": "2"}, {"analizador": "2"}, {"corpus": 2}, {"prompt": "v2"},
                   {"modelos": {"rapido": "x", "completo": "b"}}):
        assert base != CacheExacta.clave_informe("sha", "animacion", "notas", {**V, **cambio})
    assert base != CacheExacta.clave_informe("sha", "web_ar", "notas", V)
    assert base != CacheExacta.clave_informe("sha", "animacion", "otras", V)
    assert base != CacheExacta.clave_informe("sha2", "animacion", "notas", V)


def test_informe_solo_validado_y_expira_a_los_7_dias():
    exacta, _, reloj = nuevas()
    k = CacheExacta.clave_informe("sha", "animacion", "", V)
    assert not exacta.guardar_informe(k, {"x": 1}, 1, validada=False)
    assert exacta.obtener_informe(k) is None
    assert exacta.guardar_informe(k, {"x": 1}, 1, validada=True)
    reloj.t += 7 * 24 * 3600 - 1
    assert exacta.obtener_informe(k) == {"x": 1}
    reloj.t += 2
    assert exacta.obtener_informe(k) is None


def test_hallazgo_guarda_sin_mediciones():
    exacta, _, _ = nuevas()
    k = CacheExacta.clave_hallazgo("V4", "animacion", "menor", 1, "v1", "gemma4:e2b")
    assert k != CacheExacta.clave_hallazgo("V4", "animacion", "menor", 1, "v1", "gpt-oss:20b")
    exacta.guardar_hallazgo(k, {"explicacion": "e", "correccion": ["p"], "fuente": {"d": 1},
                                "medido": 3, "limite": "0"}, 1, validada=True)
    assert exacta.obtener_hallazgo(k) == {"explicacion": "e", "correccion": ["p"], "fuente": {"d": 1}}


def test_pregunta_exacta_normaliza_texto():
    a = CacheExacta.clave_pregunta("sha", "animacion", "¿Cómo corrijo las normales?", V)
    b = CacheExacta.clave_pregunta("sha", "animacion", "  cómo corrijo   las NORMALES ", V)
    assert a == b
    assert normalizar_pregunta("¿Hola?") == "hola"


def test_semantica_mismo_archivo_perfil_y_umbral():
    _, sem, reloj = nuevas()
    sem.guardar("¿Cómo corrijo las aristas no manifold?", "sha", "animacion", {"r": 1}, 1, True)
    acierto = sem.buscar("como corrijo las aristas no manifold", "sha", "animacion", 1)
    assert acierto and acierto[1] >= 0.92 and acierto[0] == {"r": 1}
    assert sem.buscar("¿Qué presupuesto de triángulos tiene un juego?", "sha", "animacion", 1) is None
    assert sem.buscar("como corrijo las aristas no manifold", "otro", "animacion", 1) is None
    assert sem.buscar("como corrijo las aristas no manifold", "sha", "web_ar", 1) is None
    assert sem.buscar("como corrijo las aristas no manifold", "sha", "animacion", 2) is None
    reloj.t += 24 * 3600 + 1
    assert sem.buscar("como corrijo las aristas no manifold", "sha", "animacion", 1) is None


def test_semantica_no_guarda_rechazos():
    _, sem, _ = nuevas()
    assert not sem.guardar("p", "sha", "animacion", {"r": 1}, 1, validada=False)


def test_purga_por_version_de_corpus():
    exacta, sem, _ = nuevas()
    exacta.guardar("pregunta", "k1", {"v": 1}, 1, True)
    exacta.guardar("pregunta", "k2", {"v": 2}, 2, True)
    sem.guardar("pregunta vieja", "sha", "animacion", {"r": 1}, 1, True)
    assert exacta.purgar(2) == 2
    assert exacta.obtener_pregunta("k1") is None and exacta.obtener_pregunta("k2") == {"v": 2}


def test_cache_desactivada():
    exacta, sem, _ = nuevas(activa=False)
    assert not exacta.guardar_informe("k", {"a": 1}, 1, True)
    assert exacta.obtener_informe("k") is None
    assert sem.buscar("x", "s", "p", 1) is None
