# SPEC — App con HTMX + FastAPI

> Pieza 6 del plan. Demuestra criterio al elegir herramientas simples: reactividad ligera sin arrastrar un framework SPA.
> Contexto general y bitácora: ver `PORTAFOLIO.md` en la carpeta padre (`~/portafolio/`).

---

## Objetivo

Un tablero kanban de tareas (crear, editar inline, mover entre columnas, reordenar, buscar) donde toda la interactividad se resuelve con HTMX pidiendo fragmentos HTML al servidor — cero SPA, cero build step, cero estado de UI duplicado en el cliente. El servidor es siempre la fuente de verdad.

## Alcance

**Dentro:**
- Un solo tablero, tres columnas fijas: Por hacer / En progreso / Hecho
- CRUD de tareas: crear, editar inline (título, descripción, etiqueta, fecha límite), eliminar
- Mover tareas entre columnas y reordenar dentro de una columna (drag-and-drop), persistido en servidor
- Búsqueda/filtro en vivo por texto y etiqueta, sin recargar página
- Contador de tareas por columna y marca visual de tareas vencidas, actualizados tras cada acción
- Persistencia en SQLite

**Fuera:**
- Autenticación, multi-usuario o colaboración en tiempo real entre varios clientes conectados
- Múltiples tableros
- Adjuntos, comentarios, subtareas

## Stack

- **Backend:** Python 3.11+ + FastAPI + Uvicorn
- **Plantillas:** Jinja2 (HTML server-rendered, fragmentos parciales para cada respuesta HTMX)
- **Reactividad:** HTMX (`hx-get/post/put/delete`, `hx-swap`, `hx-trigger`, `hx-swap-oob`)
- **Drag-and-drop:** SortableJS — única concesión a JS de terceros; no hay reemplazo razonable en HTMX puro para arrastrar y soltar
- **Datos:** SQLite vía SQLModel (motor simple, un archivo, sin servicio aparte que levantar — coherente con "montable en un comando"; SQLModel da modelos tipados reutilizables como esquema Pydantic de las respuestas)
- **Estilos:** CSS propio, sin build step (nada de Tailwind/PostCSS) — refuerza el punto del proyecto: herramientas mínimas para el problema
- **Montaje:** `docker-compose.yml`, volumen para persistir el archivo SQLite

## Estructura de carpetas

```
app-htmx-fastapi/
├── app/
│   ├── main.py                     # FastAPI app, monta rutas, estáticos y plantillas
│   ├── database.py                 # engine SQLModel, sesión, creación de tablas
│   ├── modelos.py                  # Tarea: id, titulo, descripcion, columna, orden, etiqueta, fecha_limite, creado_en
│   ├── rutas/
│   │   ├── tablero.py              # GET / -> página completa
│   │   └── tareas.py               # crear/editar/mover/eliminar/buscar (fragmentos HTMX)
│   ├── templates/
│   │   ├── base.html
│   │   ├── tablero.html            # layout de 3 columnas
│   │   └── fragmentos/
│   │       ├── tarjeta.html        # una tarea (vista)
│   │       ├── formulario_tarea.html  # tarjeta en modo edición/creación
│   │       └── columna.html        # columna completa (para búsqueda/filtro)
│   └── static/
│       ├── estilos.css
│       └── vendor/                 # htmx.min.js, sortable.min.js (vendorizados, sin CDN)
├── tests/
│   └── test_tareas.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Endpoints

```
GET    /                        -> tablero completo (server-rendered)
GET    /tareas?buscar=&etiqueta= -> columnas filtradas (fragmento, para búsqueda en vivo)
POST   /tareas                  -> crea tarea, devuelve la tarjeta insertada + oob del contador de su columna
GET    /tareas/{id}             -> tarjeta individual (vista); usado por "Cancelar" al salir de edición sin guardar
GET    /tareas/{id}/editar      -> formulario inline (reemplaza la tarjeta)
PUT    /tareas/{id}             -> guarda edición, devuelve la tarjeta actualizada
DELETE /tareas/{id}             -> elimina, respuesta vacía (el nodo desaparece vía hx-swap) + oob del contador
PUT    /tareas/{id}/mover       -> cambia columna y/o posición; devuelve columna origen y destino actualizadas
```

## Patrones de interacción (el punto del proyecto)

- **Edición inline:** cada tarjeta es su propia unidad HTMX. `hx-get` carga el formulario en el lugar de la tarjeta; `hx-put` guarda y la reemplaza por la vista de nuevo. Nunca hay un modal ni un router de cliente.
- **Arrastrar y soltar:** SortableJS solo detecta el gesto y dispara un callback; ese callback hace un `hx-post` a `/tareas/{id}/mover` con columna y posición nuevas. HTMX intercambia las columnas origen/destino con lo que responde el servidor — el cliente nunca calcula ni asume el orden final.
- **Búsqueda en vivo:** input con `hx-trigger="keyup changed delay:300ms"` apuntando a `/tareas`, sin JS de filtrado en cliente.
- **Contadores y vencidas:** se actualizan con `hx-swap-oob` en la respuesta de crear/mover/eliminar, para no tener que re-renderizar la columna completa por un número.

## Criterios de aceptación

- [ ] `docker compose up` levanta la app en `localhost:8000` con datos persistidos en un volumen SQLite.
- [ ] Crear, editar inline, eliminar y mover tareas funciona sin recarga de página completa (verificable en la pestaña Network).
- [ ] El orden tras arrastrar y soltar sobrevive un refresh del navegador (el servidor lo persistió).
- [ ] La búsqueda en vivo filtra por texto y etiqueta con debounce, sin parpadeos.
- [ ] Contadores por columna y marca de vencidas correctos tras cada acción.
- [ ] Sin JS de aplicación custom más allá del callback de SortableJS: cero framework SPA, cero build step.
- [ ] Tests con `pytest` + `TestClient` cubren crear, editar, mover y eliminar.
- [ ] README con GIF mostrando drag-and-drop y edición inline.

## Orden de implementación (con commits sugeridos)

1. `chore: estructura base FastAPI + SQLModel + docker-compose`
2. `feat(modelo): modelo Tarea y datos semilla`
3. `feat(tablero): pagina principal con 3 columnas server-rendered`
4. `feat(tareas): crear tarea y fragmento de tarjeta`
5. `feat(tareas): editar inline y eliminar`
6. `feat(tareas): mover entre columnas y reordenar con SortableJS`
7. `feat(tablero): contadores y marca de vencidas via hx-swap-oob`
8. `feat(busqueda): filtro en vivo por texto y etiqueta`
9. `test: cobertura de endpoints con TestClient`
10. `chore: Dockerfile, docker-compose y README con GIF`

## Notas para Claude

- Si una interacción se puede resolver con un fragmento HTML y `hx-swap-oob`, no metas JS custom para lograrlo — ese es el criterio que este proyecto demuestra.
- SortableJS es la única librería de frontend permitida; no agregues otra sin repensar si de verdad hace falta.
- El servidor decide siempre el estado final (orden, columna); el cliente solo dispara la acción y reconcilia con la respuesta.
- Actualiza la bitácora de este proyecto en `PORTAFOLIO.md` (carpeta padre) al cerrar cada bloque.
