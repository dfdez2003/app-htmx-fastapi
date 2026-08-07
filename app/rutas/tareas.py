from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.database import get_session
from app.modelos import Columna, Prioridad, Tarea
from app.plantillas import templates
from app.vistas import SIN_CATEGORIA, categoria_id_desde_form, construir_filas

router = APIRouter()


def _obtener_o_404(session: Session, tarea_id: int) -> Tarea:
    tarea = session.get(Tarea, tarea_id)
    if tarea is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return tarea


def _fila_id(categoria_id: int | None) -> str:
    return SIN_CATEGORIA if categoria_id is None else str(categoria_id)


@router.get("/tareas")
def buscar_tareas(
    request: Request,
    buscar: str = "",
    etiqueta: str = "",
    session: Session = Depends(get_session),
):
    """Filas filtradas por texto (título) y/o etiqueta, para la búsqueda en
    vivo. Sin filtros, equivale al tablero completo."""
    consulta = select(Tarea).order_by(Tarea.orden)
    buscar = buscar.strip()
    etiqueta = etiqueta.strip()
    if buscar:
        consulta = consulta.where(Tarea.titulo.ilike(f"%{buscar}%"))
    if etiqueta:
        consulta = consulta.where(Tarea.etiqueta.ilike(f"%{etiqueta}%"))

    tareas = session.exec(consulta).all()
    filas = construir_filas(session, tareas)
    return templates.TemplateResponse(request, "fragmentos/filas.html", {"filas": filas})


@router.post("/tareas")
def crear_tarea(
    request: Request,
    titulo: str = Form(...),
    columna: Columna = Form(...),
    categoria: str = Form(SIN_CATEGORIA),
    etiqueta: str = Form(""),
    session: Session = Depends(get_session),
):
    titulo = titulo.strip()
    if not titulo:
        raise HTTPException(status_code=422, detail="El título es obligatorio")

    categoria_id = categoria_id_desde_form(categoria)

    tareas_celda = session.exec(
        select(Tarea).where(Tarea.columna == columna, Tarea.categoria_id == categoria_id)
    ).all()
    siguiente_orden = max((t.orden for t in tareas_celda), default=-1) + 1

    tarea = Tarea(
        titulo=titulo,
        columna=columna,
        categoria_id=categoria_id,
        etiqueta=etiqueta.strip() or None,
        orden=siguiente_orden,
    )
    session.add(tarea)
    session.commit()
    session.refresh(tarea)

    return templates.TemplateResponse(
        request,
        "fragmentos/tarea_creada.html",
        {
            "tarea": tarea,
            "columna_clave": columna.value,
            "fila_id": _fila_id(categoria_id),
            "total": len(tareas_celda) + 1,
        },
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
    prioridad: Prioridad = Form(Prioridad.media),
    session: Session = Depends(get_session),
):
    tarea = _obtener_o_404(session, tarea_id)

    titulo = titulo.strip()
    if not titulo:
        raise HTTPException(status_code=422, detail="El título es obligatorio")

    # Categoría y columna no se tocan aquí — se cambian arrastrando en el
    # tablero (igual que ya pasaba con columna antes de este hito), para no
    # dejar la tarjeta visualmente en la celda vieja tras un swap in-place.
    tarea.titulo = titulo
    tarea.descripcion = descripcion.strip()
    tarea.etiqueta = etiqueta.strip() or None
    tarea.fecha_limite = date.fromisoformat(fecha_limite) if fecha_limite else None
    tarea.prioridad = prioridad

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
    categoria_id = tarea.categoria_id
    session.delete(tarea)
    session.commit()

    total = len(
        session.exec(
            select(Tarea).where(Tarea.columna == columna, Tarea.categoria_id == categoria_id)
        ).all()
    )
    return templates.TemplateResponse(
        request,
        "fragmentos/contador.html",
        {"fila_id": _fila_id(categoria_id), "columna_clave": columna.value, "total": total},
    )


@router.put("/tareas/{tarea_id}/mover")
def mover_tarea(
    request: Request,
    tarea_id: int,
    columna_destino: Columna = Form(...),
    categoria_destino: str = Form(SIN_CATEGORIA),
    posicion: int = Form(...),
    session: Session = Depends(get_session),
):
    tarea = _obtener_o_404(session, tarea_id)
    columna_origen = tarea.columna
    categoria_origen_id = tarea.categoria_id
    categoria_destino_id = categoria_id_desde_form(categoria_destino)
    cambia_celda = (columna_origen, categoria_origen_id) != (columna_destino, categoria_destino_id)

    # Recalcular la celda destino insertando la tarea en la posición pedida
    # (se excluye a sí misma de la consulta: si es un reordenamiento dentro
    # de la misma celda, esto es lo que permite "sacarla y reinsertarla").
    tareas_destino = session.exec(
        select(Tarea)
        .where(
            Tarea.columna == columna_destino,
            Tarea.categoria_id == categoria_destino_id,
            Tarea.id != tarea_id,
        )
        .order_by(Tarea.orden)
    ).all()
    posicion = max(0, min(posicion, len(tareas_destino)))
    tareas_destino.insert(posicion, tarea)

    tarea.columna = columna_destino
    tarea.categoria_id = categoria_destino_id
    for indice, t in enumerate(tareas_destino):
        t.orden = indice
        session.add(t)

    # Si cambió de celda, recompactar también el orden de la celda origen
    if cambia_celda:
        tareas_origen = session.exec(
            select(Tarea)
            .where(Tarea.columna == columna_origen, Tarea.categoria_id == categoria_origen_id)
            .order_by(Tarea.orden)
        ).all()
        for indice, t in enumerate(tareas_origen):
            t.orden = indice
            session.add(t)

    session.commit()

    tareas_destino_final = session.exec(
        select(Tarea)
        .where(Tarea.columna == columna_destino, Tarea.categoria_id == categoria_destino_id)
        .order_by(Tarea.orden)
    ).all()
    bloques = [
        {
            "fila_id": _fila_id(categoria_destino_id),
            "columna_clave": columna_destino.value,
            "tareas": tareas_destino_final,
        }
    ]

    if cambia_celda:
        tareas_origen_final = session.exec(
            select(Tarea)
            .where(Tarea.columna == columna_origen, Tarea.categoria_id == categoria_origen_id)
            .order_by(Tarea.orden)
        ).all()
        bloques.append(
            {
                "fila_id": _fila_id(categoria_origen_id),
                "columna_clave": columna_origen.value,
                "tareas": tareas_origen_final,
            }
        )

    return templates.TemplateResponse(
        request, "fragmentos/lista_columna.html", {"bloques": bloques}
    )
