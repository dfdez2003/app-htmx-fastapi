"""Construcción de las filas del tablero (swimlanes: categoría x columna).

Compartido entre GET / (tablero completo) y GET /tareas (búsqueda en vivo)
para que ambos rutas rendericen exactamente la misma estructura.
"""

from sqlmodel import Session, select

from app.modelos import ETIQUETAS_COLUMNA, Categoria, Columna, Tarea

SIN_CATEGORIA = "sin"


def categoria_id_desde_form(valor: str) -> int | None:
    """Convierte el valor de un campo de formulario (id numérico o el token
    SIN_CATEGORIA) al categoria_id real que se guarda en Tarea."""
    return None if valor in ("", SIN_CATEGORIA) else int(valor)


def listar_categorias(session: Session) -> list[Categoria]:
    """Categorías ordenadas, para poblar el <select> de filtro de búsqueda
    y el panel de configuración."""
    return session.exec(select(Categoria).order_by(Categoria.orden)).all()


def construir_filas(session: Session, tareas: list[Tarea]) -> list[dict]:
    """Agrupa `tareas` en filas por categoría (ordenadas por Categoria.orden,
    más una fila fija "Sin categoría" al final), cada una con sus 3 columnas."""
    categorias = listar_categorias(session)

    def bloque_columnas(categoria_id: int | None) -> list[dict]:
        return [
            {
                "clave": clave.value,
                "etiqueta": ETIQUETAS_COLUMNA[clave],
                "tareas": [
                    t for t in tareas if t.columna == clave and t.categoria_id == categoria_id
                ],
            }
            for clave in Columna
        ]

    filas = [
        {"id": str(categoria.id), "nombre": categoria.nombre, "columnas": bloque_columnas(categoria.id)}
        for categoria in categorias
    ]
    filas.append(
        {"id": SIN_CATEGORIA, "nombre": "Sin categoría", "columnas": bloque_columnas(None)}
    )
    return filas
