from pathlib import Path

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_DIR_STATIC = Path(__file__).parent / "static"


def _estatico(ruta: str) -> str:
    """URL de un archivo en app/static con un `?v=` basado en su mtime, para
    que el navegador lo recargue solo cuando el archivo realmente cambió —
    sin esto, un `<script src="/static/x.js">` sin querystring puede quedar
    servido desde caché de disco del navegador indefinidamente, incluso
    después de un deploy nuevo (nos pasó varias veces con este mismo CSS/JS
    durante el desarrollo: el servidor respondía el archivo correcto por
    curl, pero el navegador seguía ejecutando una versión vieja)."""
    ruta_absoluta = _DIR_STATIC / ruta
    version = int(ruta_absoluta.stat().st_mtime) if ruta_absoluta.exists() else 0
    return f"/static/{ruta}?v={version}"


templates.env.globals["estatico"] = _estatico

_MESES_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _fecha_corta(fecha) -> str:
    """Formatea una fecha como "12 ago" sin depender de %-d/%#d de strftime
    (no son portables entre Linux y Windows)."""
    if fecha is None:
        return ""
    return f"{fecha.day} {_MESES_ES[fecha.month - 1]}"


templates.env.filters["fecha_corta"] = _fecha_corta


def combinar(request, *piezas: tuple[str, dict]) -> HTMLResponse:
    """Concatena varias plantillas ya renderizadas en una sola respuesta.

    Se usa para adjuntar fragmentos hx-swap-oob (contador, resumen) a la
    respuesta principal de un endpoint sin envolver cada uno en su propio
    TemplateResponse."""
    html = "".join(
        templates.get_template(nombre).render({"request": request, **contexto})
        for nombre, contexto in piezas
    )
    return HTMLResponse(html)
