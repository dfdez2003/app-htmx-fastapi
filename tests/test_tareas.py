from sqlmodel import Session, select

from app.modelos import Categoria, Tarea


def _crear(client, engine, titulo="Tarea", columna="por_hacer", etiqueta=""):
    """Crea una tarea vía el endpoint real y devuelve su id (leído de la BD,
    ya que la respuesta es el fragmento HTML de la tarjeta, no un JSON)."""
    client.post(
        "/tareas", data={"titulo": titulo, "columna": columna, "etiqueta": etiqueta}
    )
    with Session(engine) as session:
        tarea = session.exec(select(Tarea).where(Tarea.titulo == titulo)).one()
        return tarea.id


# --- crear ---------------------------------------------------------------


def test_crear_tarea(client, engine):
    resp = client.post(
        "/tareas", data={"titulo": "Nueva tarea", "columna": "por_hacer", "etiqueta": "qa"}
    )
    assert resp.status_code == 200
    assert "Nueva tarea" in resp.text
    assert 'id="contador-sin-por_hacer"' in resp.text  # oob del contador (sin categoría)

    with Session(engine) as session:
        tareas = session.exec(select(Tarea)).all()
    assert len(tareas) == 1
    assert tareas[0].titulo == "Nueva tarea"
    assert tareas[0].etiqueta == "qa"
    assert tareas[0].orden == 0


def test_crear_tarea_calcula_orden_al_final_de_su_columna(client, engine):
    _crear(client, engine, titulo="Primera")
    _crear(client, engine, titulo="Segunda")

    with Session(engine) as session:
        ordenes = [
            t.orden
            for t in session.exec(select(Tarea).order_by(Tarea.orden)).all()
        ]
    assert ordenes == [0, 1]


def test_crear_tarea_con_titulo_vacio_falla(client):
    resp = client.post("/tareas", data={"titulo": "   ", "columna": "por_hacer"})
    assert resp.status_code == 422


# --- editar ----------------------------------------------------------------


def test_formulario_editar_devuelve_form(client, engine):
    tarea_id = _crear(client, engine, titulo="Original")
    resp = client.get(f"/tareas/{tarea_id}/editar")
    assert resp.status_code == 200
    assert "Original" in resp.text
    assert f'hx-put="/tareas/{tarea_id}"' in resp.text


def test_editar_tarea(client, engine):
    tarea_id = _crear(client, engine, titulo="Original", etiqueta="vieja")

    resp = client.put(
        f"/tareas/{tarea_id}",
        data={
            "titulo": "Editada",
            "descripcion": "una descripcion",
            "etiqueta": "nueva",
            "fecha_limite": "",
        },
    )
    assert resp.status_code == 200
    assert "Editada" in resp.text

    with Session(engine) as session:
        tarea = session.get(Tarea, tarea_id)
    assert tarea.titulo == "Editada"
    assert tarea.descripcion == "una descripcion"
    assert tarea.etiqueta == "nueva"


def test_editar_tarea_con_titulo_vacio_falla(client, engine):
    tarea_id = _crear(client, engine)
    resp = client.put(
        f"/tareas/{tarea_id}",
        data={"titulo": "  ", "descripcion": "", "etiqueta": "", "fecha_limite": ""},
    )
    assert resp.status_code == 422


def test_editar_tarea_inexistente_da_404(client):
    resp = client.put(
        "/tareas/999",
        data={"titulo": "x", "descripcion": "", "etiqueta": "", "fecha_limite": ""},
    )
    assert resp.status_code == 404


def test_cancelar_edicion_devuelve_la_tarjeta_sin_guardar(client, engine):
    tarea_id = _crear(client, engine, titulo="Cancelable")
    resp = client.get(f"/tareas/{tarea_id}")
    assert resp.status_code == 200
    assert "Cancelable" in resp.text


def test_tarea_con_fecha_pasada_se_marca_vencida_salvo_en_hecho(client, engine):
    en_curso = _crear(client, engine, titulo="Vencida", columna="por_hacer")
    en_hecho = _crear(client, engine, titulo="Terminada", columna="hecho")

    for tarea_id in (en_curso, en_hecho):
        client.put(
            f"/tareas/{tarea_id}",
            data={
                "titulo": "x",
                "descripcion": "",
                "etiqueta": "",
                "fecha_limite": "2000-01-01",
            },
        )

    with Session(engine) as session:
        assert session.get(Tarea, en_curso).vencida is True
        assert session.get(Tarea, en_hecho).vencida is False


# --- eliminar ----------------------------------------------------------------


def test_eliminar_tarea(client, engine):
    tarea_id = _crear(client, engine, titulo="Borrame")

    resp = client.delete(f"/tareas/{tarea_id}")
    assert resp.status_code == 200
    assert 'id="contador-sin-por_hacer"' in resp.text

    with Session(engine) as session:
        assert session.get(Tarea, tarea_id) is None
    assert client.get(f"/tareas/{tarea_id}").status_code == 404


def test_eliminar_tarea_inexistente_da_404(client):
    assert client.delete("/tareas/999").status_code == 404


# --- mover / reordenar -------------------------------------------------------


def test_mover_tarea_entre_columnas_recalcula_orden_en_ambas(client, engine):
    id_a = _crear(client, engine, titulo="A", columna="por_hacer")
    id_b = _crear(client, engine, titulo="B", columna="por_hacer")
    id_c = _crear(client, engine, titulo="C", columna="en_progreso")

    resp = client.put(
        f"/tareas/{id_a}/mover", data={"columna_destino": "en_progreso", "posicion": 0}
    )
    assert resp.status_code == 200

    with Session(engine) as session:
        tarea_a = session.get(Tarea, id_a)
        tarea_b = session.get(Tarea, id_b)
        tarea_c = session.get(Tarea, id_c)

    # destino: A entra primero, C pasa a la posicion 1
    assert tarea_a.columna == "en_progreso"
    assert tarea_a.orden == 0
    assert tarea_c.orden == 1
    # origen: se recompacta, B pasa a ocupar el orden 0 que dejo A
    assert tarea_b.columna == "por_hacer"
    assert tarea_b.orden == 0


def test_reordenar_dentro_de_la_misma_columna(client, engine):
    id_a = _crear(client, engine, titulo="A", columna="por_hacer")
    id_b = _crear(client, engine, titulo="B", columna="por_hacer")
    id_c = _crear(client, engine, titulo="C", columna="por_hacer")

    client.put(f"/tareas/{id_c}/mover", data={"columna_destino": "por_hacer", "posicion": 0})

    with Session(engine) as session:
        ordenados = session.exec(
            select(Tarea).where(Tarea.columna == "por_hacer").order_by(Tarea.orden)
        ).all()
    assert [t.titulo for t in ordenados] == ["C", "A", "B"]
    assert [t.id for t in ordenados] == [id_c, id_a, id_b]


def test_mover_tarea_inexistente_da_404(client):
    resp = client.put("/tareas/999/mover", data={"columna_destino": "hecho", "posicion": 0})
    assert resp.status_code == 404


def test_mover_con_posicion_fuera_de_rango_se_clampa_sin_error(client, engine):
    id_a = _crear(client, engine, titulo="A", columna="por_hacer")
    resp = client.put(
        f"/tareas/{id_a}/mover", data={"columna_destino": "por_hacer", "posicion": 999}
    )
    assert resp.status_code == 200
    with Session(engine) as session:
        assert session.get(Tarea, id_a).orden == 0


# --- busqueda ----------------------------------------------------------------


def test_busqueda_por_texto(client, engine):
    _crear(client, engine, titulo="Comprar leche")
    _crear(client, engine, titulo="Escribir informe")

    resp = client.get("/tareas", params={"buscar": "leche"})
    assert resp.status_code == 200
    assert "Comprar leche" in resp.text
    assert "Escribir informe" not in resp.text


def test_busqueda_por_etiqueta(client, engine):
    _crear(client, engine, titulo="Tarea backend", etiqueta="backend")
    _crear(client, engine, titulo="Tarea frontend", etiqueta="frontend")

    resp = client.get("/tareas", params={"etiqueta": "backend"})
    assert "Tarea backend" in resp.text
    assert "Tarea frontend" not in resp.text


def test_busqueda_combinada_sin_coincidencia_no_devuelve_nada(client, engine):
    _crear(client, engine, titulo="Tarea backend", etiqueta="backend")

    resp = client.get("/tareas", params={"buscar": "Tarea", "etiqueta": "frontend"})
    assert "Tarea backend" not in resp.text


def test_busqueda_sin_filtros_devuelve_todas(client, engine):
    _crear(client, engine, titulo="Una", columna="por_hacer")
    _crear(client, engine, titulo="Otra", columna="en_progreso")

    resp = client.get("/tareas")
    assert "Una" in resp.text
    assert "Otra" in resp.text


def _crear_categoria(client, engine, nombre):
    client.post("/categorias", data={"nombre": nombre})
    with Session(engine) as session:
        categoria = session.exec(select(Categoria).where(Categoria.nombre == nombre)).one()
        return categoria.id


def test_busqueda_por_categoria(client, engine):
    escuela_id = _crear_categoria(client, engine, "Escuela")
    client.post(
        "/tareas", data={"titulo": "Tarea escuela", "columna": "por_hacer", "categoria": str(escuela_id)}
    )
    client.post("/tareas", data={"titulo": "Tarea sin categoria", "columna": "por_hacer"})

    resp = client.get("/tareas", params={"categoria": str(escuela_id)})
    assert "Tarea escuela" in resp.text
    assert "Tarea sin categoria" not in resp.text


def test_busqueda_por_categoria_token_sin(client, engine):
    escuela_id = _crear_categoria(client, engine, "Escuela")
    client.post(
        "/tareas", data={"titulo": "Tarea escuela", "columna": "por_hacer", "categoria": str(escuela_id)}
    )
    client.post("/tareas", data={"titulo": "Tarea suelta", "columna": "por_hacer"})

    resp = client.get("/tareas", params={"categoria": "sin"})
    assert "Tarea suelta" in resp.text
    assert "Tarea escuela" not in resp.text


def test_busqueda_combinada_texto_y_categoria(client, engine):
    escuela_id = _crear_categoria(client, engine, "Escuela")
    trabajo_id = _crear_categoria(client, engine, "Trabajo")
    client.post(
        "/tareas",
        data={"titulo": "Leer capitulo", "columna": "por_hacer", "categoria": str(escuela_id)},
    )
    client.post(
        "/tareas",
        data={"titulo": "Leer informe", "columna": "por_hacer", "categoria": str(trabajo_id)},
    )

    resp = client.get("/tareas", params={"buscar": "Leer", "categoria": str(escuela_id)})
    assert "Leer capitulo" in resp.text
    assert "Leer informe" not in resp.text


def test_busqueda_con_vista_checklist_devuelve_fragmento_de_lista(client, engine):
    _crear(client, engine, titulo="Una tarea")

    resp = client.get("/tareas", params={"vista": "checklist"})
    assert resp.status_code == 200
    assert "Una tarea" in resp.text
    assert "estado-icono" in resp.text
    assert "fila-columnas" not in resp.text
