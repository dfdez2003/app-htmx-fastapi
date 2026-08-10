from datetime import date, datetime
from enum import Enum

from sqlmodel import Field, Relationship, SQLModel


class Columna(str, Enum):
    por_hacer = "por_hacer"
    en_progreso = "en_progreso"
    hecho = "hecho"


ETIQUETAS_COLUMNA = {
    Columna.por_hacer: "Por hacer",
    Columna.en_progreso: "En progreso",
    Columna.hecho: "Hecho",
}


class Prioridad(str, Enum):
    alta = "alta"
    media = "media"
    baja = "baja"


# Colores por default para categorías nuevas, asignados por turno según
# cuántas existan ya (ver rutas/categorias.py) — el usuario los puede
# cambiar después desde /configuracion.
PALETA_CATEGORIAS = ["#4f8ef7", "#f2994a", "#9b59b6", "#27ae60", "#e0554f", "#16a2a8"]


class Categoria(SQLModel, table=True):
    """Tipo de tarea (ej. "Escuela", "Trabajo"). Gestionable por el usuario
    desde /configuracion — no es un enum fijo como Columna. Ya no ordena
    filas del tablero (ver Hito 14): solo aporta un color para distinguir
    tareas de distinto tipo dentro de una misma columna."""

    id: int | None = Field(default=None, primary_key=True)
    nombre: str
    orden: int = 0
    color: str = PALETA_CATEGORIAS[0]

    tareas: list["Tarea"] = Relationship(back_populates="categoria")


class Tarea(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    titulo: str
    descripcion: str = ""
    columna: Columna = Columna.por_hacer
    orden: int = 0
    etiqueta: str | None = None
    fecha_limite: date | None = None
    creado_en: datetime = Field(default_factory=datetime.utcnow)
    categoria_id: int | None = Field(default=None, foreign_key="categoria.id")
    prioridad: Prioridad = Prioridad.media

    categoria: Categoria | None = Relationship(back_populates="tareas")

    @property
    def vencida(self) -> bool:
        """Tiene fecha límite pasada y todavía no está en "Hecho"."""
        return (
            self.fecha_limite is not None
            and self.fecha_limite < date.today()
            and self.columna != Columna.hecho
        )
