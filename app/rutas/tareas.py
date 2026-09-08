from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from app import estado
from app.database import get_session
from app.modelos import Columna, Prioridad, Tarea
from app.plantillas import combinar, templates
from app.vistas import (
    SIN_CATEGORIA,
    categoria_id_desde_form,
    construir_checklist,
    construir_columna_categoria,
    construir_columnas,
    construir_por_categoria,
    construir_resumen,
    leer_prefs_checklist,
    listar_categorias,
)

router = APIRouter()


def _obtener_o_404(session: Session, tarea_id: int) -> Tarea:
    tarea = session.get(Tarea, tarea_id)
    if tarea is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return tarea


def _resumen_oob(session: Session) -> tuple[str, dict]:
    """Fragmento hx-swap-oob del resumen de la cabecera (`N tareas · N
    hechas · N vencidas`), para adjuntar a la respuesta de cualquier
    endpoint que cree/edite/mueva/borre una tarea."""
    todas = session.exec(select(Tarea)).all()
    return ("fragmentos/resumen.html", {"resumen": construir_resumen(todas), "oob": True})


def _columna_categoria_pieza(session: Session, request: Request, valor: str, oob: bool = False) -> tuple[str, dict]:
    """Fragmento de UNA columna de la vista por categoría, re-renderizada
    desde el estado actual de la BD. La usan crear/mover/estado/borrar en modo
    "categoria" para que la columna siempre refleje el orden por estado."""
    _, giro = leer_prefs_checklist(request)
    todas = session.exec(select(Tarea)).all()
    categorias = listar_categorias(session)
    col = construir_columna_categoria(todas, valor, categorias, giro)
    return ("fragmentos/columna_categoria.html", {"col": col, "oob": oob})


def _valor_categoria(tarea: Tarea) -> str:
    """El id de categoría de una tarea como string, o SIN_CATEGORIA si no tiene."""
    return SIN_CATEGORIA if tarea.categoria_id is None else str(tarea.categoria_id)


ORDEN_ESTADOS = [Columna.por_hacer, Columna.en_progreso, Columna.hecho]


def _reinsertar(session: Session, tarea: Tarea, columna_destino: Columna, posicion: int) -> bool:
    """Núcleo compartido de mover/deshacer: reinserta `tarea` en
    `columna_destino` en la posición pedida, recompactando el `orden` de
    destino y (si cambió) también el de origen. Devuelve si cambió de
    columna. No hace commit — lo decide quien llama."""
    columna_origen = tarea.columna
    cambia_columna = columna_origen != columna_destino

    tareas_destino = session.exec(
        select(Tarea)
        .where(Tarea.columna == columna_destino, Tarea.id != tarea.id)
        .order_by(Tarea.orden)
    ).all()
    posicion = max(0, min(posicion, len(tareas_destino)))
    tareas_destino.insert(posicion, tarea)

    tarea.columna = columna_destino
    for indice, t in enumerate(tareas_destino):
        t.orden = indice
        session.add(t)

    if cambia_columna:
        tareas_origen = session.exec(
            select(Tarea).where(Tarea.columna == columna_origen).order_by(Tarea.orden)
        ).all()
        for indice, t in enumerate(tareas_origen):
            t.orden = indice
            session.add(t)

    return cambia_columna


def _bloques_tras_mover(session: Session, columna_destino: Columna, columna_origen: Columna, cambia_columna: bool) -> list[dict]:
    tareas_destino_final = session.exec(
        select(Tarea).where(Tarea.columna == columna_destino).order_by(Tarea.orden)
    ).all()
    bloques = [{"columna_clave": columna_destino.value, "tareas": tareas_destino_final}]
    if cambia_columna:
        tareas_origen_final = session.exec(
            select(Tarea).where(Tarea.columna == columna_origen).order_by(Tarea.orden)
        ).all()
        bloques.append({"columna_clave": columna_origen.value, "tareas": tareas_origen_final})
    return bloques


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
        modo, giro = leer_prefs_checklist(request)
        if modo == "categoria":
            return templates.TemplateResponse(
                request,
                "fragmentos/grid_categorias.html",
                {
                    "columnas_cat": construir_por_categoria(tareas, listar_categorias(session), giro),
                    "giro": giro,
                },
            )
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
    origen: str = Form(""),
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

    # Creada desde una columna de la vista por categoría: se re-renderiza esa
    # columna entera (para que la tarea nueva caiga en su grupo de estado),
    # en vez de agregar una tarjeta suelta como en el tablero.
    if origen == "categoria":
        return combinar(
            request,
            _columna_categoria_pieza(session, request, categoria or SIN_CATEGORIA),
            _resumen_oob(session),
        )

    return combinar(
        request,
        (
            "fragmentos/tarea_creada.html",
            {"tarea": tarea, "columna_clave": columna.value, "total": len(tareas_columna) + 1},
        ),
        _resumen_oob(session),
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

    return combinar(
        request,
        ("fragmentos/tarjeta.html", {"tarea": tarea}),
        _resumen_oob(session),
    )


@router.delete("/tareas/{tarea_id}")
def eliminar_tarea(
    request: Request,
    tarea_id: int,
    vista: str = "",
    session: Session = Depends(get_session),
):
    tarea = _obtener_o_404(session, tarea_id)
    columna = tarea.columna
    valor_categoria = _valor_categoria(tarea)
    session.delete(tarea)
    session.commit()

    # Si lo último deshacible era mover justo esta tarea, ya no hay a qué
    # volver: se borró. Evita un 404 al pulsar "deshacer" después.
    if estado.ultimo_movimiento and estado.ultimo_movimiento["tarea_id"] == tarea_id:
        estado.ultimo_movimiento = None

    # En la vista por categoría se re-renderiza la columna (para actualizar su
    # cuenta); en tablero/lista basta con actualizar el contador de la columna.
    if vista == "categoria":
        return combinar(
            request,
            _columna_categoria_pieza(session, request, valor_categoria),
            _resumen_oob(session),
        )

    total = len(session.exec(select(Tarea).where(Tarea.columna == columna)).all())
    return combinar(
        request,
        ("fragmentos/contador.html", {"columna_clave": columna.value, "total": total}),
        _resumen_oob(session),
    )


@router.put("/tareas/{tarea_id}/estado")
def ciclar_estado(
    request: Request,
    tarea_id: int,
    vista: str = "",
    session: Session = Depends(get_session),
):
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

    # En la vista por categoría, cambiar de estado reordena la tarjeta dentro
    # de su columna, así que se re-renderiza la columna completa; en la lista
    # única basta con actualizar el ítem en su sitio (el ícono de estado).
    if vista == "categoria":
        return combinar(
            request,
            _columna_categoria_pieza(session, request, _valor_categoria(tarea)),
            _resumen_oob(session),
        )

    return combinar(
        request,
        ("fragmentos/item_checklist.html", {"tarea": tarea}),
        _resumen_oob(session),
    )


@router.put("/tareas/{tarea_id}/categoria")
def recategorizar_tarea(
    request: Request,
    tarea_id: int,
    categoria_valor: str = Form(...),
    session: Session = Depends(get_session),
):
    """Reasigna la categoría de una tarea al soltarla en otra columna de la
    vista por categoría. No toca su estado ni su orden: la tarea reaparece en
    su mismo grupo de estado, ahora dentro de la columna destino. Devuelve la
    columna destino (target) y, si cambió, la de origen (oob)."""
    tarea = _obtener_o_404(session, tarea_id)
    origen_valor = _valor_categoria(tarea)

    tarea.categoria_id = categoria_id_desde_form(categoria_valor)
    session.add(tarea)
    session.commit()

    destino_valor = _valor_categoria(tarea)
    piezas = [_columna_categoria_pieza(session, request, destino_valor)]
    if destino_valor != origen_valor:
        piezas.append(_columna_categoria_pieza(session, request, origen_valor, oob=True))
    piezas.append(_resumen_oob(session))
    return combinar(request, *piezas)


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

    # Snapshot de "dónde estaba" antes de moverla, para poder deshacer este
    # movimiento con un clic (ver /tareas/deshacer): su posición dentro de
    # su columna de origen, tal como estaba justo antes del drag.
    tareas_origen_antes = session.exec(
        select(Tarea).where(Tarea.columna == columna_origen).order_by(Tarea.orden)
    ).all()
    posicion_origen = next(i for i, t in enumerate(tareas_origen_antes) if t.id == tarea_id)

    cambia_columna = _reinsertar(session, tarea, columna_destino, posicion)
    session.commit()

    estado.ultimo_movimiento = {
        "tarea_id": tarea_id,
        "columna_origen": columna_origen.value,
        "posicion_origen": posicion_origen,
    }

    bloques = _bloques_tras_mover(session, columna_destino, columna_origen, cambia_columna)

    return combinar(
        request,
        ("fragmentos/lista_columna.html", {"bloques": bloques}),
        _resumen_oob(session),
        ("fragmentos/boton_deshacer.html", {"puede_deshacer": True, "oob": True}),
    )


@router.post("/tareas/deshacer")
def deshacer_movimiento(request: Request, session: Session = Depends(get_session)):
    """Revierte el último drag-and-drop (un solo nivel, ver `app/estado.py`).
    Sin nada que deshacer, es un no-op que solo confirma el botón deshabilitado."""
    datos = estado.ultimo_movimiento
    if datos is None:
        return combinar(request, ("fragmentos/boton_deshacer.html", {"puede_deshacer": False}))

    estado.ultimo_movimiento = None
    tarea = _obtener_o_404(session, datos["tarea_id"])
    columna_actual = tarea.columna
    columna_origen = Columna(datos["columna_origen"])

    cambia_columna = _reinsertar(session, tarea, columna_origen, datos["posicion_origen"])
    session.commit()

    bloques = _bloques_tras_mover(session, columna_origen, columna_actual, cambia_columna)

    return combinar(
        request,
        ("fragmentos/boton_deshacer.html", {"puede_deshacer": False}),
        ("fragmentos/lista_columna.html", {"bloques": bloques, "todas_oob": True}),
        _resumen_oob(session),
    )
