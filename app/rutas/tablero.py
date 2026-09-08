from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app import estado
from app.database import get_session
from app.modelos import Tarea
from app.plantillas import templates
from app.vistas import (
    construir_checklist,
    construir_columnas,
    construir_por_categoria,
    construir_resumen,
    leer_prefs_checklist,
    listar_categorias,
)

router = APIRouter()


@router.get("/")
def tablero(request: Request, session: Session = Depends(get_session)):
    tareas = session.exec(select(Tarea).order_by(Tarea.orden)).all()
    columnas = construir_columnas(tareas)
    categorias = listar_categorias(session)
    resumen = construir_resumen(tareas)
    return templates.TemplateResponse(
        request,
        "tablero.html",
        {
            "columnas": columnas,
            "categorias": categorias,
            "resumen": resumen,
            "puede_deshacer": estado.ultimo_movimiento is not None,
        },
    )


def _contexto_checklist(session: Session, modo: str, giro: bool) -> dict:
    """Contexto común de la vista checklist en cualquiera de sus dos modos:
    "lista" (una sola lista) o "categoria" (una columna por categoría)."""
    tareas = session.exec(select(Tarea).order_by(Tarea.orden)).all()
    categorias = listar_categorias(session)
    contexto = {
        "modo": modo,
        "giro": giro,
        "categorias": categorias,
        "resumen": construir_resumen(tareas),
    }
    if modo == "categoria":
        contexto["columnas_cat"] = construir_por_categoria(tareas, categorias, giro)
    else:
        contexto["tareas"] = construir_checklist(tareas)
    return contexto


@router.get("/checklist")
def checklist(request: Request, session: Session = Depends(get_session)):
    """Vista alterna del tablero. Dos modos, recordados en cookie: "lista"
    (todas las tareas en una sola lista ordenada por estado) y "categoria"
    (una columna por categoría, cada una ordenada por estado, con giro)."""
    modo, giro = leer_prefs_checklist(request)
    contexto = _contexto_checklist(session, modo, giro)
    contexto["puede_deshacer"] = estado.ultimo_movimiento is not None
    return templates.TemplateResponse(request, "checklist.html", contexto)


@router.get("/checklist/vista")
def checklist_vista(
    request: Request,
    modo: str = "lista",
    giro: str = "normal",
    session: Session = Depends(get_session),
):
    """Cambia el modo de presentación o gira el orden de estados. Devuelve el
    panel (controles + contenido) ya renderizado y persiste la elección en
    cookies para que la próxima carga completa arranque igual."""
    if modo not in ("lista", "categoria"):
        modo = "lista"
    invertir = giro == "invertido"
    contexto = _contexto_checklist(session, modo, invertir)
    respuesta = templates.TemplateResponse(request, "fragmentos/checklist_panel.html", contexto)
    respuesta.set_cookie("checklist_modo", modo, max_age=60 * 60 * 24 * 365, samesite="lax")
    respuesta.set_cookie("checklist_giro", giro, max_age=60 * 60 * 24 * 365, samesite="lax")
    return respuesta
