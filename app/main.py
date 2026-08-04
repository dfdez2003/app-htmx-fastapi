from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import crear_tablas, sembrar_datos


@asynccontextmanager
async def lifespan(app: FastAPI):
    crear_tablas()
    sembrar_datos()
    yield


app = FastAPI(title="Tablero kanban", lifespan=lifespan)


@app.get("/salud")
def salud() -> dict[str, bool]:
    return {"ok": True}
