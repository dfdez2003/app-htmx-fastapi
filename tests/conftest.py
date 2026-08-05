import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.main import app


@pytest.fixture()
def engine():
    """Motor SQLite en memoria, aislado por test (no toca data/tablero.db)."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture()
def client(engine):
    def _get_session_prueba():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session_prueba
    # Sin "with": evita disparar el lifespan de app.main (crear_tablas/
    # sembrar_datos), que trabaja sobre el engine real de app.database.
    yield TestClient(app)
    app.dependency_overrides.clear()
