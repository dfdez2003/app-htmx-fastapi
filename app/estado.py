"""Estado en memoria del proceso — no persiste en BD ni por sesión, vive
mientras corre el servidor. Por ahora solo guarda el último movimiento de
tarjeta (drag-and-drop) para poder deshacerlo con un clic; no hay usuarios
ni sesiones en esta app, así que un único valor global es suficiente."""

ultimo_movimiento: dict | None = None
