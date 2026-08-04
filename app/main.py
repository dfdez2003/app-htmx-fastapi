from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import crear_tablas, sembrar_datos
from app.rutas.tablero import router as tablero_router
from app.rutas.tareas import router as tareas_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    crear_tablas()
    sembrar_datos()
    yield


app = FastAPI(title="Tablero kanban", lifespan=lifespan)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)
app.include_router(tablero_router)
app.include_router(tareas_router)


@app.get("/salud")
def salud() -> dict[str, bool]:
    return {"ok": True}
