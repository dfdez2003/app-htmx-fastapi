from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.database import get_session
from app.modelos import Tarea
from app.plantillas import templates
from app.vistas import construir_filas, listar_categorias

router = APIRouter()


@router.get("/")
def tablero(request: Request, session: Session = Depends(get_session)):
    tareas = session.exec(select(Tarea).order_by(Tarea.orden)).all()
    filas = construir_filas(session, tareas)
    categorias = listar_categorias(session)
    return templates.TemplateResponse(
        request, "tablero.html", {"filas": filas, "categorias": categorias}
    )


@router.get("/checklist")
def checklist(request: Request, session: Session = Depends(get_session)):
    """Misma información que el tablero, aplanada por categoría: cada fila
    lista sus tareas por hacer → en progreso → hecho una tras otra, en vez
    de en columnas separadas."""
    tareas = session.exec(select(Tarea).order_by(Tarea.orden)).all()
    filas = construir_filas(session, tareas)
    categorias = listar_categorias(session)
    return templates.TemplateResponse(
        request, "checklist.html", {"filas": filas, "categorias": categorias}
    )
