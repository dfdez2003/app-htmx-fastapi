# SPEC — App con HTMX + FastAPI

> Pieza 6 del plan. Demuestra criterio al elegir herramientas simples: reactividad ligera sin arrastrar un framework SPA.
> Contexto general y bitácora: ver `PORTAFOLIO.md` en la carpeta padre (`~/portafolio/`).

---

## Objetivo

Un tablero kanban de tareas (crear, editar inline, mover entre columnas, reordenar, buscar) donde toda la interactividad se resuelve con HTMX pidiendo fragmentos HTML al servidor — cero SPA, cero build step, cero estado de UI duplicado en el cliente. El servidor es siempre la fuente de verdad.

## Alcance

**Dentro:**
- Un tablero por categorías (swimlanes): cada categoría es una fila, con las tres columnas fijas al lado — Por hacer / En progreso / Hecho
- Categorías gestionables por el usuario (crear, renombrar, reordenar, borrar) desde un panel de configuración aparte del tablero; una tarea sin categoría cae en la fila fija "Sin categoría"
- Prioridad de tarea (alta/media/baja), solo visual — no reordena nada automáticamente, el orden sigue siendo 100% manual (drag-and-drop)
- CRUD de tareas: crear, editar inline (título, descripción, etiqueta, fecha límite, categoría, prioridad), eliminar
- Mover tareas entre categoría×columna y reordenar dentro de una celda (drag-and-drop), persistido en servidor
- Vista alterna "checklist": misma información aplanada en una sola lista por categoría, con un ícono de estado cíclico (☐ por hacer → ◐ en progreso → ✓ hecho) en vez de columnas espaciales
- Búsqueda/filtro en vivo por texto, etiqueta y categoría, sin recargar página, funcional en ambas vistas
- Contador de tareas por columna y marca visual de tareas vencidas, actualizados tras cada acción
- Persistencia en SQLite

**Fuera:**
- Autenticación, multi-usuario o colaboración en tiempo real entre varios clientes conectados
- Múltiples tableros
- Adjuntos, comentarios, subtareas
- Reordenamiento automático por prioridad (decisión explícita: solo indicador visual)

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
│   ├── modelos.py                  # Tarea, Categoria, enums Columna/Prioridad
│   ├── rutas/
│   │   ├── tablero.py              # GET / -> tablero por categorías; GET /checklist -> vista lista
│   │   ├── tareas.py               # crear/editar/mover/ciclar-estado/eliminar/buscar (fragmentos HTMX)
│   │   └── categorias.py           # GET /configuracion + CRUD de categorías
│   ├── templates/
│   │   ├── base.html
│   │   ├── tablero.html            # filas por categoría x 3 columnas (swimlanes)
│   │   ├── checklist.html          # vista lista aplanada por categoría
│   │   ├── configuracion.html      # gestión de categorías (panel escondido)
│   │   └── fragmentos/
│   │       ├── tarjeta.html        # una tarea (vista, tablero)
│   │       ├── fila_checklist.html # una tarea (vista, checklist)
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
GET    /                                  -> tablero por categorías (swimlanes, server-rendered)
GET    /checklist                         -> vista checklist (lista aplanada por categoría)
GET    /tareas?buscar=&etiqueta=&categoria= -> celdas/filas filtradas (fragmento, para búsqueda en vivo; sirve ambas vistas)
POST   /tareas                            -> crea tarea, devuelve la tarjeta insertada + oob del contador de su columna
GET    /tareas/{id}                       -> tarjeta individual (vista); usado por "Cancelar" al salir de edición sin guardar
GET    /tareas/{id}/editar                -> formulario inline (reemplaza la tarjeta; incluye selects de categoría/prioridad)
PUT    /tareas/{id}                       -> guarda edición, devuelve la tarjeta actualizada
DELETE /tareas/{id}                       -> elimina, respuesta vacía (el nodo desaparece vía hx-swap) + oob del contador
PUT    /tareas/{id}/mover                 -> cambia categoría, columna y/o posición; devuelve celda(s) origen y destino actualizadas
PUT    /tareas/{id}/estado                -> cicla el estado (por_hacer→en_progreso→hecho→por_hacer); usado por el ícono de la vista checklist
GET    /configuracion                     -> panel de gestión de categorías (página aparte, enlazada con un ícono discreto)
POST   /categorias                        -> crea categoría
PUT    /categorias/{id}                   -> renombra categoría
DELETE /categorias/{id}                   -> borra categoría; sus tareas quedan como "Sin categoría"
PUT    /categorias/{id}/mover             -> reordena (intercambia con la vecina, botones ▲▼)
```

## Patrones de interacción (el punto del proyecto)

- **Edición inline:** cada tarjeta es su propia unidad HTMX. `hx-get` carga el formulario en el lugar de la tarjeta; `hx-put` guarda y la reemplaza por la vista de nuevo. Nunca hay un modal ni un router de cliente.
- **Arrastrar y soltar (swimlanes):** SortableJS solo detecta el gesto y dispara un callback; ese callback hace un `hx-post` a `/tareas/{id}/mover` con categoría, columna y posición nuevas. Todas las celdas (categoría × columna) comparten `group: "tablero"`, así que un solo arrastre puede cambiar categoría y estado a la vez. HTMX intercambia la(s) celda(s) origen/destino con lo que responde el servidor — el cliente nunca calcula ni asume el orden final.
- **Prioridad:** puramente visual (indicador de color en la tarjeta); nunca reordena nada por sí sola, para no pelearse con el orden manual de drag-and-drop.
- **Vista checklist:** mismos datos que el tablero, aplanados en una lista por categoría; el ícono de estado (`PUT /tareas/{id}/estado`) reemplaza el drag-and-drop para cambiar de columna con un clic — más rápido para marcar tareas sin abrir el tablero completo.
- **Panel de categorías escondido:** vive en `/configuracion`, fuera del flujo principal — el tablero se mantiene limpio; se llega ahí por un ícono discreto, no por un modal.
- **Búsqueda en vivo:** input con `hx-trigger="keyup changed delay:300ms"` apuntando a `/tareas`, sin JS de filtrado en cliente; funciona igual en tablero y checklist.
- **Contadores y vencidas:** se actualizan con `hx-swap-oob` en la respuesta de crear/mover/eliminar, para no tener que re-renderizar la columna completa por un número.

## Criterios de aceptación

- [ ] `docker compose up` levanta la app en `localhost:8000` con datos persistidos en un volumen SQLite.
- [ ] Crear, editar inline, eliminar y mover tareas funciona sin recarga de página completa (verificable en la pestaña Network).
- [ ] El orden tras arrastrar y soltar sobrevive un refresh del navegador (el servidor lo persistió).
- [ ] La búsqueda en vivo filtra por texto, etiqueta y categoría con debounce, sin parpadeos, en ambas vistas.
- [ ] Contadores por columna y marca de vencidas correctos tras cada acción.
- [ ] Categorías gestionables desde `/configuracion` (crear/renombrar/reordenar/borrar), sin tocar código.
- [ ] El tablero permite arrastrar una tarea entre categoría×columna en un solo gesto.
- [ ] La vista checklist refleja el mismo estado que el tablero y permite ciclar por hacer→en progreso→hecho con un clic.
- [ ] Sin JS de aplicación custom más allá del callback de SortableJS: cero framework SPA, cero build step.
- [ ] Tests con `pytest` + `TestClient` cubren crear, editar, mover, eliminar, categorías y ciclo de estado.
- [ ] README con GIF mostrando drag-and-drop, edición inline, categorías y checklist.

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
10. `feat(categorias): modelo Categoria y panel de configuracion`
11. `feat(tablero): swimlanes por categoria y prioridad visual`
12. `feat(checklist): vista lista con estado ciclico`
13. `feat(busqueda): extender filtro a categoria en ambas vistas`
14. `chore: Dockerfile, docker-compose y README con GIF`

## Notas para Claude

- Si una interacción se puede resolver con un fragmento HTML y `hx-swap-oob`, no metas JS custom para lograrlo — ese es el criterio que este proyecto demuestra.
- SortableJS es la única librería de frontend permitida; no agregues otra sin repensar si de verdad hace falta.
- El servidor decide siempre el estado final (orden, columna); el cliente solo dispara la acción y reconcilia con la respuesta.
- Actualiza la bitácora de este proyecto en `PORTAFOLIO.md` (carpeta padre) al cerrar cada bloque.
