"""Adaptador vectorial persistente sobre ChromaDB (C7), espacio coseno."""
from __future__ import annotations

import os
from pathlib import Path

from servicio.dominio import ErrorDatos, Fragmento, Recuperado

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


def _metadatos(f: Fragmento) -> dict:
    meta = {
        "doc_id": f.doc_id,
        "titulo": f.titulo,
        "seccion": f.seccion,
        "pagina": f.pagina if f.pagina is not None else -1,
        "formato": f.formato,
        "licencia": f.licencia,
        "perfiles": ",".join(f.perfiles),
    }
    for perfil in f.perfiles:  # Chroma no filtra listas: una bandera por perfil
        meta[f"perfil_{perfil}"] = True
    return meta


def _fragmento(id_: str, texto: str, meta: dict) -> Fragmento:
    pagina = meta.get("pagina", -1)
    return Fragmento(
        id=id_, doc_id=meta["doc_id"], texto=texto, titulo=meta.get("titulo", ""),
        seccion=meta.get("seccion", ""), pagina=None if pagina == -1 else int(pagina),
        formato=meta.get("formato", ""), licencia=meta.get("licencia", ""),
        perfiles=[p for p in meta.get("perfiles", "").split(",") if p])


def traducir_filtro(filtro: dict | None) -> dict | None:
    """Filtro del dominio -> cláusula ``where`` de Chroma."""
    if not filtro:
        return None
    clausulas = []
    for clave, valor in filtro.items():
        if clave == "perfil":
            clausulas.append({f"perfil_{valor}": True})
        else:
            clausulas.append({clave: valor})
    return clausulas[0] if len(clausulas) == 1 else {"$and": clausulas}


class AlmacenChroma:
    """Puerto ``AlmacenVectorial`` con ChromaDB persistente."""

    nombre = "chromadb"

    def __init__(self, ruta: Path | str, coleccion: str = "normas"):
        import chromadb
        from chromadb.config import Settings

        try:
            Path(ruta).mkdir(parents=True, exist_ok=True)
            self._cliente = chromadb.PersistentClient(
                path=str(ruta), settings=Settings(anonymized_telemetry=False))
            self._coleccion = self._cliente.get_or_create_collection(
                name=coleccion, metadata={"hnsw:space": "cosine"},
                embedding_function=None)
        except Exception as exc:  # noqa: BLE001
            raise ErrorDatos(f"No se pudo abrir ChromaDB: {exc}") from exc

    def agregar(self, fragmentos: list[Fragmento], vectores: list[list[float]]) -> None:
        if not fragmentos:
            return
        self._coleccion.upsert(
            ids=[f.id for f in fragmentos],
            embeddings=[list(map(float, v)) for v in vectores],
            documents=[f.texto for f in fragmentos],
            metadatas=[_metadatos(f) for f in fragmentos])

    def buscar(self, vector: list[float], k: int,
               filtro: dict | None = None) -> list[Recuperado]:
        if self._coleccion.count() == 0:
            return []
        resultado = self._coleccion.query(
            query_embeddings=[list(map(float, vector))], n_results=k,
            where=traducir_filtro(filtro),
            include=["documents", "metadatas", "distances"])
        recuperados = []
        for id_, texto, meta, distancia in zip(
                resultado["ids"][0], resultado["documents"][0],
                resultado["metadatas"][0], resultado["distances"][0]):
            recuperados.append(Recuperado(_fragmento(id_, texto, meta),
                                          puntaje=1.0 - float(distancia)))
        return recuperados

    def eliminar_documento(self, doc_id: str) -> int:
        existentes = self._coleccion.get(where={"doc_id": doc_id}, include=[])
        ids = existentes["ids"]
        if ids:
            self._coleccion.delete(ids=ids)
        return len(ids)

    def contar(self) -> int:
        return self._coleccion.count()

    def vaciar(self) -> None:
        todos = self._coleccion.get(include=[])["ids"]
        if todos:
            self._coleccion.delete(ids=todos)

    def comprobar(self) -> dict:
        try:
            return {"ok": True, "fragmentos": self._coleccion.count()}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "detalle": type(exc).__name__}
