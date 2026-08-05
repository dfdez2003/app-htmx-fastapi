# PLAN — App con HTMX + FastAPI

> Traduce `SPEC.md` en pasos ejecutables. Reglas de trabajo (commits chicos, probar antes de dar por hecho, confirmar solo en pasos sensibles) heredadas de `PORTAFOLIO.md`, no se repiten aquí.

---

## Hito 1 — Esqueleto del proyecto
- Crear `pyproject.toml` con dependencias: fastapi, uvicorn[standard], sqlmodel, jinja2, python-multipart (para forms), pytest, httpx (TestClient).
- Crear `app/main.py` con una app FastAPI mínima y un endpoint `GET /salud` que devuelva `{"ok": true}`.
- Crear `Dockerfile` y `docker-compose.yml` (puerto 8000, volumen para `data/`).
- **Verificar:** `docker compose up` levanta el contenedor y `curl localhost:8000/salud` responde 200. `uvicorn app.main:app --reload` también corre en local.
- Commit: `chore: estructura base FastAPI + SQLModel + docker-compose`

## Hito 2 — Modelo de datos
- `app/database.py`: engine SQLite (`data/tablero.db`), función `crear_tablas()`, dependencia `get_session`.
- `app/modelos.py`: `Tarea(SQLModel, table=True)` con `id, titulo, descripcion, columna, orden, etiqueta, fecha_limite, creado_en`.
- Sembrar 3-4 tareas de ejemplo repartidas en las columnas al iniciar si la tabla está vacía.
- **Verificar:** al levantar la app se crea `data/tablero.db`; inspeccionar con `sqlite3` que las tareas semilla existen.
- Commit: `feat(modelo): modelo Tarea y datos semilla`

## Hito 3 — Tablero server-rendered
- `app/templates/base.html` (carga htmx.js y sortable.js vendorizados desde `static/vendor/`, `estilos.css`).
- `app/templates/tablero.html`: 3 columnas, cada una itera sus tareas ordenadas por `orden` usando `fragmentos/tarjeta.html`.
- `app/rutas/tablero.py`: `GET /` renderiza `tablero.html` con las tareas agrupadas por columna.
- **Verificar:** abrir `localhost:8000` en el navegador, ver las 3 columnas con las tareas semilla, sin errores en consola.
- Commit: `feat(tablero): pagina principal con 3 columnas server-rendered`

## Hito 4 — Crear tarea
- `fragmentos/formulario_tarea.html` (modo creación) y `fragmentos/tarjeta.html` (vista).
- `POST /tareas`: valida datos, inserta con `orden` al final de su columna, devuelve `tarjeta.html` renderizada.
- Formulario en la UI con `hx-post="/tareas" hx-target="#columna-{col} .lista" hx-swap="beforeend"`.
- **Verificar:** crear una tarea desde el navegador, confirmar que aparece sin recargar y que persiste tras refrescar (F5).
- Commit: `feat(tareas): crear tarea y fragmento de tarjeta`

## Hito 5 — Editar inline y eliminar
- `GET /tareas/{id}/editar` devuelve `formulario_tarea.html` en modo edición.
- `PUT /tareas/{id}` guarda cambios, devuelve `tarjeta.html` actualizada.
- `DELETE /tareas/{id}` elimina y responde vacío; tarjeta tiene `hx-confirm="¿Eliminar esta tarea?"`.
- **Verificar:** editar una tarea inline sin que se mueva el layout de la columna; eliminar y confirmar que desaparece y no vuelve tras F5.
- Commit: `feat(tareas): editar inline y eliminar`

## Hito 6 — Mover entre columnas y reordenar
- Integrar SortableJS en cada `.lista` de columna (`group: "tablero"` para permitir mover entre listas).
- Listener `onEnd` de SortableJS dispara `hx-post` (via `htmx.ajax`) a `PUT /tareas/{id}/mover` con `columna_destino` y `posicion`.
- Endpoint recalcula `orden` de las tareas afectadas en ambas columnas (origen y destino) de forma consistente.
- **Verificar:** arrastrar una tarea a otra columna y a otra posición, refrescar (F5) y confirmar que el orden final coincide con lo que se veía antes del refresh.
- Commit: `feat(tareas): mover entre columnas y reordenar con SortableJS`

## Hito 7 — Contadores y vencidas
- Cada `columna.html` muestra un contador de tareas; calcular server-side.
- Tarjetas con `fecha_limite` pasada se marcan visualmente (clase CSS distinta).
- Respuestas de crear/mover/eliminar incluyen un fragmento `hx-swap-oob="true"` para actualizar el contador de la(s) columna(s) afectada(s) sin re-renderizarla entera.
- **Verificar:** crear/mover/eliminar tareas y ver el contador actualizarse correctamente cada vez; poner una fecha pasada y ver la marca visual.
- Commit: `feat(tablero): contadores y marca de vencidas via hx-swap-oob`

## Hito 8 — Búsqueda en vivo
- Input de búsqueda con `hx-get="/tareas" hx-trigger="keyup changed delay:300ms" hx-target="#tablero-columnas"`.
- `GET /tareas?buscar=&etiqueta=` devuelve las 3 columnas filtradas (reutiliza `columna.html` x3).
- **Verificar:** escribir en el buscador y ver el filtrado sin parpadeos ni perder el foco del input.
- Commit: `feat(busqueda): filtro en vivo por texto y etiqueta`

## Hito 9 — Tests
- `tests/test_tareas.py` con `TestClient`: crear, editar, mover (verificar `orden` recalculado), eliminar, búsqueda.
- **Verificar:** `pytest` pasa en limpio.
- Commit: `test: cobertura de endpoints con TestClient`

## Hito 10 — Cierre
- Revisar `Dockerfile`/`docker-compose.yml` funcionan desde cero (`docker compose up --build` en carpeta limpia, sin `data/` previo).
- Grabar GIF corto mostrando: crear, editar inline, drag-and-drop, búsqueda.
- Completar `README.md` (cómo correr en un comando, GIF, resumen del stack).
- **Verificar:** checklist completo de "Criterios de aceptación" en `SPEC.md`.
- Commit: `chore: Dockerfile, docker-compose y README con GIF`
- Actualizar bitácora de `app-htmx-fastapi` y el checklist de la pieza 6 en `PORTAFOLIO.md` (carpeta padre).

---

## Estado

- [x] Hito 1 — Esqueleto del proyecto
- [x] Hito 2 — Modelo de datos
- [x] Hito 3 — Tablero server-rendered
- [x] Hito 4 — Crear tarea
- [x] Hito 5 — Editar inline y eliminar
- [x] Hito 6 — Mover entre columnas y reordenar
- [ ] Hito 7 — Contadores y vencidas
- [ ] Hito 8 — Búsqueda en vivo
- [ ] Hito 9 — Tests
- [ ] Hito 10 — Cierre
