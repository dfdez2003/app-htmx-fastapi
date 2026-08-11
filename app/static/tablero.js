// Arrastrar y soltar entre columnas del tablero.
// SortableJS solo detecta el gesto; el servidor decide el orden final
// (ver "Patrones de interacción" en SPEC.md).

function moverTarea(evt) {
  var tareaId = evt.item.dataset.id;
  var columnaDestino = evt.to.dataset.columna;
  var posicion = evt.newIndex;

  htmx.ajax("PUT", "/tareas/" + tareaId + "/mover", {
    target: "#" + evt.to.id,
    swap: "outerHTML",
    values: {
      columna_destino: columnaDestino,
      posicion: posicion,
    },
  });
}

function inicializarListas() {
  document.querySelectorAll(".lista").forEach(function (lista) {
    if (!Sortable.get(lista)) {
      new Sortable(lista, {
        group: "tablero",
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
          moverTarea(evt);
        },
      });
    }
  });
}

// El swap de outerHTML sustituye el nodo .lista completo (incluida la
// instancia de Sortable que tuviera enganchada), así que hay que
// reenganchar tras cada intercambio, incluidos los oob de la columna origen.
document.body.addEventListener("htmx:afterSwap", inicializarListas);
document.body.addEventListener("htmx:oobAfterSwap", inicializarListas);
inicializarListas();

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
