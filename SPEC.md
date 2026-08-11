# SPEC — App con HTMX + FastAPI

> Pieza 6 del plan. Demuestra criterio al elegir herramientas simples: reactividad ligera sin arrastrar un framework SPA.
> Contexto general y bitácora: ver `PORTAFOLIO.md` en la carpeta padre (`~/portafolio/`).

---

## Objetivo

Un tablero kanban de tareas (crear, editar inline, mover entre columnas, reordenar, buscar) donde toda la interactividad se resuelve con HTMX pidiendo fragmentos HTML al servidor — cero SPA, cero build step, cero estado de UI duplicado en el cliente. El servidor es siempre la fuente de verdad.

## Alcance

**Dentro:**
- Un tablero de 3 columnas fijas — Por hacer / En progreso / Hecho — donde todas las categorías se mezclan libremente dentro de cada columna (no hay filas por categoría: la categoría es un color, no una posición)
- Categorías gestionables por el usuario (crear, renombrar, cambiar color, borrar) desde un panel de configuración aparte del tablero; cada tarjeta/ítem se tiñe con el color de su categoría, "Sin categoría" se ve sin tinte
- Prioridad de tarea (alta/media/baja), solo visual — no reordena nada automáticamente, el orden sigue siendo 100% manual (drag-and-drop)
- CRUD de tareas: crear, editar inline (título, descripción, etiqueta, fecha límite, categoría, prioridad), eliminar. La categoría se edita desde el formulario; la columna solo por arrastre
- Mover tareas entre columnas y reordenar dentro de una (drag-and-drop), persistido en servidor
- Vista alterna "checklist": misma información en una sola lista (sin agrupar por categoría), ordenada por estado, con un ícono de estado cíclico (☐ por hacer → ◐ en progreso → ✓ hecho) en vez de columnas espaciales
- Búsqueda/filtro en vivo por texto, etiqueta y categoría, sin recargar página, funcional en ambas vistas
- Contador de tareas por columna, resumen global (`N tareas · N hechas · N vencidas`) y marca visual de tareas vencidas, actualizados tras cada acción
- Deshacer el último movimiento de tarjeta (drag-and-drop) con un clic — un solo nivel, no es un historial completo
- Tema claro/medio/oscuro, ciclado con un botón y persistido en `localStorage`; sin elegir ninguno, sigue `prefers-color-scheme`
- Persistencia en SQLite

**Fuera:**
- Autenticación, multi-usuario o colaboración en tiempo real entre varios clientes conectados
- Múltiples tableros
- Adjuntos, comentarios, subtareas
- Reordenamiento automático por prioridad (decisión explícita: solo indicador visual)
- Categorías como filas/swimlanes del tablero (probado en el Hito 11, revertido en el Hito 14: dispersaba el flujo de una sola vista y no dejaba mezclar tipos de tarea en una columna)

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
│   ├── modelos.py                  # Tarea, Categoria (con color), enums Columna/Prioridad
│   ├── vistas.py                   # construir_columnas/construir_checklist/construir_resumen, compartido por tablero/checklist/búsqueda
│   ├── estado.py                   # último movimiento (drag-and-drop) para poder deshacerlo; en memoria, no en BD
│   ├── plantillas.py               # Jinja2Templates + filtro fecha_corta + combinar() (concatena piezas hx-swap-oob)
│   ├── rutas/
│   │   ├── tablero.py              # GET / -> 3 columnas; GET /checklist -> lista única
│   │   ├── tareas.py               # crear/editar/mover/deshacer/ciclar-estado/eliminar/buscar (fragmentos HTMX)
│   │   └── categorias.py           # GET /configuracion + CRUD de categorías (nombre + color)
│   ├── templates/
│   │   ├── base.html
│   │   ├── tablero.html            # 3 columnas fijas, categorías mezcladas y coloreadas
│   │   ├── checklist.html          # lista única, ordenada por estado
│   │   ├── configuracion.html      # gestión de categorías (panel escondido)
│   │   └── fragmentos/
│   │       ├── barra.html          # barra superior compartida: marca, cambio de vista, deshacer, tema, config
│   │       ├── tarjeta.html        # una tarea (vista, tablero) — cabecera teñida con categoria.color
│   │       ├── item_checklist.html # una tarea (vista, checklist)
│   │       ├── formulario_tarea.html  # tarjeta en modo edición/creación (incluye select de categoría)
│   │       ├── columnas.html       # las 3 columnas completas (para búsqueda/filtro)
│   │       ├── resumen.html        # "N tareas · N hechas · N vencidas", también como oob
│   │       └── boton_deshacer.html # estado (activo/deshabilitado) del botón deshacer, también como oob
│   └── static/
│       ├── estilos.css
│       ├── tema.js                 # ciclo de tema (auto/claro/medio/oscuro), persistido en localStorage
│       ├── tablero.js              # SortableJS + mostrar/ocultar el formulario de nueva tarea
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
GET    /                                  -> tablero de 3 columnas (server-rendered, categorías mezcladas)
GET    /checklist                         -> vista checklist (lista única, ordenada por estado)
GET    /tareas?buscar=&etiqueta=&categoria=&vista= -> columnas o lista filtradas (fragmento, para búsqueda en vivo; vista=tablero|checklist decide el fragmento)
POST   /tareas                            -> crea tarea, devuelve la tarjeta insertada + oob del contador de su columna
GET    /tareas/{id}                       -> tarjeta individual (vista); usado por "Cancelar" al salir de edición sin guardar
GET    /tareas/{id}/editar                -> formulario inline (reemplaza la tarjeta; incluye selects de categoría/prioridad)
PUT    /tareas/{id}                       -> guarda edición (incluida categoría), devuelve la tarjeta actualizada
DELETE /tareas/{id}                       -> elimina, respuesta vacía (el nodo desaparece vía hx-swap) + oob del contador
PUT    /tareas/{id}/mover                 -> cambia columna y/o posición; devuelve columna(s) origen y destino actualizadas + oob del botón deshacer
POST   /tareas/deshacer                   -> revierte el último /mover (un solo nivel); no-op si no hay nada que deshacer
PUT    /tareas/{id}/estado                -> cicla el estado (por_hacer→en_progreso→hecho→por_hacer); usado por el ícono de la vista checklist
GET    /configuracion                     -> panel de gestión de categorías (página aparte, enlazada con un ícono discreto)
POST   /categorias                        -> crea categoría (color asignado por turno de una paleta fija)
PUT    /categorias/{id}                   -> actualiza nombre y color
DELETE /categorias/{id}                   -> borra categoría; sus tareas quedan como "Sin categoría"
```

## Patrones de interacción (el punto del proyecto)

- **Edición inline:** cada tarjeta es su propia unidad HTMX. `hx-get` carga el formulario en el lugar de la tarjeta; `hx-put` guarda y la reemplaza por la vista de nuevo. Nunca hay un modal ni un router de cliente. Como la categoría ya no determina la posición de la tarjeta (Hito 14), se edita ahí mismo sin reubicar nada; la columna sigue siendo solo por arrastre porque un swap in-place no puede mover el nodo a otra lista.
- **Arrastrar y soltar (columnas):** SortableJS solo detecta el gesto y dispara un callback; ese callback hace un `hx-put` a `/tareas/{id}/mover` con columna y posición nuevas. Las 3 listas comparten `group: "tablero"`. HTMX intercambia la(s) columna(s) origen/destino con lo que responde el servidor — el cliente nunca calcula ni asume el orden final.
- **Color de categoría:** cada tarjeta/ítem se pinta con un tinte suave del color de su categoría vía `color-mix()` en CSS, leyendo una custom property (`--categoria-color`) puesta inline por la plantilla; sin categoría, la property no existe y el `var(..., fallback)` cae al fondo normal — sin lógica de color en Python.
- **Prioridad:** puramente visual (indicador de color en la tarjeta, distinto del color de categoría); nunca reordena nada por sí sola, para no pelearse con el orden manual de drag-and-drop.
- **Vista checklist:** mismos datos que el tablero, en una sola lista ordenada por estado (no agrupada por categoría — mismo criterio de "todo junto, diferenciado por color" que el tablero); el ícono de estado (`PUT /tareas/{id}/estado`) reemplaza el drag-and-drop para cambiar de columna con un clic.
- **Panel de categorías escondido:** vive en `/configuracion`, fuera del flujo principal — el tablero se mantiene limpio; se llega ahí por un ícono discreto, no por un modal. Lo único editable de una categoría es nombre y color — ya no tiene una posición visual que reordenar.
- **Búsqueda en vivo:** input con `hx-trigger="keyup changed delay:300ms"` apuntando a `/tareas`, sin JS de filtrado en cliente; funciona igual en tablero y checklist (el parámetro `vista` decide qué fragmento devuelve el mismo endpoint).
- **Contadores, resumen y vencidas:** se actualizan con `hx-swap-oob` en la respuesta de crear/editar/mover/eliminar/ciclar-estado (`app/plantillas.py:combinar()` concatena la respuesta principal con estas piezas oob), para no tener que re-renderizar la columna ni la cabecera completa por un número.
- **Deshacer:** `app/estado.py` guarda en memoria el snapshot (tarea, columna origen, posición) del último `/mover`, sobrescrito en cada drag — un solo nivel, no una pila. El botón de la barra lo consume con `POST /tareas/deshacer` y se deshabilita a sí mismo vía oob; si la tarea se borra antes de deshacer, el snapshot se invalida para no dar 404.
- **Tema:** un script inline en `base.html` aplica el tema guardado en `localStorage` antes del primer pintado (evita parpadeo); el botón de la barra cicla auto→claro→medio→oscuro escribiendo `data-tema` en `<html>`, que es lo único que lee `estilos.css` — el servidor no sabe ni le importa qué tema hay activo.

## Criterios de aceptación

- [ ] `docker compose up` levanta la app en `localhost:8000` con datos persistidos en un volumen SQLite.
- [ ] Crear, editar inline, eliminar y mover tareas funciona sin recarga de página completa (verificable en la pestaña Network).
- [ ] El orden tras arrastrar y soltar sobrevive un refresh del navegador (el servidor lo persistió).
- [ ] La búsqueda en vivo filtra por texto, etiqueta y categoría con debounce, sin parpadeos, en ambas vistas.
- [ ] Contadores por columna y marca de vencidas correctos tras cada acción.
- [ ] Categorías gestionables desde `/configuracion` (crear/renombrar/cambiar color/borrar), sin tocar código.
- [ ] El tablero mezcla todas las categorías dentro de cada columna, diferenciadas solo por color; editar la categoría de una tarea no la reubica.
- [ ] La vista checklist refleja el mismo estado que el tablero, en una sola lista, y permite ciclar por hacer→en progreso→hecho con un clic.
- [ ] Deshacer revierte el último movimiento de tarjeta (columna y/o posición); un segundo clic sin movimientos nuevos es un no-op seguro.
- [ ] El tema (claro/medio/oscuro) persiste entre recargas y no parpadea al cargar la página.
- [ ] Sin JS de aplicación que duplique lógica de servidor (cálculo de orden, estado, filtros): el JS propio se limita al callback de SortableJS y utilidades de UI pura (tema, mostrar/ocultar un formulario) — cero framework SPA, cero build step.
- [ ] Tests con `pytest` + `TestClient` cubren crear, editar, mover, deshacer, eliminar, categorías y ciclo de estado.
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
14. `refactor(tablero): categorias por color en vez de swimlanes, tablero y checklist planos`
15. `style(rediseno): tokens, temas y barra superior compartida` (+ commits siguientes por plantilla, guía en `entrega/`)
16. `chore: Dockerfile, docker-compose y README con GIF`

## Notas para Claude

- Si una interacción se puede resolver con un fragmento HTML y `hx-swap-oob`, no metas JS custom para lograrlo — ese es el criterio que este proyecto demuestra.
- SortableJS es la única librería de frontend permitida; no agregues otra sin repensar si de verdad hace falta.
- El servidor decide siempre el estado final (orden, columna); el cliente solo dispara la acción y reconcilia con la respuesta.
- Actualiza la bitácora de este proyecto en `PORTAFOLIO.md` (carpeta padre) al cerrar cada bloque.
