import sys
import os
import sqlite3
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as app_module
from modules.db.db_manager import DBManager
from modules.db.models import Profesor, Horario, Ausencia


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
    """Registrar presencia debe influir en los datos calculados que muestra /guardias."""
    db_path = crear_bd_temporal()
    app_module.app.config["DB_PATH"] = db_path

    try:
        db_manager = DBManager(db_path)
        profesor_ausente = db_manager.insert_profesor(Profesor(nombre="Profesor Ausente", rfid="A1", activo=1))
        profesor_cobertura = db_manager.insert_profesor(Profesor(nombre="Profesor Cobertura", rfid="B1", activo=1))

        hoy = datetime.now().strftime("%Y-%m-%d")
        dia_semana = datetime.strptime(hoy, "%Y-%m-%d").strftime("%A").capitalize()

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
    assert b"Cubierta" in respuesta_guardias.data
    assert b"Profesores ordenados por prioridad" in respuesta_guardias.data
    assert b"Aulas que requieren cobertura" in respuesta_guardias.data


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
