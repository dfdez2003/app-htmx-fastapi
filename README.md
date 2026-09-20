# App con HTMX + FastAPI

App con reactividad ligera usando HTMX y FastAPI, sin JS pesado en el frontend — demuestra criterio al elegir herramientas simples para el problema.

## Estado
Funcionando: tablero kanban con categorías, cola de trabajo, checklist y arrastrar
y soltar. El alcance completo, los criterios de aceptación y la estructura de
carpetas están en [`SPEC.md`](./SPEC.md); el plan con hitos, en [`PLAN.md`](./PLAN.md).

## Stack
Python 3.11+, FastAPI, HTMX, Jinja2, SortableJS. La fuente de verdad persistente
es `datos/tablero.json` (versionado en el repo, así clonar = tener los datos);
SQLModel sobre SQLite se usa solo como motor de consultas y se reconstruye al
arrancar.

## Instalar en una máquina nueva

Requisito único: **Docker** con el plugin `docker compose` (`docker compose version`
debe responder). No hace falta instalar Python ni nada más en el host — todo corre
dentro del contenedor.

```bash
git clone https://github.com/dfdez2003/app-htmx-fastapi.git
cd app-htmx-fastapi
./agenda build
```

La app queda en <http://localhost:8100>.

## Cómo correr

El primer arranque —y cada vez que cambien el `Dockerfile`, el `pyproject.toml` o
el código— necesita `build`:

```bash
./agenda build
```

Después, para levantarla rápido en segundo plano:

```bash
./agenda run
```

Otros comandos: `./agenda stop`, `./agenda status` y `./agenda log`. Los cambios
en `datos/` no requieren reconstruir.

## El comando `agenda` desde cualquier carpeta

Ejecuta una vez, dentro del repo:

```bash
./agenda install
```

Eso crea un enlace en `~/.local/bin/agenda`. A partir de ahí puedes escribir
`agenda run`, `agenda stop`, etc. **desde cualquier directorio**, sin `./` y sin
entrar al repo.

Si tras instalarlo la terminal responde `agenda: command not found`, es que
`~/.local/bin` no está en tu `PATH`. Compruébalo con `echo $PATH` y, si falta,
añádelo a tu `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Luego abre una terminal nueva (o `source ~/.bashrc`).

## Parte del portafolio
Este repo es la pieza 6 del portafolio general. Contexto y bitácora: `PORTAFOLIO.md` en la carpeta padre (`~/portafolio/`).
