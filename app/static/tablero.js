// Arrastrar y soltar entre columnas del tablero.
// SortableJS solo detecta el gesto; el servidor decide el orden final
// (ver "Patrones de interacción" en SPEC.md).

function valorFiltro(id) {
  var el = document.getElementById(id);
  return el ? el.value : "";
}

function moverTarea(evt) {
  var tareaId = evt.item.dataset.id;
  var columnaDestino = evt.to.dataset.columna;
  // Ancla: la tarjeta que quedó justo antes de la soltada. El servidor
  // reinserta después de ella, así el drop cae donde se ve incluso con un
  // filtro activo (donde el índice numérico no corresponde a la lista real).
  var anterior = evt.item.previousElementSibling;
  var antesId = anterior ? anterior.dataset.id : "";

  htmx.ajax("PUT", "/tareas/" + tareaId + "/mover", {
    target: "#" + evt.to.id,
    swap: "outerHTML",
    // Se reenvía el filtro activo para que la columna re-pintada lo conserve.
    values: {
      columna_destino: columnaDestino,
      antes_id: antesId,
      buscar: valorFiltro("buscador-texto"),
      etiqueta: valorFiltro("buscador-etiqueta"),
      categoria: valorFiltro("buscador-categoria"),
    },
  });
}

function inicializarListas() {
  document.querySelectorAll(".lista").forEach(function (lista) {
    if (!Sortable.get(lista)) {
      new Sortable(lista, {
        // Al arrastrar hacia el panel de la cola, se CLONA (la tarjeta se
        // queda en su columna: la cola es una numeración, no un movimiento).
        // Entre columnas del tablero es un move normal.
        group: {
          name: "tablero",
          pull: function (to) {
            return to.el.id === "cola-lista" ? "clone" : true;
          },
          put: ["tablero"],
        },
        // Solo las tarjetas se arrastran. Clave: al editar, el formulario
        // reemplaza a la tarjeta DENTRO de la lista; sin esto, forceFallback
        // secuestraba el clic de sus campos (no se podía abrir el <select>
        // de categoría). El formulario no es .tarjeta, así que queda libre.
        draggable: ".tarjeta",
        animation: 150,
        forceFallback: true,
        // Sin tolerancia, forceFallback arranca el drag con el primer
        // pixel de movimiento del mouse: cualquier temblor al hacer clic
        // se sentía como un reordenamiento accidental, sobre todo
        // reordenando dentro de la misma columna (mover distancias
        // cortas). Unos px de margen antes de considerarlo un drag real
        // lo vuelve mucho más predecible sin notarse como demora.
        fallbackTolerance: 5,
        ghostClass: "sortable-ghost",
        chosenClass: "sortable-chosen",
        // El hover de .tarjeta (sombra + levantarse 1px) compite con el
        // propio movimiento del drag si el cursor pasa por encima de
        // tarjetas vecinas mientras arrastra — se apaga durante el drag.
        onStart: function () {
          document.body.classList.add("arrastrando");
        },
        onEnd: function (evt) {
          document.body.classList.remove("arrastrando");
          // Soltada en el panel de la cola: no es un cambio de columna, lo
          // maneja el Sortable de la cola (onAdd). Aquí no hacemos nada.
          if (evt.to.id === "cola-lista") return;
          moverTarea(evt);
        },
      });
    }
  });
}

// ---------- Cola de trabajo ----------
// Lista ordenada de ids que hay ahora mismo en el panel (deduplicada: al
// arrastrar una tarjeta ya numerada, su clon aparecería dos veces).
function idsDeCola() {
  var ids = [];
  document.querySelectorAll("#cola-lista [data-id]").forEach(function (el) {
    var id = el.dataset.id;
    if (id && ids.indexOf(id) < 0) ids.push(id);
  });
  return ids;
}

// Manda el orden completo al servidor. Él renumera y responde con
// actualizaciones oob (la lista del panel y los números de las tarjetas).
function enviarOrdenCola() {
  htmx.ajax("PUT", "/cola", {
    target: "#cola-lista",
    swap: "none",
    values: { ids: idsDeCola().join(",") },
  });
}

function inicializarCola() {
  var lista = document.getElementById("cola-lista");
  if (lista && !Sortable.get(lista)) {
    new Sortable(lista, {
      // Acepta tarjetas del tablero y reordena internamente; no deja sacar
      // ítems fuera (quitar es con la ✕).
      group: { name: "cola", pull: false, put: ["tablero", "cola"] },
      animation: 150,
      forceFallback: true,
      fallbackTolerance: 5,
      ghostClass: "sortable-ghost",
      onAdd: enviarOrdenCola, // llegó una tarjeta del tablero
      onUpdate: enviarOrdenCola, // se reordenó dentro del panel
    });
  }
}

// El swap de outerHTML sustituye el nodo .lista completo (incluida la
// instancia de Sortable que tuviera enganchada), así que hay que
// reenganchar tras cada intercambio, incluidos los oob de la columna origen
// y la lista de la cola (que se re-renderiza vía oob).
function reengancharSortables() {
  inicializarListas();
  inicializarCola();
}
document.body.addEventListener("htmx:afterSwap", reengancharSortables);
document.body.addEventListener("htmx:oobAfterSwap", reengancharSortables);
reengancharSortables();

// El panel arranca a la altura de las tarjetas (no topa arriba) y baja al
// fondo. Como la cabecera de la página no es fija, se recalcula el `top` en
// cada scroll: al inicio queda al nivel de las columnas y, al bajar, se clampa
// justo debajo de la barra superior fija.
function ajustarTopCola() {
  var panel = document.getElementById("cola-panel");
  if (!panel) return;
  var barra = document.querySelector(".barra");
  var columnas = document.getElementById("tablero-columnas");
  var minTop = barra ? barra.getBoundingClientRect().bottom : 0;
  var colsTop = columnas ? columnas.getBoundingClientRect().top : minTop;
  panel.style.top = Math.max(minTop, colsTop) + "px";
}
window.addEventListener("scroll", ajustarTopCola, { passive: true });
window.addEventListener("resize", ajustarTopCola);
ajustarTopCola();

// Abrir/cerrar el panel de la cola; se recuerda en cookie para que el
// servidor lo pinte igual al recargar (mismo criterio que el tema). Al abrir,
// `body.cola-abierta` empuja el contenido para que el panel no tape nada; la
// pestaña lateral se mueve junto con el panel para quedar siempre a la vista.
function fijarCola(abierta) {
  var panel = document.getElementById("cola-panel");
  var pestana = document.getElementById("cola-toggle");
  if (panel) panel.classList.toggle("abierta", abierta);
  if (pestana) pestana.classList.toggle("abierta", abierta);
  document.body.classList.toggle("cola-abierta", abierta);
  document.cookie = "cola_abierta=" + (abierta ? "1" : "0") + "; path=/; max-age=" + 60 * 60 * 24 * 365;
  if (abierta) ajustarTopCola();
}

document.body.addEventListener("click", function (evt) {
  if (evt.target.closest("#cola-toggle")) {
    var panel = document.getElementById("cola-panel");
    fijarCola(panel ? !panel.classList.contains("abierta") : true);
    return;
  }
  if (evt.target.closest("#cola-cerrar")) {
    fijarCola(false);
    return;
  }
  // Clic en la zona vacía del panel (la lista, fuera de una tarjeta): cierra.
  if (evt.target.closest("#cola-lista") && !evt.target.closest(".cola-item")) {
    fijarCola(false);
  }
});

// Botón "+ Nueva tarea" / "+" de cabecera de columna: revela el formulario
// de creación que ya está montado en el DOM (oculto), sin pedir nada al
// servidor. cerrarCreador() se llama también tras un POST /tareas exitoso.
function abrirCreador(clave) {
  var wrap = document.getElementById("creador-" + clave);
  if (!wrap) return;
  wrap.querySelector(".disparador").style.display = "none";
  var form = wrap.querySelector("form");
  form.style.display = "flex";
  form.querySelector('input[name="titulo"]').focus();
}

function cerrarCreador(form) {
  var wrap = form.closest(".formulario-crear");
  if (!wrap) return;
  form.style.display = "none";
  wrap.querySelector(".disparador").style.display = "flex";
}

document.body.addEventListener("click", function (evt) {
  var boton = evt.target.closest("[data-abre-creador]");
  if (boton) abrirCreador(boton.dataset.abreCreador);
});
