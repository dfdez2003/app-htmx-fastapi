from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.database import get_session
from app.modelos import Tarea
from app.plantillas import templates
from app.vistas import construir_checklist, construir_columnas, listar_categorias

router = APIRouter()


@router.get("/")
def tablero(request: Request, session: Session = Depends(get_session)):
    tareas = session.exec(select(Tarea).order_by(Tarea.orden)).all()
    columnas = construir_columnas(tareas)
    categorias = listar_categorias(session)
    return templates.TemplateResponse(
        request, "tablero.html", {"columnas": columnas, "categorias": categorias}
    )


@router.get("/checklist")
def checklist(request: Request, session: Session = Depends(get_session)):
    """Misma información que el tablero, en una sola lista: todas las
    tareas ordenadas por estado (por hacer → en progreso → hecho)."""
    tareas = session.exec(select(Tarea).order_by(Tarea.orden)).all()
    lista = construir_checklist(tareas)
    categorias = listar_categorias(session)
    return templates.TemplateResponse(
        request, "checklist.html", {"tareas": lista, "categorias": categorias}
    )
