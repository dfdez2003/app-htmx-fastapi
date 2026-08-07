from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine, select

from app.modelos import Categoria, Columna, Tarea

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'tablero.db'}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def crear_tablas() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def sembrar_datos() -> None:
    with Session(engine) as session:
        if session.exec(select(Tarea)).first() is not None:
            return

        ejemplos = [
            Tarea(
                titulo="Disenar el layout de columnas",
                columna=Columna.por_hacer,
                orden=0,
                etiqueta="diseno",
            ),
            Tarea(
                titulo="Escribir README con GIF",
                columna=Columna.por_hacer,
                orden=1,
                etiqueta="docs",
            ),
            Tarea(
                titulo="Modelo Tarea con SQLModel",
                columna=Columna.en_progreso,
                orden=0,
                etiqueta="backend",
            ),
            Tarea(
                titulo="Esqueleto FastAPI + docker-compose",
                columna=Columna.hecho,
                orden=0,
                etiqueta="backend",
            ),
        ]
        session.add_all(ejemplos)
        session.commit()


def sembrar_categorias() -> None:
    with Session(engine) as session:
        if session.exec(select(Categoria)).first() is not None:
            return

        session.add_all(
            [
                Categoria(nombre="Escuela", orden=0),
                Categoria(nombre="Trabajo", orden=1),
                Categoria(nombre="Maestría", orden=2),
            ]
        )
        session.commit()
