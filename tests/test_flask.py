import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as app_module


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


def test_ruta_presencia_muestra_botonera_dinamica_y_estados(monkeypatch, cliente):
    """La vista de presencia debe renderizar el estado simulado del profesorado."""
    estado_simulado = {
        1: {"nombre": "Ana García", "presente": True, "ultima_accion": "entrada", "timestamp": "09:00"},
        2: {"nombre": "Luis Pérez", "presente": False, "ultima_accion": None, "timestamp": None},
    }
    monkeypatch.setattr(app_module, "obtener_estado_actual", lambda *_args, **_kwargs: estado_simulado)

    respuesta = cliente.get("/presencia")

    assert respuesta.status_code == 200
    assert "Ana García".encode("utf-8") in respuesta.data
    assert "Luis Pérez".encode("utf-8") in respuesta.data
    assert b"Presente" in respuesta.data
    assert b"Ausente" in respuesta.data


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


def test_ruta_guardias_pasa_datos_simulados(monkeypatch, cliente):
    """La vista de guardias debe renderizar los datos simulados recibidos del motor."""
    monkeypatch.setattr(app_module, "obtener_datos_guardias", lambda *_args, **_kwargs: {
        "fecha": "2026-04-15",
        "resumen": {
            "ausencias_detectadas": 1,
            "guardias_necesarias": 1,
            "guardias_cubiertas": 0,
        },
        "ranking_profesores": [
            {
                "posicion": 1,
                "nombre": "Profesor Cobertura",
                "guardias_semana": 0,
                "guardias_acumuladas": 0,
                "carga_lectiva": 12,
                "horas_disponibles": [1],
                "horas_disponibles_texto": "1 (8:45-9:45)",
            }
        ],
        "guardias": [
            {
                "dia": "Martes",
                "hora": 1,
                "hora_texto": "1 (8:45-9:45)",
                "aula": "A101",
                "asignatura": "Matemáticas",
                "profesor_ausente_id": 9,
                "profesor_asignado_id": 2,
                "profesor_ausente": "Profesor Ausente",
                "profesor_asignado": "Profesor Cobertura",
                "estado": "Calculada",
                "registrada": False,
                "candidatos": [
                    {
                        "id": 2,
                        "nombre": "Profesor Cobertura",
                        "guardias_semana": 0,
                        "guardias_acumuladas": 0,
                        "carga_lectiva": 12,
                    }
                ],
            }
        ],
    })

    respuesta = cliente.get("/guardias")

    assert respuesta.status_code == 200
    assert b"Profesor Ausente" in respuesta.data
    assert b"Profesor Cobertura" in respuesta.data
    assert b"A101" in respuesta.data
    assert b"Calculada" in respuesta.data
    assert b"Matem\xc3\xa1ticas" in respuesta.data


def test_ruta_horario_devuelve_200(monkeypatch, cliente):
    """La ruta /horario debe responder con código HTTP 200."""
    monkeypatch.setattr(app_module, "obtener_datos_horario", lambda *_args, **_kwargs: {
        "fecha": "2026-04-15",
        "fecha_texto": "Miércoles 2026-04-15",
        "dia_semana": "Miércoles",
        "profesores": [{"id": 1, "nombre": "Ana García", "departamento": "Matemáticas"}],
        "horas": [{"hora": 1, "hora_texto": "1 (8:45-9:45)"}],
        "celdas": {
            1: {
                1: {
                    "tiene_horario": True,
                    "tipo": "clase",
                    "asignatura": "Álgebra",
                    "aula": "A201",
                    "ausente": False,
                    "motivo": "",
                }
            }
        },
        "ausencias_totales": 0,
        "resumen": {"ausencias_detectadas": 0, "guardias_necesarias": 0, "guardias_cubiertas": 0},
        "ranking_profesores": [],
        "guardias": [],
    })

    respuesta = cliente.get("/horario")

    assert respuesta.status_code == 200
    assert b"Horario del Profesorado" in respuesta.data


def test_ruta_horario_marca_ausente_en_rojo(monkeypatch, cliente):
    """La vista de horario debe mostrar el estado Ausente cuando haya ausencia en la celda."""
    monkeypatch.setattr(app_module, "obtener_datos_horario", lambda *_args, **_kwargs: {
        "fecha": "2026-04-15",
        "fecha_texto": "Miércoles 2026-04-15",
        "dia_semana": "Miércoles",
        "profesores": [{"id": 5, "nombre": "Profesor Ausente", "departamento": "Lengua"}],
        "horas": [{"hora": 2, "hora_texto": "2 (9:35-10:25)"}],
        "celdas": {
            5: {
                2: {
                    "tiene_horario": True,
                    "tipo": "clase",
                    "asignatura": "Lengua",
                    "aula": "B103",
                    "ausente": True,
                    "motivo": "Ausencia detectada automáticamente",
                }
            }
        },
        "ausencias_totales": 1,
        "resumen": {"ausencias_detectadas": 1, "guardias_necesarias": 1, "guardias_cubiertas": 0},
        "ranking_profesores": [],
        "guardias": [],
    })

    respuesta = cliente.get("/horario")

    assert respuesta.status_code == 200
    assert b"Profesor Ausente" in respuesta.data
    assert b"Ausente" in respuesta.data
    assert b"B103" in respuesta.data


def test_ruta_presencia_pasa_estado_al_template(monkeypatch, cliente):
    """La ruta /presencia pasa los datos de estado simulados correctamente."""
    estado_simulado = {
        1: {"nombre": "Profesor Test", "presente": True, "ultima_accion": "entrada", "timestamp": "09:00"}
    }
    monkeypatch.setattr(app_module, "obtener_estado_actual", lambda *_args, **_kwargs: estado_simulado)

    respuesta = cliente.get("/presencia")

    assert respuesta.status_code == 200
    assert b"Profesor Test" in respuesta.data


def test_ruta_enrolar_huella_profesor_ok(monkeypatch, cliente):
    """La ruta de enrolado debe mostrar mensaje de éxito cuando el servicio responde OK."""
    monkeypatch.setattr(app_module, "registrar_huella_profesor", lambda *_args, **_kwargs: (True, "Huella registrada", 17))

    respuesta = cliente.post(
        "/presencia/enrolar",
        data={"profesor_id": 1, "huella_id_preferida": 17, "next": "/presencia"},
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert b"Huella registrada" in respuesta.data


def test_ruta_enrolar_huella_profesor_requiere_profesor(cliente):
    """Debe validar que exista profesor seleccionado en el formulario."""
    respuesta = cliente.post(
        "/presencia/enrolar",
        data={"next": "/presencia"},
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert b"Selecciona un profesor" in respuesta.data


def test_obtener_datos_guardias_no_retrocede_a_ultima_fecha_con_ausencias(monkeypatch):
    class StubManager:
        def get_ausencias_hoy(self, fecha=None):
            return []

        def get_guardias_by_dia(self, dia):
            assert dia == "2026-04-20"
            return []

        def get_fechas_con_ausencias(self):
            return ["2026-04-16"]

        def get_profesor_by_id(self, profesor_id):
            return None

    class StubMotor:
        def __init__(self, db_path=None):
            self.db_manager = StubManager()

        def detectar_ausencias_automaticas(self, ahora=None, margen_minutos=10, hora_corte_global=None):
            return []

        def calcular_guardias(self, dia=None):
            assert dia == "2026-04-20"
            return {"ranking_profesores": [], "guardias": []}

    monkeypatch.setattr(app_module, "MotorGuardias", StubMotor)

    datos = app_module.obtener_datos_guardias(dia=None, ahora=datetime.strptime("2026-04-20 09:00:00", "%Y-%m-%d %H:%M:%S"))

    assert datos["fecha"] == "2026-04-20"
    assert datos["fechas_disponibles"] == ["2026-04-16"]
    assert datos["guardias"] == []
