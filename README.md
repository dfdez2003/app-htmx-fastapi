# App con HTMX + FastAPI

App con reactividad ligera usando HTMX y FastAPI, sin JS pesado en el frontend — demuestra criterio al elegir herramientas simples para el problema.

## Estado
Funcionando: tablero kanban con categorías, cola de trabajo, checklist y arrastrar
y soltar. El alcance completo, los criterios de aceptación y la estructura de
carpetas están en [`SPEC.md`](./SPEC.md); el plan con hitos, en [`PLAN.md`](./PLAN.md).

## Stack
Python 3.11+, FastAPI, HTMX, Jinja2, SortableJS, MongoDB Atlas. La fuente de
verdad persistente es un documento en Atlas; `datos/tablero.json` quedó como
caché local (ya no versionada) para poder arrancar sin internet. SQLModel sobre
SQLite se usa solo como motor de consultas y se reconstruye al arrancar.

## Instalar en una máquina nueva

Requisito único: **Docker** con el plugin `docker compose` (`docker compose version`
debe responder). No hace falta instalar Python ni nada más en el host — todo corre
dentro del contenedor.

```bash
git clone https://github.com/dfdez2003/app-htmx-fastapi.git
cd app-htmx-fastapi
cp .env.example .env     # y pon dentro tu cadena de conexión de Atlas
./agenda build
```

La app queda en <http://localhost:8100>, ya con tus tareas: las trae de Atlas, no
del repo. Copiar el `.env` es el único paso manual, una vez por máquina — es lo
único que no puede viajar en el repo.

Sin `.env` la app también arranca, pero guardando solo en local (ver la sección
siguiente).

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

## Persistencia: MongoDB Atlas

Las tareas viven en un cluster de Atlas (la capa gratis M0 sobra: el tablero
completo son ~15 KB). Así, mover una tarjeta en una laptop se ve en la otra sin
hacer commit ni pull; al repo solo se le sube código.

Para montarlo: crea un cluster gratis en Atlas, saca la cadena de conexión de
*Connect → Drivers* y ponla en `.env` como `MONGODB_URI`. En *Network Access*
tendrás que permitir tu IP; si trabajas desde varias redes, lo práctico es
`0.0.0.0/0` con una contraseña larga, porque las IPs domésticas cambian.

Cómo se comporta:

- **Todo el tablero es un solo documento** (`agenda.tablero`, `_id: "principal"`),
  así que cada escritura es atómica: nunca se ve un estado a medias.
- **La subida va en segundo plano**, agrupando ráfagas. Arrastrar una tarjeta no
  espera al viaje de red.
- **Se consulta si hay cambios remotos al abrir `/`, `/checklist` o
  `/configuracion`**, no en cada interacción. Al llegar a la otra laptop, recarga
  la página y tendrás lo último.
- **Sin internet la app sigue funcionando** con la caché de `datos/`, y avisa por
  consola. Sin `MONGODB_URI` se comporta como antes de tener Atlas: la caché hace
  de fuente de verdad.

### Si las dos laptops escriben lo mismo

El documento lleva un contador `version` y solo se pisa si nadie lo cambió desde
que lo leímos. Git avisaba de estos choques con un conflicto de merge; Atlas no,
de ahí el contador.

Si dejas la pestaña abierta en una laptop, trabajas en la otra y luego haces clic
en la primera, esa escritura se **rechaza** en vez de borrar lo de la otra: el
estado rechazado queda en `datos/conflicto-<fecha>.json` y en consola aparece el
aviso. Recarga la página para quedarte con lo bueno, y si perdiste algo, está en
ese archivo.

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
