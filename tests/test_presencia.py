import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import modules.presencia.registro as registro


def test_identificar_profesor_metodo_desconocido_lanza_valueerror(monkeypatch):
    """Un método de presencia no soportado debe lanzar ValueError con mensaje descriptivo."""
    monkeypatch.setenv("METODO_PRESENCIA", "voz")

    with pytest.raises(ValueError, match="Método de presencia desconocido"):
        registro.identificar_profesor()


def test_identificar_profesor_usa_huella_por_defecto(monkeypatch):
    """Si no se define METODO_PRESENCIA, el método por defecto es huella."""
    monkeypatch.delenv("METODO_PRESENCIA", raising=False)
    monkeypatch.setattr(registro, "identificar_huella", lambda: 7)

    resultado = registro.identificar_profesor()

    assert resultado == 7


def test_identificar_profesor_huella_devuelve_id_simulado(monkeypatch):
    """Con METODO_PRESENCIA=huella, identificar_profesor() devuelve el id del servicio de huella simulado."""
    monkeypatch.setenv("METODO_PRESENCIA", "huella")
    monkeypatch.setattr(registro, "identificar_huella", lambda: 15)

    resultado = registro.identificar_profesor()

    assert resultado == 15


def test_identificar_profesor_huella_puede_devolver_none(monkeypatch):
    """Si el lector de huella no reconoce al profesor, identificar_profesor() devuelve None."""
    monkeypatch.setenv("METODO_PRESENCIA", "huella")
    monkeypatch.setattr(registro, "identificar_huella", lambda: None)

    resultado = registro.identificar_profesor()

    assert resultado is None
