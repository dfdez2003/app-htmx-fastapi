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
    indice_columna = {clave: i for i, clave in enumerate(Columna)}
    return sorted(tareas, key=lambda t: (indice_columna[t.columna], t.orden))


def construir_resumen(tareas: list[Tarea]) -> dict:
    """Totales para la cabecera del tablero/checklist (`N tareas · N hechas
    · N vencidas`). Siempre sobre el conjunto completo de tareas, no el
    filtrado por búsqueda — es una foto del tablero entero, no del filtro."""
    return {
        "total": len(tareas),
        "hechas": sum(1 for t in tareas if t.columna == Columna.hecho),
        "vencidas": sum(1 for t in tareas if t.vencida),
    }
