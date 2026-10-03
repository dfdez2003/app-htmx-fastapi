from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.database import crear_tablas, sembrar_categorias, sembrar_datos, sincronizar_si_cambio
from app.rutas.categorias import router as categorias_router
from app.rutas.cola import router as cola_router
from app.rutas.tablero import router as tablero_router
from app.rutas.tareas import router as tareas_router
from app.sincronizacion import vaciar as vaciar_sincronizacion

# Solo las cargas de página completa preguntan a Atlas si hay algo nuevo. Los
# fragmentos de HTMX (arrastrar, marcar, editar) son la mayoría de las peticiones
# y no deben pagar un viaje de red: cuando llegas a otra laptop, lo primero que
# haces es abrir una de estas rutas.
RUTAS_SINCRONIZABLES = {"/", "/checklist", "/configuracion"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    crear_tablas()
    sembrar_categorias()
    sembrar_datos()
    yield
    # Sube lo que quede pendiente: el volcado remoto es asíncrono y un cambio
    # hecho justo antes de apagar todavía no habría salido.
    await run_in_threadpool(vaciar_sincronizacion)


app = FastAPI(title="Tablero kanban", lifespan=lifespan)


@app.middleware("http")
async def _sincronizar_antes_de_pagina(request: Request, call_next):
    if request.method == "GET" and request.url.path in RUTAS_SINCRONIZABLES:
        # En un hilo aparte: pymongo es bloqueante y esto corre en el loop async.
        await run_in_threadpool(sincronizar_si_cambio)
    return await call_next(request)


app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)
app.include_router(tablero_router)
app.include_router(tareas_router)
app.include_router(categorias_router)
app.include_router(cola_router)


@app.get("/salud")
def salud() -> dict[str, bool]:
    return {"ok": True}
