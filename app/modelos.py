from datetime import date, datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class Columna(str, Enum):
    por_hacer = "por_hacer"
    en_progreso = "en_progreso"
    hecho = "hecho"


ETIQUETAS_COLUMNA = {
    Columna.por_hacer: "Por hacer",
    Columna.en_progreso: "En progreso",
    Columna.hecho: "Hecho",
}


class Tarea(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    titulo: str
    descripcion: str = ""
    columna: Columna = Columna.por_hacer
    orden: int = 0
    etiqueta: str | None = None
    fecha_limite: date | None = None
    creado_en: datetime = Field(default_factory=datetime.utcnow)

    @property
    def vencida(self) -> bool:
        """Tiene fecha límite pasada y todavía no está en "Hecho"."""
        return (
            self.fecha_limite is not None
            and self.fecha_limite < date.today()
            and self.columna != Columna.hecho
        )
