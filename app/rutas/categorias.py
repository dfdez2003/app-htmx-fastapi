from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.database import get_session
from app.modelos import Categoria, Columna, Tarea
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

    session.add(Categoria(nombre=nombre, orden=siguiente_orden))
    session.commit()

    return _lista_categorias(request, session)


@router.put("/categorias/{categoria_id}")
def renombrar_categoria(
    request: Request,
    categoria_id: int,
    nombre: str = Form(...),
    session: Session = Depends(get_session),
):
    categoria = _obtener_o_404(session, categoria_id)
    nombre = nombre.strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="El nombre es obligatorio")

    categoria.nombre = nombre
    session.add(categoria)
    session.commit()

    return _lista_categorias(request, session)


@router.delete("/categorias/{categoria_id}")
def eliminar_categoria(
    request: Request, categoria_id: int, session: Session = Depends(get_session)
):
    categoria = _obtener_o_404(session, categoria_id)

    # Sus tareas no se borran: quedan como "Sin categoría".
    huerfanas = session.exec(select(Tarea).where(Tarea.categoria_id == categoria_id)).all()
    for tarea in huerfanas:
        tarea.categoria_id = None
        session.add(tarea)

    session.delete(categoria)
    session.commit()

    # El orden de las huérfanas venía de su celda anterior y puede chocar con
    # el de tareas que ya estaban en "Sin categoría" — se recompacta por
    # columna para que quede consistente (0, 1, 2... sin huecos ni empates).
    for clave in Columna:
        tareas_sin_categoria = session.exec(
            select(Tarea)
            .where(Tarea.categoria_id.is_(None), Tarea.columna == clave)
            .order_by(Tarea.orden, Tarea.id)
        ).all()
        for indice, tarea in enumerate(tareas_sin_categoria):
            tarea.orden = indice
            session.add(tarea)
    session.commit()

    return _lista_categorias(request, session)


@router.put("/categorias/{categoria_id}/mover")
def mover_categoria(
    request: Request,
    categoria_id: int,
    direccion: str = Form(...),
    session: Session = Depends(get_session),
):
    categoria = _obtener_o_404(session, categoria_id)
    categorias = session.exec(select(Categoria).order_by(Categoria.orden)).all()
    indice = categorias.index(categoria)

    vecina = None
    if direccion == "arriba" and indice > 0:
        vecina = categorias[indice - 1]
    elif direccion == "abajo" and indice < len(categorias) - 1:
        vecina = categorias[indice + 1]

    if vecina is not None:
        categoria.orden, vecina.orden = vecina.orden, categoria.orden
        session.add(categoria)
        session.add(vecina)
        session.commit()

    return _lista_categorias(request, session)
