from pathlib import Path

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

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
