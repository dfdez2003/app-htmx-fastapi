from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.database import get_session
from app.modelos import ETIQUETAS_COLUMNA, Columna, Tarea
from app.plantillas import templates

router = APIRouter()


@router.get("/")
def tablero(request: Request, session: Session = Depends(get_session)):
    tareas = session.exec(select(Tarea).order_by(Tarea.orden)).all()
    columnas = [
        {
            "clave": clave.value,
            "etiqueta": ETIQUETAS_COLUMNA[clave],
            "tareas": [t for t in tareas if t.columna == clave],
        }
        for clave in Columna
    ]
    return templates.TemplateResponse(
        request, "tablero.html", {"columnas": columnas}
    )
