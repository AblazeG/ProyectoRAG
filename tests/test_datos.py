"""C7: SQLite, almacenes vectoriales, lectores y dobles falsos."""
import json
import time

import numpy as np
import pytest

from servicio.datos.chroma import AlmacenChroma
from servicio.datos.documentos import LectorDocumentos
from servicio.datos.falsos import ChatFalso, EmbeddingsFalsos
from servicio.datos.mallas import AlmacenMallasTemporal, LectorTrimesh, leer_lados_obj
from servicio.datos.memoria import AlmacenMemoria
from servicio.datos.sqlite import (AlmacenCacheSQLite, BaseSQLite, RepositorioDocumentosSQLite,
                                   RepositorioInformesSQLite, RepositorioManifiestoSQLite,
                                   RepositorioRetroalimentacionSQLite)
from servicio.dominio import (ArchivoSubido, EntradaInvalida, ErrorTiempoLimite, Fragmento,
                              ModeloInexistente, RespuestaExplicaciones)


def frag(i, doc="d1", perfiles=("animacion",), texto="texto"):
    return Fragmento(id=f"{doc}:s#{i}", doc_id=doc, texto=texto, titulo="T", seccion="S",
                     pagina=None, formato="markdown", licencia="CC0-1.0", perfiles=list(perfiles))


@pytest.mark.parametrize("fabrica", ["memoria", "chroma"])
def test_almacenes_vectoriales(fabrica, tmp_path):
    almacen = AlmacenMemoria() if fabrica == "memoria" else AlmacenChroma(tmp_path / "c")
    almacen.agregar([frag(1), frag(2, perfiles=("web_ar",)), frag(3, doc="d2")],
                    [[1, 0, 0], [0.9, 0.1, 0], [0, 1, 0]])
    assert almacen.contar() == 3
    r = almacen.buscar([1, 0, 0], k=2)
    assert r[0].fragmento.id == "d1:s#1" and r[0].puntaje == pytest.approx(1.0, abs=1e-4)
    filtrado = almacen.buscar([1, 0, 0], k=5, filtro={"perfil": "animacion"})
    assert {x.fragmento.id for x in filtrado} == {"d1:s#1", "d2:s#3"}
    assert filtrado[0].fragmento.perfiles == ["animacion"]
    assert almacen.eliminar_documento("d1") == 2
    assert almacen.contar() == 1


def test_sqlite_cache_y_purga(tmp_path):
    cache = AlmacenCacheSQLite(BaseSQLite(tmp_path / "x.sqlite"))
    ahora = time.time()
    cache.guardar("informe", "k", {"a": 1}, 1, ahora + 10, ahora)
    assert cache.obtener("informe", "k", ahora) == {"a": 1}
    assert cache.obtener("informe", "k", ahora + 11) is None
    cache.guardar_semantica("g", [1.0, 0.0], {"r": 1}, 1, ahora + 10, ahora)
    cache.guardar_semantica("g", [0.0, 1.0], {"r": 2}, 2, ahora + 10, ahora)
    assert len(cache.listar_semantica("g", ahora)) == 2
    assert cache.purgar(2) == 2
    assert [e["valor"] for e in cache.listar_semantica("g", ahora)] == [{"r": 2}]
    assert cache.eliminar_expirados(ahora + 100) == 1


def test_repositorios_sqlite(tmp_path):
    base = BaseSQLite(tmp_path / "x.sqlite")
    inf = RepositorioInformesSQLite(base)
    inf.guardar({"auditoria_id": "a1", "traza_id": "t1", "perfil": "animacion"}, "sha")
    assert inf.obtener("a1")["_archivo_sha"] == "sha"
    assert inf.obtener_por_traza("t1")["auditoria_id"] == "a1"
    assert inf.obtener("nada") is None
    docs = RepositorioDocumentosSQLite(base)
    docs.guardar({"doc_id": "d1", "titulo": "T"})
    assert docs.listar() == [{"doc_id": "d1", "titulo": "T"}]
    assert docs.eliminar("d1") and not docs.eliminar("d1")
    man = RepositorioManifiestoSQLite(base)
    assert man.leer() == {}
    man.guardar({"version_corpus": 3})
    assert man.leer()["version_corpus"] == 3
    retro = RepositorioRetroalimentacionSQLite(base)
    retro.guardar({"traza_id": "t1", "util": True})
    retro.guardar({"traza_id": "t1", "util": False, "hallazgo_id": "h"})
    assert retro.resumen()["tasa_utilidad"] == 0.5
    assert base.comprobar()["ok"]


def test_lector_obj_lados_y_temporal(tmp_path):
    obj = tmp_path / "m.obj"
    obj.write_text("v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nv 2 0 0\n"
                   "f 1 2 3 4\nf 2 5 3\n")
    assert leer_lados_obj(obj) == [4, 3]
    malla = LectorTrimesh().leer(obj)
    assert malla.formato == "obj" and malla.caras.shape == (3, 3)
    assert malla.lados_por_cara == [4, 3] and malla.uv is None
    temporal = AlmacenMallasTemporal(tmp_path / "mallas")
    ruta = temporal.guardar(b"abc", ".OBJ")
    assert ruta.exists() and ruta.suffix == ".obj"
    temporal.borrar(ruta)
    assert not ruta.exists()
    basura = tmp_path / "b.obj"
    basura.write_text("hola")
    with pytest.raises(EntradaInvalida):
        LectorTrimesh().leer(basura)


def test_lector_documentos_markdown_y_html():
    lector = LectorDocumentos()
    md = ArchivoSubido("n.md", "---\ntitulo: Norma\nlicencia: CC0-1.0\n---\n# Norma\n\n"
                       "## Sección A\n\nPárrafo uno.\n\n## Sección B\n\nPárrafo dos.\n".encode())
    assert lector.inspeccionar(md)["licencia_detectada"] == "CC0-1.0"
    doc = lector.extraer(md)
    assert doc.titulo == "Norma" and [s.titulo for s in doc.secciones] == ["Sección A", "Sección B"]
    html = ArchivoSubido("p.html", b"<html><head><title>Guia</title></head><body>"
                         b"<nav>Menu inicio</nav><header>Cabecera</header><main><h2>Normales</h2>"
                         b"<p>Recalcula las normales.</p></main><footer>Pie</footer></body></html>")
    doc = lector.extraer(html)
    assert doc.titulo == "Guia"
    assert "Menu" not in doc.texto and "Pie" not in doc.texto and "Cabecera" not in doc.texto
    assert doc.secciones[0].titulo == "Normales"
    assert lector.inspeccionar(ArchivoSubido("x.pdf", b"nada"))["firma_ok"] is False


def test_lector_documentos_pdf():
    from pypdf import PdfWriter
    import io
    escritor = PdfWriter()
    escritor.add_blank_page(100, 100)
    salida = io.BytesIO()
    escritor.write(salida)
    archivo = ArchivoSubido("v.pdf", salida.getvalue())
    assert LectorDocumentos().inspeccionar(archivo)["firma_ok"]
    assert LectorDocumentos().extraer(archivo).secciones == []


def test_embeddings_falsos_deterministas_y_cercanos():
    emb = EmbeddingsFalsos()
    a, b, c = emb.vectorizar(["Aristas no manifold en la malla",
                              "aristas NO manifold en la malla.",
                              "receta de pastel de chocolate"], "consulta")
    assert a == emb.vectorizar(["Aristas no manifold en la malla"], "documento")[0]
    assert np.dot(a, b) > 0.99 and np.dot(a, c) < 0.3
    assert abs(np.linalg.norm(a) - 1) < 1e-9


def test_chat_falso_cita_y_respeta_esquema():
    chat = ChatFalso("rapido-falso")
    prompt = ('<contexto>\n<fragmento id="d:s#1">Las aristas no manifold rompen la malla. '
              'Usa Select Non Manifold para encontrarlas.</fragmento>\n</contexto>\n'
              '<hallazgos>\n<hallazgo id="h-V4" fragmentos="d:s#1">x</hallazgo>\n'
              '<hallazgo id="h-V8" fragmentos="">y</hallazgo>\n</hallazgos>')
    g = chat.generar([{"role": "user", "content": prompt}],
                     RespuestaExplicaciones.model_json_schema(), 10)
    r = RespuestaExplicaciones.model_validate_json(g.texto)
    assert r.hallazgos[0].citas == ["d:s#1"] and "[d:s#1]" in r.hallazgos[0].explicacion
    assert r.hallazgos[1].explicacion == "Sin norma aplicable en el corpus"
    with pytest.raises(ErrorTiempoLimite):
        ChatFalso(falla="timeout").generar([], None, 1)
    una = ChatFalso(falla="404", fallas=1)
    with pytest.raises(ModeloInexistente):
        una.generar([], None, 1)
    json.loads(una.generar([], {"properties": {"a": {"type": "string"}}}, 1).texto)
