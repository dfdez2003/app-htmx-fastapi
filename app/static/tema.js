// Ciclo de tema de la barra superior: auto (según el sistema) -> claro ->
// medio -> oscuro -> auto... El script inline de base.html ya aplica el
// tema guardado antes de pintar; este archivo solo maneja el clic del
// botón y lo mantiene sincronizado tras cada swap de htmx.

var CICLO_TEMA = ["auto", "claro", "medio", "oscuro"];
var TITULOS_TEMA = {
  auto: "Tema: automático (según el sistema)",
  claro: "Tema: claro",
  medio: "Tema: medio (fondo oscuro, tarjetas claras)",
  oscuro: "Tema: oscuro",
};

function aplicarTema(tema) {
  if (tema === "auto") {
    document.documentElement.removeAttribute("data-tema");
  } else {
    document.documentElement.setAttribute("data-tema", tema);
  }
  var boton = document.getElementById("boton-tema");
  if (boton) boton.title = TITULOS_TEMA[tema];
}

function alternarTema() {
  var actual = localStorage.getItem("tema") || "auto";
  var siguiente = CICLO_TEMA[(CICLO_TEMA.indexOf(actual) + 1) % CICLO_TEMA.length];
  localStorage.setItem("tema", siguiente);
  aplicarTema(siguiente);
}

document.body.addEventListener("click", function (evt) {
  if (evt.target.closest && evt.target.closest("#boton-tema")) alternarTema();
});

aplicarTema(localStorage.getItem("tema") || "auto");
