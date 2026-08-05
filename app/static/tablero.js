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
    values: { columna_destino: columnaDestino, posicion: posicion },
  });
}

function inicializarListas() {
  document.querySelectorAll(".lista").forEach(function (lista) {
    if (!Sortable.get(lista)) {
      new Sortable(lista, {
        group: "tablero",
        animation: 150,
        forceFallback: true,
        onEnd: moverTarea,
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
