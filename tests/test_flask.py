import sys
import os

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
                "profesor_asignado_id": None,
                "profesor_ausente": "Profesor Ausente",
                "profesor_asignado": "Sin asignar",
                "estado": "Pendiente",
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
    assert b"Pendiente" in respuesta.data


def test_ruta_presencia_pasa_estado_al_template(monkeypatch, cliente):
    """La ruta /presencia pasa los datos de estado simulados correctamente."""
    estado_simulado = {
        1: {"nombre": "Profesor Test", "presente": True, "ultima_accion": "entrada", "timestamp": "09:00"}
    }
    monkeypatch.setattr(app_module, "obtener_estado_actual", lambda *_args, **_kwargs: estado_simulado)

    respuesta = cliente.get("/presencia")

    assert respuesta.status_code == 200
    assert b"Profesor Test" in respuesta.data
