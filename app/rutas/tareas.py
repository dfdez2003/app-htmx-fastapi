from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app.database import get_session
from app.modelos import Columna, Prioridad, Tarea
from app.plantillas import templates
from app.vistas import (
    SIN_CATEGORIA,
    categoria_id_desde_form,
    construir_checklist,
    construir_columnas,
    listar_categorias,
)

router = APIRouter()


def _obtener_o_404(session: Session, tarea_id: int) -> Tarea:
    tarea = session.get(Tarea, tarea_id)
    if tarea is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return tarea


ORDEN_ESTADOS = [Columna.por_hacer, Columna.en_progreso, Columna.hecho]


@router.get("/tareas")
def buscar_tareas(
    request: Request,
    buscar: str = "",
    etiqueta: str = "",
    categoria: str = "",
    vista: str = "tablero",
    session: Session = Depends(get_session),
):
    """Tareas filtradas por texto (título), etiqueta y/o categoría, para la
    búsqueda en vivo. Sin filtros, equivale a la vista completa.

    `vista` decide el fragmento de salida: "tablero" (3 columnas, default)
    o "checklist" (lista única) — mismas tareas, distinto renderizado."""
    consulta = select(Tarea).order_by(Tarea.orden)
    buscar = buscar.strip()
    etiqueta = etiqueta.strip()
    categoria = categoria.strip()
    if buscar:
        consulta = consulta.where(Tarea.titulo.ilike(f"%{buscar}%"))
    if etiqueta:
        consulta = consulta.where(Tarea.etiqueta.ilike(f"%{etiqueta}%"))
    if categoria:
        consulta = consulta.where(Tarea.categoria_id == categoria_id_desde_form(categoria))

    tareas = session.exec(consulta).all()

    if vista == "checklist":
        return templates.TemplateResponse(
            request, "fragmentos/lista_checklist.html", {"tareas": construir_checklist(tareas)}
        )
    return templates.TemplateResponse(
        request, "fragmentos/columnas.html",
        {"columnas": construir_columnas(tareas), "categorias": listar_categorias(session)},
    )


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

    tareas_columna = session.exec(select(Tarea).where(Tarea.columna == columna)).all()
    siguiente_orden = max((t.orden for t in tareas_columna), default=-1) + 1

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
            "total": len(tareas_columna) + 1,
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
        {"modo": "editar", "tarea": tarea, "categorias": listar_categorias(session)},
    )


@router.put("/tareas/{tarea_id}")
def editar_tarea(
    request: Request,
    tarea_id: int,
    titulo: str = Form(...),
    descripcion: str = Form(""),
    etiqueta: str = Form(""),
    fecha_limite: str = Form(""),
    categoria: str = Form(SIN_CATEGORIA),
    prioridad: Prioridad = Form(Prioridad.media),
    session: Session = Depends(get_session),
):
    tarea = _obtener_o_404(session, tarea_id)

    titulo = titulo.strip()
    if not titulo:
        raise HTTPException(status_code=422, detail="El título es obligatorio")

    # La columna no se toca aquí — se cambia arrastrando en el tablero (un
    # swap in-place no puede reubicar la tarjeta a otra lista). La categoría
    # sí es editable desde el formulario: desde el Hito 14 solo cambia el
    # color de la tarjeta, no su posición, así que no hay nada que reubicar.
    tarea.titulo = titulo
    tarea.descripcion = descripcion.strip()
    tarea.etiqueta = etiqueta.strip() or None
    tarea.fecha_limite = date.fromisoformat(fecha_limite) if fecha_limite else None
    tarea.categoria_id = categoria_id_desde_form(categoria)
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
    session.delete(tarea)
    session.commit()

    total = len(session.exec(select(Tarea).where(Tarea.columna == columna)).all())
    return templates.TemplateResponse(
        request,
        "fragmentos/contador.html",
        {"columna_clave": columna.value, "total": total},
    )


@router.put("/tareas/{tarea_id}/estado")
def ciclar_estado(request: Request, tarea_id: int, session: Session = Depends(get_session)):
    """Avanza por_hacer → en_progreso → hecho → por_hacer. Usado por el
    ícono de estado de la vista checklist en vez de arrastrar."""
    tarea = _obtener_o_404(session, tarea_id)
    indice_actual = ORDEN_ESTADOS.index(tarea.columna)
    nueva_columna = ORDEN_ESTADOS[(indice_actual + 1) % len(ORDEN_ESTADOS)]

    # Recompactar la columna de origen
    tareas_origen = session.exec(
        select(Tarea)
        .where(Tarea.columna == tarea.columna, Tarea.id != tarea_id)
        .order_by(Tarea.orden)
    ).all()
    for indice, t in enumerate(tareas_origen):
        t.orden = indice
        session.add(t)

    # Va al final de la columna destino
    tareas_destino = session.exec(select(Tarea).where(Tarea.columna == nueva_columna)).all()
    tarea.columna = nueva_columna
    tarea.orden = max((t.orden for t in tareas_destino), default=-1) + 1

    session.add(tarea)
    session.commit()
    session.refresh(tarea)

    return templates.TemplateResponse(
        request, "fragmentos/item_checklist.html", {"tarea": tarea}
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
    cambia_columna = columna_origen != columna_destino

    # Recalcular la columna destino insertando la tarea en la posición
    # pedida (se excluye a sí misma de la consulta: si es un reordenamiento
    # dentro de la misma columna, esto permite "sacarla y reinsertarla").
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
    if cambia_columna:
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

    if cambia_columna:
        tareas_origen_final = session.exec(
            select(Tarea).where(Tarea.columna == columna_origen).order_by(Tarea.orden)
        ).all()
        bloques.append({"columna_clave": columna_origen.value, "tareas": tareas_origen_final})

    return templates.TemplateResponse(
        request, "fragmentos/lista_columna.html", {"bloques": bloques}
    )
