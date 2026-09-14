"""Cola de trabajo: un número manual por tarea (1 = la que estás haciendo,
2 = la siguiente, …) que fija el orden de ejecución del día, independiente de
la posición, el estado o la categoría. Siempre contigua (1..N): cualquier
cambio la renumera. Vive solo en el Tablero.

Las respuestas son puras actualizaciones out-of-band (hx-swap-oob): la lista
del panel lateral y el número/botón de cada tarjeta afectada, para no tocar
las columnas (y así no perder el filtro ni los formularios abiertos)."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.database import get_session
from app.modelos import Tarea
from app.plantillas import combinar

router = APIRouter()


def listar_cola(session: Session) -> list[Tarea]:
    """Tareas en la cola, en orden de ejecución."""
    return session.exec(
        select(Tarea)
        .where(Tarea.orden_ejecucion != None)  # noqa: E711 -> SQL IS NOT NULL
        .order_by(Tarea.orden_ejecucion)
    ).all()


def renumerar_cola(session: Session, orden_ids: list[int]) -> None:
    """Deja la cola exactamente como `orden_ids`: asigna 1..N a esas tareas (en
    ese orden) y saca de la cola (None) a cualquier otra que estuviera. Hace
    commit — es la única fuente de verdad del número de cola."""
    en_lista = set(orden_ids)
    for tarea in listar_cola(session):
        if tarea.id not in en_lista:
            tarea.orden_ejecucion = None
            session.add(tarea)
    for indice, tarea_id in enumerate(orden_ids, start=1):
        tarea = session.get(Tarea, tarea_id)
        if tarea is not None:
            tarea.orden_ejecucion = indice
            session.add(tarea)
    session.commit()


def quitar_de_cola(session: Session, tarea_id: int) -> bool:
    """Saca una tarea de la cola y renumera el resto. Devuelve si estaba en la
    cola (para decidir si hace falta refrescar el panel). Usado también al
    completar o borrar una tarea desde otras rutas."""
    tarea = session.get(Tarea, tarea_id)
    if tarea is None or tarea.orden_ejecucion is None:
        return False
    renumerar_cola(session, [t.id for t in listar_cola(session) if t.id != tarea_id])
    return True


def piezas_cola(session: Session, extra_ids: list[int] | None = None) -> list[tuple[str, dict]]:
    """Piezas oob para adjuntar a cualquier respuesta que cambie la cola: la
    lista del panel y el número de cada tarjeta en cola, más el de las tarjetas
    que acaban de salir (`extra_ids`, para que su tarjeta vuelva a mostrar #)."""
    cola = listar_cola(session)
    piezas: list[tuple[str, dict]] = [("fragmentos/cola_lista.html", {"cola": cola, "oob": True})]
    for tarea in cola:
        piezas.append(("fragmentos/cola_marca.html", {"tarea": tarea, "oob": True}))
    for tarea_id in extra_ids or []:
        tarea = session.get(Tarea, tarea_id)
        if tarea is not None:
            piezas.append(("fragmentos/cola_marca.html", {"tarea": tarea, "oob": True}))
    return piezas


@router.post("/cola/{tarea_id}")
def agregar_a_cola(request: Request, tarea_id: int, session: Session = Depends(get_session)):
    """Agrega la tarea al final de la cola (botón # de la tarjeta)."""
    tarea = session.get(Tarea, tarea_id)
    if tarea is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    if tarea.orden_ejecucion is None:
        renumerar_cola(session, [t.id for t in listar_cola(session)] + [tarea_id])
    return combinar(request, *piezas_cola(session))


@router.delete("/cola/{tarea_id}")
def sacar_de_cola(request: Request, tarea_id: int, session: Session = Depends(get_session)):
    """Quita la tarea de la cola (✕ del panel o del número en la tarjeta)."""
    quitar_de_cola(session, tarea_id)
    return combinar(request, *piezas_cola(session, extra_ids=[tarea_id]))


@router.put("/cola")
def ordenar_cola(request: Request, ids: str = Form(""), session: Session = Depends(get_session)):
    """Fija el orden completo de la cola (reordenar dentro del panel o arrastrar
    una tarjeta al panel). `ids` es la lista ordenada, separada por comas."""
    orden = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    previos = {t.id for t in listar_cola(session)}
    renumerar_cola(session, orden)
    removidos = list(previos - set(orden))
    return combinar(request, *piezas_cola(session, extra_ids=removidos))
