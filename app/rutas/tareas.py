from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.database import get_session
from app.modelos import Columna, Tarea
from app.plantillas import templates

router = APIRouter()


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
        request, "fragmentos/tarjeta.html", {"tarea": tarea}
    )
