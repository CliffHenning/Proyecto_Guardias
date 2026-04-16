import sys
import os
import sqlite3
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as app_module
from modules.db.db_manager import DBManager
from modules.db.models import Profesor, Horario, Ausencia, Presencia
from modules.guardias.motor import obtener_dia_semana_es


def crear_bd_temporal():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(db_path)
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "modules", "db", "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as schema_file:
        conn.executescript(schema_file.read())
    conn.commit()
    conn.close()

    return db_path


def test_ruta_index_devuelve_200(cliente):
    """La ruta raíz / debe responder con código HTTP 200."""
    respuesta = cliente.get("/")

    assert respuesta.status_code == 200


def test_ruta_index_muestra_botones_principales(cliente):
    """La portada debe mostrar los accesos a presencia y guardias."""
    respuesta = cliente.get("/")

    assert respuesta.status_code == 200
    assert b"Control de presencia" in respuesta.data
    assert b"Guardias" in respuesta.data


def test_ruta_presencia_devuelve_200(monkeypatch, cliente):
    """La ruta /presencia debe responder con 200 sin acceder a la base de datos real."""
    monkeypatch.setattr(app_module, "obtener_estado_actual", lambda *_args, **_kwargs: {})

    respuesta = cliente.get("/presencia")

    assert respuesta.status_code == 200


def test_ruta_presencia_muestra_botonera_dinamica_y_estados(cliente):
    """La vista de presencia debe mostrar profesorado y estados presente/ausente."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor_presente = db_manager.insert_profesor(Profesor(nombre="Ana García", rfid="R1", activo=1))
        db_manager.insert_profesor(Profesor(nombre="Luis Pérez", rfid="R2", activo=1))

        app_module.registrar_presencia(profesor_presente.id, db_path)

        respuesta = cliente.get("/presencia")
    finally:
        app_module.app.config["DB_PATH"] = "ies.db"
        os.remove(db_path)

    assert respuesta.status_code == 200
    assert b"Botonera din" in respuesta.data
    assert "Ana García".encode("utf-8") in respuesta.data
    assert "Luis Pérez".encode("utf-8") in respuesta.data
    assert b"Presente" in respuesta.data
    assert b"Ausente" in respuesta.data
    assert b"btn-success" in respuesta.data


def test_registrar_presencia_desde_boton_dinamico_actualiza_estado(cliente):
    """La botonera dinámica debe permitir registrar presencia manualmente."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor = db_manager.insert_profesor(Profesor(nombre="Profesor Botón", rfid="RB1", activo=1))

        respuesta = cliente.post("/presencia/registrar", data={"profesor_id": profesor.id}, follow_redirects=True)
    finally:
        app_module.app.config["DB_PATH"] = "ies.db"
        os.remove(db_path)

    assert respuesta.status_code == 200
    assert "Profesor Botón".encode("utf-8") in respuesta.data
    assert b"Registro de entrada exitoso" in respuesta.data
    assert b"Presente" in respuesta.data


def test_identificacion_correcta_registra_en_bd_y_marca_presente(monkeypatch, cliente):
    """La identificación correcta debe insertar presencia y reflejarse en la botonera y tabla."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor = db_manager.insert_profesor(Profesor(nombre="Profesor RFID", rfid="RF1", activo=1))
        monkeypatch.setattr(app_module, "identificar_profesor", lambda: profesor.id)

        respuesta = cliente.post("/presencia/registrar", follow_redirects=True)
        presencias = db_manager.get_presencias_hoy()
    finally:
        app_module.app.config["DB_PATH"] = "ies.db"
        os.remove(db_path)

    assert respuesta.status_code == 200
    assert len(presencias) == 1
    assert presencias[0].profesor_id == profesor.id
    assert presencias[0].tipo == "entrada"
    assert "Profesor RFID".encode("utf-8") in respuesta.data
    assert b"Registro de entrada exitoso" in respuesta.data
    assert b"Presente" in respuesta.data
    assert b"btn-success" in respuesta.data


def test_identificacion_fallida_muestra_error_y_no_inserta(cliente, monkeypatch):
    """Si no se identifica al profesor, no debe insertarse presencia ni cambiar el estado."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor = db_manager.insert_profesor(Profesor(nombre="Profesor Sin Identificar", rfid="RF2", activo=1))
        monkeypatch.setattr(app_module, "identificar_profesor", lambda: None)

        respuesta = cliente.post("/presencia/registrar", follow_redirects=True)
        presencias = db_manager.get_presencias_hoy()
        estado = app_module.obtener_estado_actual(db_path)
    finally:
        app_module.app.config["DB_PATH"] = "ies.db"
        os.remove(db_path)

    assert respuesta.status_code == 200
    assert b"Profesor no identificado" in respuesta.data
    assert len(presencias) == 0
    assert estado[profesor.id]["presente"] is False
    assert b"Ausente" in respuesta.data


def test_registro_de_salida_alterna_estado_y_guarda_segundo_evento(cliente):
    """Una segunda identificación del mismo profesor debe registrar salida y dejarlo ausente."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor = db_manager.insert_profesor(Profesor(nombre="Profesor Alternancia", rfid="RF3", activo=1))

        cliente.post("/presencia/registrar", data={"profesor_id": profesor.id}, follow_redirects=True)
        respuesta = cliente.post("/presencia/registrar", data={"profesor_id": profesor.id}, follow_redirects=True)
        presencias = db_manager.get_presencias_hoy()
        estado = app_module.obtener_estado_actual(db_path)
    finally:
        app_module.app.config["DB_PATH"] = "ies.db"
        os.remove(db_path)

    assert respuesta.status_code == 200
    assert len(presencias) == 2
    assert presencias[0].tipo == "entrada"
    assert presencias[1].tipo == "salida"
    assert estado[profesor.id]["presente"] is False
    assert b"Registro de salida exitoso" in respuesta.data
    assert b"Ausente" in respuesta.data


def test_visualizacion_estado_global_muestra_profesores_presentes_y_ausentes(cliente):
    """La interfaz debe representar correctamente el estado global del profesorado."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor_presente = db_manager.insert_profesor(Profesor(nombre="Global Presente", rfid="RG1", activo=1))
        profesor_ausente = db_manager.insert_profesor(Profesor(nombre="Global Ausente", rfid="RG2", activo=1))

        app_module.registrar_presencia(profesor_presente.id, db_path)
        respuesta = cliente.get("/presencia")
    finally:
        app_module.app.config["DB_PATH"] = "ies.db"
        os.remove(db_path)

    assert respuesta.status_code == 200
    assert b"Estado Actual del Profesorado" in respuesta.data
    assert b"Global Presente" in respuesta.data
    assert b"Global Ausente" in respuesta.data
    assert respuesta.data.count(b"Presente") >= 1
    assert respuesta.data.count(b"Ausente") >= 1


def test_ruta_guardias_devuelve_200(monkeypatch, cliente):
    """La ruta /guardias debe responder con código HTTP 200."""
    monkeypatch.setattr(app_module, "obtener_datos_guardias", lambda *_args, **_kwargs: {
        "fecha": "2026-04-15",
        "resumen": {
            "ausencias_detectadas": 0,
            "guardias_necesarias": 0,
            "guardias_cubiertas": 0,
        },
        "ranking_profesores": [],
        "guardias": [],
    })

    respuesta = cliente.get("/guardias")

    assert respuesta.status_code == 200


def test_ruta_guardias_muestra_datos_calculados_desde_bd(monkeypatch, cliente):
    """La vista de guardias debe mostrar la falta y permitir elegir entre profesores disponibles."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor_ausente = db_manager.insert_profesor(Profesor(nombre="Profesor Ausente", rfid="A1", activo=1))
        profesor_cobertura = db_manager.insert_profesor(Profesor(nombre="Profesor Cobertura", rfid="B1", activo=1))

        hoy = datetime.now().strftime("%Y-%m-%d")
        dia_semana = obtener_dia_semana_es(datetime.strptime(hoy, "%Y-%m-%d"))

        db_manager.insert_horario(Horario(profesor_id=profesor_ausente.id, dia=dia_semana, hora=1, aula="A101", asignatura="Matemáticas"))
        db_manager.insert_horario(Horario(profesor_id=profesor_cobertura.id, dia=dia_semana, hora=2, aula="B203", asignatura="Lengua"))
        db_manager.insert_ausencia(Ausencia(profesor_id=profesor_ausente.id, dia=hoy, hora=1, motivo="Enfermedad"))

        monkeypatch.setattr(app_module, "identificar_profesor", lambda: profesor_cobertura.id)

        respuesta_registro = cliente.post("/presencia/registrar", follow_redirects=True)
        respuesta_guardias = cliente.get("/guardias")
    finally:
        app_module.app.config["DB_PATH"] = "ies.db"
        os.remove(db_path)

    assert respuesta_registro.status_code == 200
    assert respuesta_guardias.status_code == 200
    assert b"Profesor Cobertura" in respuesta_guardias.data
    assert b"Profesor Ausente" in respuesta_guardias.data
    assert b"A101" in respuesta_guardias.data
    assert "Matemáticas".encode("utf-8") in respuesta_guardias.data
    assert b"Pendiente" in respuesta_guardias.data
    assert b"Registrar guardia" in respuesta_guardias.data
    assert b"Sin asignar" in respuesta_guardias.data
    assert b"Profesores ordenados por prioridad" in respuesta_guardias.data
    assert b"Aulas que requieren cobertura" in respuesta_guardias.data
    assert b"1 (8:45-9:45)" in respuesta_guardias.data


def test_llegada_del_profesor_elimina_ausencia_y_desaparece_la_guardia(cliente):
    """Si un profesor ficha tras haberse marcado ausente, la ausencia se retira y desaparece la guardia."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor = db_manager.insert_profesor(Profesor(nombre="Profesor Tarde", rfid="T1", activo=1))
        hoy = datetime.now().strftime("%Y-%m-%d")
        dia_semana = obtener_dia_semana_es(datetime.strptime(hoy, "%Y-%m-%d"))

        db_manager.insert_horario(Horario(profesor_id=profesor.id, dia=dia_semana, hora=1, aula="A101", asignatura="Matemáticas"))
        db_manager.insert_ausencia(Ausencia(profesor_id=profesor.id, dia=hoy, hora=1, motivo="No había llegado"))

        respuesta_antes = cliente.get("/guardias")
        respuesta_registro = cliente.post("/presencia/registrar", data={"profesor_id": profesor.id}, follow_redirects=True)
        respuesta_despues = cliente.get("/guardias")

        ausencias = db_manager.get_ausencias_profesor_hoy(profesor.id, hoy)
    finally:
        app_module.app.config["DB_PATH"] = "ies.db"
        os.remove(db_path)

    assert respuesta_antes.status_code == 200
    assert b"Profesor Tarde" in respuesta_antes.data
    assert respuesta_registro.status_code == 200
    assert b"Registro de entrada exitoso" in respuesta_registro.data
    assert respuesta_despues.status_code == 200
    assert b"Profesor Tarde" not in respuesta_despues.data
    assert ausencias == []


def test_ruta_guardias_muestra_ranking_ordenado_segun_criterios(cliente):
    """La tabla de ranking debe respetar el orden definido por las reglas de prioridad."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor_ausente = db_manager.insert_profesor(Profesor(nombre="Profesor Ausente", rfid="RA1", activo=1))
        profesor_mejor = db_manager.insert_profesor(
            Profesor(nombre="Profesor Mejor Prioridad", rfid="RA2", activo=1, guardias_acumuladas=0, guardias_semana=0)
        )
        profesor_peor = db_manager.insert_profesor(
            Profesor(nombre="Profesor Peor Prioridad", rfid="RA3", activo=1, guardias_acumuladas=1, guardias_semana=0)
        )

        hoy = datetime.now().strftime("%Y-%m-%d")
        dia_semana = obtener_dia_semana_es(datetime.strptime(hoy, "%Y-%m-%d"))

        db_manager.insert_horario(Horario(profesor_id=profesor_ausente.id, dia=dia_semana, hora=1, aula="A101", asignatura="Matemáticas"))
        db_manager.insert_horario(Horario(profesor_id=profesor_mejor.id, dia=dia_semana, hora=2, aula="B201", asignatura="Física"))
        db_manager.insert_horario(Horario(profesor_id=profesor_peor.id, dia=dia_semana, hora=3, aula="B202", asignatura="Química"))
        db_manager.insert_ausencia(Ausencia(profesor_id=profesor_ausente.id, dia=hoy, hora=1, motivo="Enfermedad"))
        db_manager.insert_presencia(Presencia(profesor_id=profesor_mejor.id, timestamp=f"{hoy} 08:00:00", tipo="entrada"))
        db_manager.insert_presencia(Presencia(profesor_id=profesor_peor.id, timestamp=f"{hoy} 08:05:00", tipo="entrada"))

        respuesta = cliente.get("/guardias")
    finally:
        app_module.app.config["DB_PATH"] = "ies.db"
        os.remove(db_path)

    assert respuesta.status_code == 200
    assert b"menos guardias acumuladas" in respuesta.data
    assert b"Guardias acumuladas" in respuesta.data

    mejor = "Profesor Mejor Prioridad".encode("utf-8")
    peor = "Profesor Peor Prioridad".encode("utf-8")
    assert mejor in respuesta.data
    assert peor in respuesta.data
    assert respuesta.data.index(mejor) < respuesta.data.index(peor)


def test_ruta_guardias_agrupa_horas_disponibles_en_una_sola_fila_por_profesor(cliente):
    """El ranking visual debe mostrar cada profesor una sola vez aunque esté disponible en varias horas."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor_ausente_1 = db_manager.insert_profesor(Profesor(nombre="Ausente Uno", rfid="U1", activo=1))
        profesor_ausente_2 = db_manager.insert_profesor(Profesor(nombre="Ausente Dos", rfid="U2", activo=1))
        profesor_disponible = db_manager.insert_profesor(
            Profesor(nombre="Profesor Reutilizado", rfid="U3", activo=1, guardias_acumuladas=0, guardias_semana=0)
        )

        hoy = datetime.now().strftime("%Y-%m-%d")
        dia_semana = obtener_dia_semana_es(datetime.strptime(hoy, "%Y-%m-%d"))

        db_manager.insert_horario(Horario(profesor_id=profesor_ausente_1.id, dia=dia_semana, hora=1, aula="A101", asignatura="Matemáticas"))
        db_manager.insert_horario(Horario(profesor_id=profesor_ausente_2.id, dia=dia_semana, hora=2, aula="A102", asignatura="Lengua"))
        db_manager.insert_horario(Horario(profesor_id=profesor_disponible.id, dia=dia_semana, hora=3, aula="B201", asignatura="Física"))
        db_manager.insert_horario(Horario(profesor_id=profesor_disponible.id, dia=dia_semana, hora=4, aula="B202", asignatura="Química"))
        db_manager.insert_ausencia(Ausencia(profesor_id=profesor_ausente_1.id, dia=hoy, hora=1, motivo="Enfermedad"))
        db_manager.insert_ausencia(Ausencia(profesor_id=profesor_ausente_2.id, dia=hoy, hora=2, motivo="Gestión"))
        db_manager.insert_presencia(Presencia(profesor_id=profesor_disponible.id, timestamp=f"{hoy} 08:00:00", tipo="entrada"))

        respuesta = cliente.get("/guardias")
    finally:
        app_module.app.config["DB_PATH"] = "ies.db"
        os.remove(db_path)

    assert respuesta.status_code == 200
    contenido = respuesta.data.decode("utf-8")
    assert contenido.count("Profesor Reutilizado") == 3
    assert "Horas disponibles" in contenido
    assert "1 (8:45-9:45), 2 (9:35-10:25)" in contenido


def test_registrar_guardia_desde_vista_actualiza_bd_y_refresca_valores(cliente):
    """Registrar una guardia desde la vista debe incrementar los contadores y refrescar el ranking."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor_ausente = db_manager.insert_profesor(Profesor(nombre="Profesor Ausente", rfid="GX1", activo=1))
        profesor_guardia = db_manager.insert_profesor(
            Profesor(nombre="Profesor Guardia", rfid="GX2", activo=1, guardias_acumuladas=0, guardias_semana=0)
        )

        hoy = datetime.now().strftime("%Y-%m-%d")
        dia_semana = obtener_dia_semana_es(datetime.strptime(hoy, "%Y-%m-%d"))

        db_manager.insert_horario(Horario(profesor_id=profesor_ausente.id, dia=dia_semana, hora=1, aula="A101", asignatura="Matemáticas"))
        db_manager.insert_horario(Horario(profesor_id=profesor_guardia.id, dia=dia_semana, hora=2, aula="B203", asignatura="Lengua"))
        db_manager.insert_ausencia(Ausencia(profesor_id=profesor_ausente.id, dia=hoy, hora=1, motivo="Enfermedad"))
        db_manager.insert_presencia(Presencia(profesor_id=profesor_guardia.id, timestamp=f"{hoy} 08:00:00", tipo="entrada"))

        respuesta = cliente.post(
            "/guardias/registrar",
            data={"dia": dia_semana, "hora": 1, "aula": "A101", "profesor_asignado": profesor_guardia.id},
            follow_redirects=True,
        )

        profesor_actualizado = db_manager.get_profesor_by_id(profesor_guardia.id)
        guardias_registradas = db_manager.get_guardias_by_dia(dia_semana)
    finally:
        app_module.app.config["DB_PATH"] = "ies.db"
        os.remove(db_path)

    assert respuesta.status_code == 200
    assert b"Guardia registrada correctamente" in respuesta.data
    assert b"Registrar guardia" not in respuesta.data
    assert b"Registrada" in respuesta.data
    assert "Profesor Guardia".encode("utf-8") in respuesta.data
    assert profesor_actualizado.guardias_acumuladas == 1
    assert profesor_actualizado.guardias_semana == 1
    assert len(guardias_registradas) == 1
    assert guardias_registradas[0].profesor_asignado == profesor_guardia.id


def test_guardias_muestra_selector_con_profesores_ordenados_para_la_hora(cliente):
    """Cada guardia pendiente debe mostrar un desplegable con candidatos ordenados por prioridad."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor_ausente = db_manager.insert_profesor(Profesor(nombre="Profesor Ausente", rfid="S1", activo=1))
        profesor_mejor = db_manager.insert_profesor(
            Profesor(nombre="Profesor Mejor", rfid="S2", activo=1, guardias_acumuladas=0, guardias_semana=0)
        )
        profesor_peor = db_manager.insert_profesor(
            Profesor(nombre="Profesor Peor", rfid="S3", activo=1, guardias_acumuladas=2, guardias_semana=0)
        )

        hoy = datetime.now().strftime("%Y-%m-%d")
        dia_semana = obtener_dia_semana_es(datetime.strptime(hoy, "%Y-%m-%d"))

        db_manager.insert_horario(Horario(profesor_id=profesor_ausente.id, dia=dia_semana, hora=1, aula="A101", asignatura="Matemáticas"))
        db_manager.insert_horario(Horario(profesor_id=profesor_mejor.id, dia=dia_semana, hora=2, aula="B201", asignatura="Física"))
        db_manager.insert_horario(Horario(profesor_id=profesor_peor.id, dia=dia_semana, hora=3, aula="B202", asignatura="Química"))
        db_manager.insert_ausencia(Ausencia(profesor_id=profesor_ausente.id, dia=hoy, hora=1, motivo="Enfermedad"))
        db_manager.insert_presencia(Presencia(profesor_id=profesor_mejor.id, timestamp=f"{hoy} 08:00:00", tipo="entrada"))
        db_manager.insert_presencia(Presencia(profesor_id=profesor_peor.id, timestamp=f"{hoy} 08:05:00", tipo="entrada"))

        respuesta = cliente.get("/guardias")
    finally:
        app_module.app.config["DB_PATH"] = "ies.db"
        os.remove(db_path)

    assert respuesta.status_code == 200
    assert b"<select" in respuesta.data
    mejor = "Profesor Mejor".encode("utf-8")
    peor = "Profesor Peor".encode("utf-8")
    assert mejor in respuesta.data
    assert peor in respuesta.data
    assert respuesta.data.index(mejor) < respuesta.data.index(peor)


def test_registrar_guardia_repetida_no_duplica_contadores(cliente):
    """Una guardia registrada dos veces no debe incrementar otra vez los contadores."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor = db_manager.insert_profesor(Profesor(nombre="Profesor Unico", rfid="GX3", activo=1))

        primera = cliente.post(
            "/guardias/registrar",
            data={"dia": "Lunes", "hora": 2, "aula": "A102", "profesor_asignado": profesor.id},
            follow_redirects=True,
        )
        segunda = cliente.post(
            "/guardias/registrar",
            data={"dia": "Lunes", "hora": 2, "aula": "A102", "profesor_asignado": profesor.id},
            follow_redirects=True,
        )

        profesor_actualizado = db_manager.get_profesor_by_id(profesor.id)
    finally:
        app_module.app.config["DB_PATH"] = "ies.db"
        os.remove(db_path)

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert b"La guardia ya estaba registrada" in segunda.data
    assert profesor_actualizado.guardias_acumuladas == 1
    assert profesor_actualizado.guardias_semana == 1


def test_ruta_guardias_sin_bd_inicializada_devuelve_200(cliente):
    """Si la BD no está inicializada, la vista de guardias debe seguir respondiendo."""
    app_module.app.config["DB_PATH"] = os.path.join(tempfile.gettempdir(), "guardias-sin-esquema.db")

    respuesta = cliente.get("/guardias")

    app_module.app.config["DB_PATH"] = "ies.db"

    assert respuesta.status_code == 200
    assert b"Guardias y Sustituciones" in respuesta.data


def test_ruta_presencia_pasa_estado_al_template(monkeypatch, cliente):
    """La ruta /presencia pasa los datos de estado simulados correctamente."""
    estado_simulado = {
        1: {"nombre": "Profesor Test", "presente": True, "ultima_accion": "entrada", "timestamp": "09:00"}
    }
    monkeypatch.setattr(app_module, "obtener_estado_actual", lambda *_args, **_kwargs: estado_simulado)

    respuesta = cliente.get("/presencia")

    assert respuesta.status_code == 200
    assert b"Profesor Test" in respuesta.data
