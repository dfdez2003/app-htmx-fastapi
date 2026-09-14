"""Construcción de las estructuras que consumen las plantillas del tablero
y del checklist. Compartido entre las rutas de página completa (GET / y
GET /checklist) y la búsqueda en vivo (GET /tareas) para que ambas rindan
exactamente lo mismo.

Desde el Hito 14, la categoría ya no segmenta filas: todas las tareas de
todas las categorías se mezclan en las mismas 3 columnas / la misma lista
de checklist, distinguidas solo por su color."""

from sqlmodel import Session, select

from app.modelos import ETIQUETAS_COLUMNA, Categoria, Columna, Tarea

SIN_CATEGORIA = "sin"


def categoria_id_desde_form(valor: str) -> int | None:
    """Convierte el valor de un campo de formulario (id numérico o el token
    SIN_CATEGORIA) al categoria_id real que se guarda en Tarea."""
    return None if valor in ("", SIN_CATEGORIA) else int(valor)


def aplicar_filtros(consulta, buscar: str = "", etiqueta: str = "", categoria: str = ""):
    """Añade a `consulta` los mismos filtros de la búsqueda en vivo (título,
    etiqueta, categoría). Compartido entre GET /tareas y el re-render tras
    arrastrar/deshacer, para que mover una tarjeta no rompa el filtro activo."""
    buscar = buscar.strip()
    etiqueta = etiqueta.strip()
    categoria = categoria.strip()
    if buscar:
        consulta = consulta.where(Tarea.titulo.ilike(f"%{buscar}%"))
    if etiqueta:
        consulta = consulta.where(Tarea.etiqueta.ilike(f"%{etiqueta}%"))
    if categoria:
        consulta = consulta.where(Tarea.categoria_id == categoria_id_desde_form(categoria))
    return consulta


def listar_categorias(session: Session) -> list[Categoria]:
    """Categorías ordenadas, para poblar los <select> de categoría (filtro
    de búsqueda, formulario de tarea) y el panel de configuración."""
    return session.exec(select(Categoria).order_by(Categoria.orden)).all()


def construir_columnas(tareas: list[Tarea]) -> list[dict]:
    """Agrupa `tareas` en las 3 columnas fijas, sin importar su categoría."""
    return [
        {
            "clave": clave.value,
            "etiqueta": ETIQUETAS_COLUMNA[clave],
            "tareas": [t for t in tareas if t.columna == clave],
        }
        for clave in Columna
    ]


def construir_checklist(tareas: list[Tarea]) -> list[Tarea]:
    """Todas las tareas en una sola lista, ordenadas por estado (por hacer
    → en progreso → hecho) y dentro de cada estado por su `orden`."""
    return _ordenar_por_estado(tareas, invertir=False)


def _ordenar_por_estado(tareas: list[Tarea], invertir: bool) -> list[Tarea]:
    """Ordena por estado (por hacer → en progreso → hecho, o al revés si
    `invertir`) y, dentro de cada estado, por su `orden`. El giro solo
    invierte el orden de los *grupos* de estado, no el orden interno."""
    indice = {clave: i for i, clave in enumerate(Columna)}
    n = len(Columna)
    return sorted(
        tareas,
        key=lambda t: ((n - 1 - indice[t.columna]) if invertir else indice[t.columna], t.orden),
    )


def _columna_de_categoria(tareas: list[Tarea], valor: str, categoria: Categoria | None, invertir: bool) -> dict:
    """Arma el dict de UNA columna de la vista por categoría. `valor` es el
    id de la categoría como string, o SIN_CATEGORIA para las tareas sueltas."""
    if valor == SIN_CATEGORIA:
        propias = [t for t in tareas if t.categoria_id is None]
        nombre, color = "Sin categoría", None
    else:
        cid = int(valor)
        propias = [t for t in tareas if t.categoria_id == cid]
        nombre = categoria.nombre if categoria else "?"
        color = categoria.color if categoria else None
    return {
        "categoria_valor": valor,
        "nombre": nombre,
        "color": color,
        "tareas": _ordenar_por_estado(propias, invertir),
    }


def construir_por_categoria(tareas: list[Tarea], categorias: list[Categoria], invertir: bool = False) -> list[dict]:
    """Una columna por categoría (en su orden) y, al final, una columna
    "Sin categoría" solo si hay tareas sueltas. Cada columna trae sus tareas
    ordenadas por estado (girado o no)."""
    columnas = [
        _columna_de_categoria(tareas, str(cat.id), cat, invertir) for cat in categorias
    ]
    if any(t.categoria_id is None for t in tareas):
        columnas.append(_columna_de_categoria(tareas, SIN_CATEGORIA, None, invertir))
    return columnas


def construir_columna_categoria(tareas: list[Tarea], valor: str, categorias: list[Categoria], invertir: bool) -> dict:
    """Reconstruye una sola columna por su `valor` (id o SIN_CATEGORIA), para
    re-renderizarla tras mover/crear/cambiar estado sin rehacer toda la grilla."""
    categoria = None
    if valor != SIN_CATEGORIA:
        cid = int(valor)
        categoria = next((c for c in categorias if c.id == cid), None)
    return _columna_de_categoria(tareas, valor, categoria, invertir)


def leer_prefs_checklist(request) -> tuple[str, bool]:
    """Preferencias de la vista checklist guardadas en cookies: el modo de
    presentación ("lista" o "categoria") y si el orden de estados está girado.
    Cookies (no sesión ni BD) para que el servidor pinte el modo correcto al
    recargar, sin parpadeo ni una petición extra — igual criterio que el tema."""
    modo = request.cookies.get("checklist_modo", "lista")
    if modo not in ("lista", "categoria"):
        modo = "lista"
    invertir = request.cookies.get("checklist_giro") == "invertido"
    return modo, invertir


def construir_resumen(tareas: list[Tarea]) -> dict:
    """Totales para la cabecera del tablero/checklist (`N tareas · N hechas
    · N vencidas`). Siempre sobre el conjunto completo de tareas, no el
    filtrado por búsqueda — es una foto del tablero entero, no del filtro."""
    return {
        "total": len(tareas),
        "hechas": sum(1 for t in tareas if t.columna == Columna.hecho),
        "vencidas": sum(1 for t in tareas if t.vencida),
    }
