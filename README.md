# App con HTMX + FastAPI

App con reactividad ligera usando HTMX y FastAPI, sin JS pesado en el frontend — demuestra criterio al elegir herramientas simples para el problema.

## Estado
En specs, sin implementar todavía. Ver [`SPEC.md`](./SPEC.md) para alcance completo, stack, estructura de carpetas, criterios de aceptación y orden de commits sugerido. El plan de desarrollo con hitos accionables está en [`PLAN.md`](./PLAN.md).

## Stack
Python 3.11+, FastAPI, HTMX, SQLModel (SQLite), Jinja2, SortableJS.

## Cómo correr
Desde la carpeta del proyecto:

```bash
./agenda build
```

El primer arranque necesita `build`. Después, para levantarla rápidamente en
segundo plano:

```bash
./agenda run
```

La app queda disponible en <http://localhost:8100>. Otros comandos útiles son
`./agenda stop`, `./agenda status` y `./agenda log`.

Para poder escribir `agenda run` sin `./`, ejecuta una vez:

```bash
./agenda install
```

Vuelve a ejecutar `./agenda build` cuando cambien el `Dockerfile`,
`pyproject.toml` o el código de la aplicación. Los cambios en `datos/` no
requieren reconstrucción.

## Parte del portafolio
Este repo es la pieza 6 del portafolio general. Contexto y bitácora: `PORTAFOLIO.md` en la carpeta padre (`~/portafolio/`).
