// Colorea el <select> de categoría (creación/edición de tarea y filtro de
// búsqueda) con el color de la opción elegida, para que se distinga cuál
// es cuál también con el desplegable cerrado, no solo al abrirlo.

function colorearSelectCategoria(select) {
  var opcion = select.options[select.selectedIndex];
  var color = opcion ? opcion.dataset.color : null;
  select.style.setProperty("--categoria-color-select", color || "transparent");
}

function colorearTodosLosSelects() {
  document.querySelectorAll('select[name="categoria"]').forEach(colorearSelectCategoria);
}

document.body.addEventListener("change", function (evt) {
  if (evt.target.matches && evt.target.matches('select[name="categoria"]')) {
    colorearSelectCategoria(evt.target);
  }
});

// Los formularios se reemplazan enteros tras cada acción HTMX (crear,
// cancelar edición, etc.) — hay que volver a colorear los selects nuevos.
document.body.addEventListener("htmx:afterSwap", colorearTodosLosSelects);
document.body.addEventListener("htmx:oobAfterSwap", colorearTodosLosSelects);
colorearTodosLosSelects();
