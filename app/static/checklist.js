// Vista "por categoría" del checklist: arrastrar una tarjeta a otra columna
// reasigna su categoría. El estado y el orden no se tocan al arrastrar; el
// servidor re-renderiza la columna destino (y la de origen) ya ordenada por
// estado, así que la tarjeta "salta" a su grupo de estado al soltar.

function recategorizar(evt) {
  var tareaId = evt.item.dataset.id;
  var destino = evt.to.dataset.categoria; // id numérico o "sin"

  htmx.ajax("PUT", "/tareas/" + tareaId + "/categoria", {
    target: "#col-categoria-" + destino,
    swap: "outerHTML",
    values: { categoria_valor: destino },
  });
}

function inicializarCategorias() {
  document.querySelectorAll(".lista-categoria").forEach(function (lista) {
    if (!Sortable.get(lista)) {
      new Sortable(lista, {
        group: "checklist-categorias",
        // Solo las tarjetas se arrastran (no el "Sin tareas." placeholder).
        draggable: ".item-checklist",
        animation: 150,
        forceFallback: true,
        fallbackTolerance: 5,
        ghostClass: "sortable-ghost",
        chosenClass: "sortable-chosen",
        onStart: function () {
          document.body.classList.add("arrastrando");
        },
        onEnd: function (evt) {
          document.body.classList.remove("arrastrando");
          recategorizar(evt);
        },
      });
    }
  });
}

// Cada swap (toggle de modo, giro, búsqueda, o re-render de una columna tras
// mover/crear/borrar) reemplaza nodos con Sortable enganchado: hay que
// reengancharlos, igual que en el tablero.
document.body.addEventListener("htmx:afterSwap", inicializarCategorias);
document.body.addEventListener("htmx:oobAfterSwap", inicializarCategorias);
inicializarCategorias();

// Formulario de creación por columna (mismas funciones que el tablero, pero
// tablero.js no se carga en esta página, así que viven aquí también).
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
