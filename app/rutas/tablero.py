from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.database import get_session
from app.modelos import Tarea
from app.plantillas import templates
from app.vistas import construir_filas

router = APIRouter()


@router.get("/")
def tablero(request: Request, session: Session = Depends(get_session)):
    tareas = session.exec(select(Tarea).order_by(Tarea.orden)).all()
    filas = construir_filas(session, tareas)
    return templates.TemplateResponse(request, "tablero.html", {"filas": filas})
