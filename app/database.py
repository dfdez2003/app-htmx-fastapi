import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app import sincronizacion
from app.modelos import Categoria, Columna, Prioridad, Tarea

# Fuente de verdad PERSISTENTE: el documento en MongoDB Atlas (ver
# app/sincronizacion.py). SQLite sigue siendo solo el motor de consultas: se
# reconstruye desde el estado remoto al arrancar y se vuelca tras cada cambio.
#
# datos/tablero.json quedó como CACHÉ local, ya no versionada: permite arrancar
# sin internet y sirve de respaldo. Antes era la fuente de verdad, lo que
# obligaba a hacer commit y pull para mover una tarea entre laptops.
#
# Sin MONGODB_URI en el entorno nada de esto aplica y la caché vuelve a hacer de
# fuente de verdad, igual que antes.
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DATOS_DIR = Path("datos")
DATOS_JSON = DATOS_DIR / "tablero.json"

DATABASE_URL = f"sqlite:///{DATA_DIR / 'tablero.db'}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def crear_tablas() -> None:
    SQLModel.metadata.create_all(engine)
    _migrar_columnas()
    cargar_estado_inicial()


def _migrar_columnas() -> None:
    """Agrega columnas nuevas a una BD SQLite preexistente (por si quedó un
    archivo viejo); create_all no altera tablas que ya existen."""
    nuevas = {"orden_ejecucion": "INTEGER"}
    with engine.connect() as conn:
        existentes = {fila[1] for fila in conn.exec_driver_sql("PRAGMA table_info(tarea)").fetchall()}
        for columna, tipo in nuevas.items():
            if columna not in existentes:
                conn.exec_driver_sql(f"ALTER TABLE tarea ADD COLUMN {columna} {tipo}")
        conn.commit()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


# ---------- Volcado del estado ----------

# Se suspende el volcado durante la carga inicial (evita reescribir con lo que se
# acaba de leer y posibles reentradas del listener de commit).
_volcado_suspendido = False


class _sin_volcado:
    def __enter__(self):
        global _volcado_suspendido
        self._prev = _volcado_suspendido
        _volcado_suspendido = True

    def __exit__(self, *args):
        global _volcado_suspendido
        _volcado_suspendido = self._prev


def _categoria_a_dict(c: Categoria) -> dict:
    return {"id": c.id, "nombre": c.nombre, "orden": c.orden, "color": c.color}


def _tarea_a_dict(t: Tarea) -> dict:
    return {
        "id": t.id,
        "titulo": t.titulo,
        "descripcion": t.descripcion,
        "columna": t.columna.value,
        "orden": t.orden,
        "etiqueta": t.etiqueta,
        "fecha_limite": t.fecha_limite.isoformat() if t.fecha_limite else None,
        "creado_en": t.creado_en.isoformat(),
        "categoria_id": t.categoria_id,
        "prioridad": t.prioridad.value,
        "orden_ejecucion": t.orden_ejecucion,
    }


def snapshot() -> dict:
    """TODO el estado como dict, ordenado por id para que los diffs de la caché
    sigan siendo estables. Es lo que se escribe tanto en el JSON como en Atlas."""
    with Session(engine) as session:
        categorias = session.exec(select(Categoria).order_by(Categoria.id)).all()
        tareas = session.exec(select(Tarea).order_by(Tarea.id)).all()
        return {
            "categorias": [_categoria_a_dict(c) for c in categorias],
            "tareas": [_tarea_a_dict(t) for t in tareas],
        }


# El worker de Atlas sube el estado desde otro hilo y necesita poder obtenerlo
# sin conocer SQLModel.
sincronizacion.registrar_snapshot(snapshot)


def volcar_a_json(datos: dict | None = None) -> None:
    """Escribe la caché local. Es disco local, así que se hace síncrono; lo que
    va en segundo plano es la subida a Atlas."""
    if datos is None:
        datos = snapshot()
    DATOS_DIR.mkdir(parents=True, exist_ok=True)
    DATOS_JSON.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _aplicar(datos: dict) -> None:
    """Reconstruye las tablas con el estado recibido. Borra y reinserta con los
    ids originales: el estado remoto manda, no se intenta fusionar."""
    with _sin_volcado(), Session(engine) as session:
        for tarea in session.exec(select(Tarea)).all():
            session.delete(tarea)
        for categoria in session.exec(select(Categoria)).all():
            session.delete(categoria)
        session.commit()

        for c in datos.get("categorias", []):
            session.add(Categoria(id=c["id"], nombre=c["nombre"], orden=c.get("orden", 0), color=c["color"]))
        for t in datos.get("tareas", []):
            session.add(Tarea(
                id=t["id"],
                titulo=t["titulo"],
                descripcion=t.get("descripcion", ""),
                columna=Columna(t["columna"]),
                orden=t.get("orden", 0),
                etiqueta=t.get("etiqueta"),
                fecha_limite=date.fromisoformat(t["fecha_limite"]) if t.get("fecha_limite") else None,
                creado_en=datetime.fromisoformat(t["creado_en"]) if t.get("creado_en") else datetime.utcnow(),
                categoria_id=t.get("categoria_id"),
                prioridad=Prioridad(t.get("prioridad", "media")),
                orden_ejecucion=t.get("orden_ejecucion"),
            ))
        session.commit()


def cargar_desde_json() -> None:
    """Reconstruye las tablas desde la caché local. Sin archivo no hace nada: los
    sembradores llenan la BD y el primer commit crea la caché."""
    if not DATOS_JSON.exists():
        return
    _aplicar(json.loads(DATOS_JSON.read_text(encoding="utf-8")))


def cargar_estado_inicial() -> None:
    """Atlas manda; la caché local es el plan B."""
    situacion, remoto = sincronizacion.cargar()
    if situacion == "ok":
        _aplicar(remoto)
        volcar_a_json(remoto)
        return

    cargar_desde_json()
    if situacion == "vacio":
        # Atlas configurado pero sin documento todavía: se sube lo que haya en
        # local para que quede sembrado.
        sincronizacion.marcar_sucio()
    elif situacion == "error":
        print(
            "[database] Atlas no responde: se arranca con la caché local. "
            "Ojo, los cambios de esta sesión pueden chocar con lo remoto.",
            file=sys.stderr,
        )


def sincronizar_si_cambio() -> bool:
    """Trae lo que otra laptop haya escrito. True si hubo recarga."""
    datos = sincronizacion.cargar_si_cambio()
    if datos is None:
        return False
    _aplicar(datos)
    volcar_a_json(datos)
    return True


@event.listens_for(Session, "after_commit")
def _volcar_tras_commit(session):
    if _volcado_suspendido:
        return
    # El listener es global (sobre la clase Session); solo debe actuar con el
    # engine real de la app —no con el engine en memoria de los tests—, y un
    # fallo al volcar no debe tumbar la acción del usuario.
    try:
        if session.get_bind() is not engine:
            return
        volcar_a_json()
        sincronizacion.marcar_sucio()
    except Exception as exc:  # pragma: no cover
        print(f"[database] no se pudo volcar el estado: {exc}", file=sys.stderr)

def sembrar_datos() -> None:
    with Session(engine) as session:
        if session.exec(select(Tarea)).first() is not None:
            return

        trabajo = session.exec(select(Categoria).where(Categoria.nombre == "Trabajo")).first()
        trabajo_id = trabajo.id if trabajo else None

        ejemplos = [
            Tarea(
                titulo="Disenar el layout de columnas",
                columna=Columna.por_hacer,
                orden=0,
                etiqueta="diseno",
                categoria_id=trabajo_id,
                prioridad=Prioridad.media,
            ),
            Tarea(
                titulo="Escribir README con GIF",
                columna=Columna.por_hacer,
                orden=1,
                etiqueta="docs",
                categoria_id=trabajo_id,
                prioridad=Prioridad.baja,
            ),
            Tarea(
                titulo="Modelo Tarea con SQLModel",
                columna=Columna.en_progreso,
                orden=0,
                etiqueta="backend",
                categoria_id=trabajo_id,
                prioridad=Prioridad.alta,
            ),
            Tarea(
                titulo="Esqueleto FastAPI + docker-compose",
                columna=Columna.hecho,
                orden=0,
                etiqueta="backend",
                categoria_id=trabajo_id,
                prioridad=Prioridad.media,
            ),
        ]
        session.add_all(ejemplos)
        session.commit()


def sembrar_categorias() -> None:
    with Session(engine) as session:
        if session.exec(select(Categoria)).first() is not None:
            return

        session.add_all(
            [
                Categoria(nombre="Escuela", orden=0, color="#4f8ef7"),
                Categoria(nombre="Trabajo", orden=1, color="#f2994a"),
                Categoria(nombre="Maestría", orden=2, color="#9b59b6"),
            ]
        )
        session.commit()
