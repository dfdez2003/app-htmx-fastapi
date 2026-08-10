from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.database import get_session
from app.modelos import PALETA_CATEGORIAS, Categoria, Tarea
from app.plantillas import templates

router = APIRouter()


def _obtener_o_404(session: Session, categoria_id: int) -> Categoria:
    categoria = session.get(Categoria, categoria_id)
    if categoria is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return categoria


def _lista_categorias(request: Request, session: Session):
    categorias = session.exec(select(Categoria).order_by(Categoria.orden)).all()
    return templates.TemplateResponse(
        request, "fragmentos/lista_categorias.html", {"categorias": categorias}
    )


@router.get("/configuracion")
def configuracion(request: Request, session: Session = Depends(get_session)):
    categorias = session.exec(select(Categoria).order_by(Categoria.orden)).all()
    return templates.TemplateResponse(
        request, "configuracion.html", {"categorias": categorias}
    )


@router.post("/categorias")
def crear_categoria(
    request: Request,
    nombre: str = Form(...),
    session: Session = Depends(get_session),
):
    nombre = nombre.strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="El nombre es obligatorio")

    existentes = session.exec(select(Categoria)).all()
    siguiente_orden = max((c.orden for c in existentes), default=-1) + 1
    color = PALETA_CATEGORIAS[len(existentes) % len(PALETA_CATEGORIAS)]

    session.add(Categoria(nombre=nombre, orden=siguiente_orden, color=color))
    session.commit()

    return _lista_categorias(request, session)


@router.put("/categorias/{categoria_id}")
def editar_categoria(
    request: Request,
    categoria_id: int,
    nombre: str = Form(...),
    color: str = Form(...),
    session: Session = Depends(get_session),
):
    categoria = _obtener_o_404(session, categoria_id)
    nombre = nombre.strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="El nombre es obligatorio")

    categoria.nombre = nombre
    categoria.color = color
    session.add(categoria)
    session.commit()

    return _lista_categorias(request, session)


@router.delete("/categorias/{categoria_id}")
def eliminar_categoria(
    request: Request, categoria_id: int, session: Session = Depends(get_session)
):
    categoria = _obtener_o_404(session, categoria_id)

    # Sus tareas no se borran: quedan como "Sin categoría" (pierden el
    # color, nada más — el orden ya vive por columna, no por categoría,
    # así que no hay nada que recompactar).
    huerfanas = session.exec(select(Tarea).where(Tarea.categoria_id == categoria_id)).all()
    for tarea in huerfanas:
        tarea.categoria_id = None
        session.add(tarea)

    session.delete(categoria)
    session.commit()

    return _lista_categorias(request, session)
