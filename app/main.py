from fastapi import FastAPI

app = FastAPI(title="Tablero kanban")


@app.get("/salud")
def salud() -> dict[str, bool]:
    return {"ok": True}
