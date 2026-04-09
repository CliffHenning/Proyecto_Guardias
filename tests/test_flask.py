import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as app_module


def test_ruta_index_devuelve_200(cliente):
    """La ruta raíz / debe responder con código HTTP 200."""
    respuesta = cliente.get("/")

    assert respuesta.status_code == 200


def test_ruta_presencia_devuelve_200(monkeypatch, cliente):
    """La ruta /presencia debe responder con 200 sin acceder a la base de datos real."""
    monkeypatch.setattr(app_module, "obtener_estado_actual", lambda: {})

    respuesta = cliente.get("/presencia")

    assert respuesta.status_code == 200


def test_ruta_guardias_devuelve_200(cliente):
    """La ruta /guardias debe responder con código HTTP 200."""
    respuesta = cliente.get("/guardias")

    assert respuesta.status_code == 200


def test_ruta_presencia_pasa_estado_al_template(monkeypatch, cliente):
    """La ruta /presencia pasa los datos de estado simulados correctamente."""
    estado_simulado = {
        1: {"nombre": "Profesor Test", "presente": True, "ultima_accion": "entrada", "timestamp": "09:00"}
    }
    monkeypatch.setattr(app_module, "obtener_estado_actual", lambda: estado_simulado)

    respuesta = cliente.get("/presencia")

    assert respuesta.status_code == 200
    assert b"Profesor Test" in respuesta.data
