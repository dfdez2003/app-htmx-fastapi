"""Pruebas de la guarda de versión: es lo único que protege de que una laptop
con estado viejo pise lo que escribió la otra. No tocan Atlas de verdad; usan una
colección falsa que imita lo que devuelve pymongo."""

import json

import pytest

from app import sincronizacion


class ResultadoFalso:
    def __init__(self, matched_count: int, upserted_id=None):
        self.matched_count = matched_count
        self.upserted_id = upserted_id


class ColeccionFalsa:
    """Imita update_one con upsert sobre un único documento con _id fijo."""

    def __init__(self, doc: dict | None = None):
        self.doc = doc

    def find_one(self, filtro, proyeccion=None):
        if self.doc is None:
            return None
        if proyeccion:
            return {clave: self.doc[clave] for clave in proyeccion if clave in self.doc}
        return dict(self.doc)

    def update_one(self, filtro, update, upsert=False):
        from pymongo.errors import DuplicateKeyError

        if self.doc is not None and self.doc.get("version") == filtro.get("version"):
            self.doc.update(update["$set"])
            return ResultadoFalso(matched_count=1)
        if self.doc is None:
            if not upsert:
                return ResultadoFalso(matched_count=0)
            self.doc = {"_id": filtro["_id"], **update["$set"]}
            return ResultadoFalso(matched_count=0, upserted_id=filtro["_id"])
        # El documento existe con otra versión: el upsert choca con el _id.
        if upsert:
            raise DuplicateKeyError("E11000 duplicate key error")
        return ResultadoFalso(matched_count=0)


@pytest.fixture()
def atlas(monkeypatch, tmp_path):
    """Deja el módulo en un estado limpio, con Atlas "encendido" y los respaldos
    de conflicto fuera del repo."""
    monkeypatch.setenv("MONGODB_URI", "mongodb+srv://falso/")
    monkeypatch.setattr(sincronizacion, "_version_local", 0)
    monkeypatch.setattr(sincronizacion, "DIR_DATOS", tmp_path)
    sincronizacion._hay_cambios.clear()

    def montar(doc=None):
        coleccion = ColeccionFalsa(doc)
        monkeypatch.setattr(sincronizacion, "_obtener_coleccion", lambda: coleccion)
        return coleccion

    return montar


DATOS = {"categorias": [{"id": 1, "nombre": "Escuela", "orden": 0, "color": "#fff"}], "tareas": []}


def test_sin_uri_queda_inerte(monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    assert sincronizacion.activa() is False
    assert sincronizacion.cargar() == ("apagado", None)
    assert sincronizacion.guardar(DATOS) is False


def test_primer_guardado_crea_el_documento(atlas):
    coleccion = atlas(None)
    assert sincronizacion.cargar() == ("vacio", None)
    assert sincronizacion.guardar(DATOS) is True
    assert coleccion.doc["version"] == 1
    assert coleccion.doc["categorias"] == DATOS["categorias"]


def test_guardados_sucesivos_avanzan_la_version(atlas):
    coleccion = atlas({"_id": "principal", "version": 3, "categorias": [], "tareas": []})
    sincronizacion.cargar()
    assert sincronizacion.guardar(DATOS) is True
    assert coleccion.doc["version"] == 4
    assert sincronizacion.guardar(DATOS) is True
    assert coleccion.doc["version"] == 5


def test_conflicto_no_pisa_y_respalda_en_disco(atlas, tmp_path):
    """El caso que git resolvía con un conflicto de merge: la otra laptop escribió
    mientras esta tenía la pestaña abierta con estado viejo."""
    coleccion = atlas({"_id": "principal", "version": 2, "categorias": [], "tareas": []})
    sincronizacion.cargar()

    # La otra laptop escribe: la versión remota avanza por debajo.
    coleccion.doc["version"] = 7
    coleccion.doc["categorias"] = [{"id": 9, "nombre": "De la otra laptop", "orden": 0, "color": "#000"}]

    assert sincronizacion.guardar(DATOS) is False
    assert coleccion.doc["version"] == 7, "no debe pisar el estado remoto"
    assert coleccion.doc["categorias"][0]["nombre"] == "De la otra laptop"

    respaldos = list(tmp_path.glob("conflicto-*.json"))
    assert len(respaldos) == 1, "el estado rechazado debe quedar respaldado"
    assert json.loads(respaldos[0].read_text(encoding="utf-8")) == DATOS


def test_cargar_si_cambio_calla_cuando_no_hay_nada_nuevo(atlas):
    atlas({"_id": "principal", "version": 4, "categorias": [], "tareas": []})
    sincronizacion.cargar()
    assert sincronizacion.cargar_si_cambio() is None


def test_cargar_si_cambio_trae_el_estado_de_la_otra_laptop(atlas):
    coleccion = atlas({"_id": "principal", "version": 4, "categorias": [], "tareas": []})
    sincronizacion.cargar()
    coleccion.doc["version"] = 5
    coleccion.doc["categorias"] = DATOS["categorias"]
    assert sincronizacion.cargar_si_cambio() == DATOS


def test_cargar_si_cambio_no_descarta_cambios_locales_sin_subir(atlas):
    """Si hay algo pendiente de subir, recargar desde Atlas lo borraría."""
    coleccion = atlas({"_id": "principal", "version": 4, "categorias": [], "tareas": []})
    sincronizacion.cargar()
    coleccion.doc["version"] = 5
    sincronizacion._hay_cambios.set()
    try:
        assert sincronizacion.cargar_si_cambio() is None
    finally:
        sincronizacion._hay_cambios.clear()
