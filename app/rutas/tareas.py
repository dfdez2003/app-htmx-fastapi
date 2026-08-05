from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.database import get_session
from app.modelos import Columna, Tarea
from app.plantillas import templates

router = APIRouter()


def _obtener_o_404(session: Session, tarea_id: int) -> Tarea:
    tarea = session.get(Tarea, tarea_id)
    if tarea is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return tarea


@router.post("/tareas")
def crear_tarea(
    request: Request,
    titulo: str = Form(...),
    columna: Columna = Form(...),
    etiqueta: str = Form(""),
    session: Session = Depends(get_session),
):
    titulo = titulo.strip()
    if not titulo:
        raise HTTPException(status_code=422, detail="El título es obligatorio")

    tareas_columna = session.exec(
        select(Tarea).where(Tarea.columna == columna)
    ).all()
    siguiente_orden = max((t.orden for t in tareas_columna), default=-1) + 1

    tarea = Tarea(
        titulo=titulo,
        columna=columna,
        etiqueta=etiqueta.strip() or None,
        orden=siguiente_orden,
    )
    session.add(tarea)
    session.commit()
    session.refresh(tarea)

    return templates.TemplateResponse(
        request,
        "fragmentos/tarea_creada.html",
        {"tarea": tarea, "columna_clave": columna.value, "total": len(tareas_columna) + 1},
    )


@router.get("/tareas/{tarea_id}")
def ver_tarea(request: Request, tarea_id: int, session: Session = Depends(get_session)):
    """Vista de una sola tarjeta. La usa el botón "Cancelar" del formulario
    de edición para volver a la tarjeta sin guardar cambios."""
    tarea = _obtener_o_404(session, tarea_id)
    return templates.TemplateResponse(
        request, "fragmentos/tarjeta.html", {"tarea": tarea}
    )


@router.get("/tareas/{tarea_id}/editar")
def formulario_editar(request: Request, tarea_id: int, session: Session = Depends(get_session)):
    tarea = _obtener_o_404(session, tarea_id)
    return templates.TemplateResponse(
        request,
        "fragmentos/formulario_tarea.html",
        {"modo": "editar", "tarea": tarea},
    )


@router.put("/tareas/{tarea_id}")
def editar_tarea(
    request: Request,
    tarea_id: int,
    titulo: str = Form(...),
    descripcion: str = Form(""),
    etiqueta: str = Form(""),
    fecha_limite: str = Form(""),
    session: Session = Depends(get_session),
):
    tarea = _obtener_o_404(session, tarea_id)

    titulo = titulo.strip()
    if not titulo:
        raise HTTPException(status_code=422, detail="El título es obligatorio")

    tarea.titulo = titulo
    tarea.descripcion = descripcion.strip()
    tarea.etiqueta = etiqueta.strip() or None
    tarea.fecha_limite = date.fromisoformat(fecha_limite) if fecha_limite else None

    session.add(tarea)
    session.commit()
    session.refresh(tarea)

    return templates.TemplateResponse(
        request, "fragmentos/tarjeta.html", {"tarea": tarea}
    )


@router.delete("/tareas/{tarea_id}")
def eliminar_tarea(request: Request, tarea_id: int, session: Session = Depends(get_session)):
    tarea = _obtener_o_404(session, tarea_id)
    columna = tarea.columna
    session.delete(tarea)
    session.commit()

    total = len(session.exec(select(Tarea).where(Tarea.columna == columna)).all())
    return templates.TemplateResponse(
        request, "fragmentos/contador.html", {"columna_clave": columna.value, "total": total}
    )


@router.put("/tareas/{tarea_id}/mover")
def mover_tarea(
    request: Request,
    tarea_id: int,
    columna_destino: Columna = Form(...),
    posicion: int = Form(...),
    session: Session = Depends(get_session),
):
    tarea = _obtener_o_404(session, tarea_id)
    columna_origen = tarea.columna

    # Recalcular la columna destino insertando la tarea en la posición pedida
    # (se excluye a sí misma de la consulta: si es un reordenamiento dentro
    # de la misma columna, esto es lo que permite "sacarla y reinsertarla").
    tareas_destino = session.exec(
        select(Tarea)
        .where(Tarea.columna == columna_destino, Tarea.id != tarea_id)
        .order_by(Tarea.orden)
    ).all()
    posicion = max(0, min(posicion, len(tareas_destino)))
    tareas_destino.insert(posicion, tarea)

    tarea.columna = columna_destino
    for indice, t in enumerate(tareas_destino):
        t.orden = indice
        session.add(t)

    # Si cambió de columna, recompactar también el orden de la columna origen
    if columna_origen != columna_destino:
        tareas_origen = session.exec(
            select(Tarea).where(Tarea.columna == columna_origen).order_by(Tarea.orden)
        ).all()
        for indice, t in enumerate(tareas_origen):
            t.orden = indice
            session.add(t)

    session.commit()

    tareas_destino_final = session.exec(
        select(Tarea).where(Tarea.columna == columna_destino).order_by(Tarea.orden)
    ).all()
    bloques = [{"columna_clave": columna_destino.value, "tareas": tareas_destino_final}]

    if columna_origen != columna_destino:
        tareas_origen_final = session.exec(
            select(Tarea).where(Tarea.columna == columna_origen).order_by(Tarea.orden)
        ).all()
        bloques.append({"columna_clave": columna_origen.value, "tareas": tareas_origen_final})

    return templates.TemplateResponse(
        request, "fragmentos/lista_columna.html", {"bloques": bloques}
    )
