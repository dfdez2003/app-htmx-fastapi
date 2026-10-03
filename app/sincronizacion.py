"""Persistencia remota opcional en MongoDB Atlas.

Por qué existe: la fuente de verdad era `datos/tablero.json` versionado, así que
mover una tarea obligaba a hacer commit y pull en la otra laptop. Aquí el estado
vive en Atlas y el JSON local queda como caché (para arrancar sin internet).

Forma del dato: UN solo documento (`_id: "principal"`) con las dos listas
completas. Son ~11 KB, muy por debajo del límite de 16 MB de Mongo, y al ser un
documento único cada escritura es atómica: nunca se ve un estado a medias.

Guarda de versión: el documento lleva un contador `version`. Solo se pisa si la
versión remota sigue siendo la que leímos; si otra laptop escribió entre medias,
la escritura se rechaza y el estado que iba a subir se guarda en
`datos/conflicto-<fecha>.json` en vez de perderse. Git avisaba de estos choques
con un conflicto de merge; Atlas no, de ahí el contador.

Si no hay `MONGODB_URI` en el entorno, todo este módulo queda inerte y la app se
comporta como antes (solo JSON local).
"""

import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ID_DOC = "principal"

# Al arrastrar una tarjeta se disparan varios commits seguidos; se agrupan en una
# sola escritura remota en vez de pagar un viaje de red por cada uno.
ESPERA_AGRUPADO_SEG = 0.4

TIMEOUT_MS = 5000

# Mismo directorio que usa database.py para la caché; se repite aquí (en vez de
# importarlo) porque database.py importa este módulo y sería circular.
DIR_DATOS = Path("datos")

_cliente = None
_coleccion = None

# Protege _version_local, que lee el hilo de la petición y escribe el worker.
_lock = threading.Lock()
_version_local = 0

_lock_worker = threading.Lock()
_worker: threading.Thread | None = None
_hay_cambios = threading.Event()
_parar = threading.Event()

_snapshot: Callable[[], dict] | None = None


def _avisar(mensaje: str) -> None:
    print(f"[sincronizacion] {mensaje}", file=sys.stderr)


# ---------- Configuración (se lee en cada llamada, no al importar) ----------


def uri() -> str:
    return os.getenv("MONGODB_URI", "").strip()


def activa() -> bool:
    """True si hay Atlas configurado. Sin URI la app funciona igual que antes."""
    return bool(uri())


def _nombre_bd() -> str:
    return os.getenv("MONGODB_DB", "").strip() or "agenda"


def _nombre_coleccion() -> str:
    return os.getenv("MONGODB_COLECCION", "").strip() or "tablero"


def _obtener_coleccion():
    global _cliente, _coleccion
    if _coleccion is not None:
        return _coleccion
    from pymongo import MongoClient

    _cliente = MongoClient(
        uri(),
        serverSelectionTimeoutMS=TIMEOUT_MS,
        connectTimeoutMS=TIMEOUT_MS,
        appname="agenda",
    )
    _coleccion = _cliente[_nombre_bd()][_nombre_coleccion()]
    return _coleccion


# ---------- Lectura ----------


def cargar() -> tuple[str, dict | None]:
    """Trae el documento completo.

    Devuelve la situación junto al dato para poder distinguir "Atlas está vacío"
    (hay que subir lo local) de "Atlas no responde" (hay que trabajar con la
    caché): ("ok", datos), ("vacio", None), ("apagado", None) o ("error", None).
    """
    global _version_local
    if not activa():
        return ("apagado", None)
    try:
        doc = _obtener_coleccion().find_one({"_id": ID_DOC})
    except Exception as exc:
        _avisar(f"no se pudo leer de Atlas: {exc}")
        return ("error", None)
    if doc is None:
        return ("vacio", None)
    with _lock:
        _version_local = int(doc.get("version", 0))
    return ("ok", {"categorias": doc.get("categorias", []), "tareas": doc.get("tareas", [])})


def version_remota() -> int | None:
    """Solo el contador, sin traer las listas: es la consulta barata que permite
    preguntar "¿cambió algo?" en cada carga de página."""
    if not activa():
        return None
    try:
        doc = _obtener_coleccion().find_one({"_id": ID_DOC}, {"version": 1})
    except Exception as exc:
        _avisar(f"no se pudo consultar la versión en Atlas: {exc}")
        return None
    if doc is None:
        return None
    return int(doc.get("version", 0))


def cargar_si_cambio() -> dict | None:
    """El estado remoto, pero solo si otra laptop lo adelantó. None si no hay
    nada nuevo, si Atlas no responde o si tenemos cambios locales sin subir
    (recargar en ese momento los borraría)."""
    if not activa() or _hay_cambios.is_set():
        return None
    remota = version_remota()
    with _lock:
        local = _version_local
    if remota is None or remota <= local:
        return None
    situacion, datos = cargar()
    return datos if situacion == "ok" else None


# ---------- Escritura ----------


def _guardar_conflicto(datos: dict) -> None:
    sello = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    destino = DIR_DATOS / f"conflicto-{sello}.json"
    try:
        DIR_DATOS.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _avisar(f"conflicto: otra laptop escribió primero. Tu estado quedó en {destino}")
    except Exception as exc:
        _avisar(f"conflicto y además no se pudo escribir el respaldo: {exc}")


def guardar(datos: dict) -> bool:
    """Sube el estado con guarda de versión. False si hubo conflicto o fallo de
    red (en el conflicto, el estado rechazado queda respaldado en disco)."""
    global _version_local
    if not activa():
        return False
    from pymongo.errors import DuplicateKeyError

    with _lock:
        esperada = _version_local
    doc = {
        **datos,
        "version": esperada + 1,
        "actualizado_en": datetime.now(timezone.utc).isoformat(),
    }
    try:
        # upsert crea el documento la primera vez; si ya existe con otra versión
        # el filtro no casa y el upsert choca con el _id, que es justo la señal
        # de conflicto que buscamos.
        resultado = _obtener_coleccion().update_one(
            {"_id": ID_DOC, "version": esperada}, {"$set": doc}, upsert=True
        )
    except DuplicateKeyError:
        _guardar_conflicto(datos)
        return False
    except Exception as exc:
        _avisar(f"no se pudo escribir en Atlas: {exc}")
        return False
    if resultado.matched_count == 0 and resultado.upserted_id is None:
        _guardar_conflicto(datos)
        return False
    with _lock:
        _version_local = esperada + 1
    return True


# ---------- Worker en segundo plano ----------


def registrar_snapshot(fn: Callable[[], dict]) -> None:
    """database.py registra aquí cómo obtener el estado actual, para que el
    worker pueda subirlo sin que este módulo sepa nada de SQLModel."""
    global _snapshot
    _snapshot = fn


def marcar_sucio() -> None:
    """Hay cambios que subir. No bloquea: el volcado remoto corre en otro hilo
    para no añadir el viaje de red a la respuesta HTTP del usuario."""
    if not activa():
        return
    _hay_cambios.set()
    _arrancar_worker()


def _arrancar_worker() -> None:
    global _worker
    with _lock_worker:
        if _worker is not None and _worker.is_alive():
            return
        _parar.clear()
        _worker = threading.Thread(target=_bucle, name="agenda-atlas", daemon=True)
        _worker.start()


def _bucle() -> None:
    while not _parar.is_set():
        if not _hay_cambios.wait(timeout=1.0):
            continue
        _parar.wait(ESPERA_AGRUPADO_SEG)
        # Se limpia ANTES de escribir: si llega un cambio mientras subimos, la
        # bandera vuelve a quedar puesta y se sube otra vez (no se pierde).
        _hay_cambios.clear()
        _escribir_ahora()


def _escribir_ahora() -> None:
    if _snapshot is None:
        return
    try:
        datos = _snapshot()
    except Exception as exc:
        _avisar(f"no se pudo leer el estado local para subirlo: {exc}")
        return
    guardar(datos)


def vaciar(timeout: float = 5.0) -> None:
    """Sube lo que quede pendiente y para el worker. Se llama al apagar la app
    para que un cambio hecho en el último segundo no se quede sin subir."""
    if not activa():
        return
    if _hay_cambios.is_set():
        _hay_cambios.clear()
        _escribir_ahora()
    _parar.set()
    worker = _worker
    if worker is not None and worker.is_alive():
        worker.join(timeout=timeout)
    _cerrar_cliente()


def _cerrar_cliente() -> None:
    global _cliente, _coleccion
    if _cliente is not None:
        try:
            _cliente.close()
        except Exception:
            pass
    _cliente = None
    _coleccion = None
