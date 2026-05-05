import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.db.models import Profesor
from modules.presencia import huella_service
from modules.presencia.huella_service import _parsear_respuesta_identificacion


def test_parsear_respuesta_identificacion_formato_pifinger_embebido():
    datos = {
        "result": "Matched!\n<R>PASS_0</R>\n<S>DS=7E</S>\n"
    }

    huella_id, error = _parsear_respuesta_identificacion(datos)

    assert huella_id == 0
    assert error is None


def test_parsear_respuesta_identificacion_pass_con_id_en_texto():
    huella_id, error = _parsear_respuesta_identificacion("PASS_12")

    assert huella_id == 12
    assert error is None


def test_registrar_huella_profesor_fallback_vincula_huella_existente(monkeypatch):
    class FakeDBManager:
        def __init__(self, _db_path):
            self.guardado = None

        def get_profesor_by_id(self, profesor_id):
            return Profesor(id=profesor_id, nombre="Ana", huella_id=None, activo=1)

        def set_profesor_huella_id(self, profesor_id, huella_id):
            self.guardado = (profesor_id, huella_id)
            return 1

    monkeypatch.setattr(huella_service, "DBManager", FakeDBManager)
    monkeypatch.setattr(
        huella_service,
        "enrolar_huella_remota",
        lambda **_kwargs: (None, "El servidor de huellas no expone endpoint de alta."),
    )
    monkeypatch.setattr(huella_service, "_identificar_via_red", lambda: 7)

    ok, mensaje, huella_id = huella_service.registrar_huella_profesor(1, db_path="ies.db")

    assert ok is True
    assert huella_id == 7
    assert "Se vinculó la huella existente" in mensaje


def test_registrar_huella_profesor_fallback_sin_huella_detectada(monkeypatch):
    class FakeDBManager:
        def __init__(self, _db_path):
            pass

        def get_profesor_by_id(self, profesor_id):
            return Profesor(id=profesor_id, nombre="Luis", huella_id=None, activo=1)

        def set_profesor_huella_id(self, profesor_id, huella_id):
            return 1

    monkeypatch.setattr(huella_service, "DBManager", FakeDBManager)
    monkeypatch.setattr(
        huella_service,
        "enrolar_huella_remota",
        lambda **_kwargs: (None, "El servidor de huellas no expone endpoint de alta."),
    )
    monkeypatch.setattr(huella_service, "_identificar_via_red", lambda: None)

    ok, mensaje, huella_id = huella_service.registrar_huella_profesor(1, db_path="ies.db")

    assert ok is False
    assert huella_id is None
    assert "No hay endpoint de alta" in mensaje


def test_identificar_huella_limita_la_busqueda_a_huellas_registradas(monkeypatch):
    class FakeDBManager:
        def __init__(self, _db_path="ies.db"):
            pass

        def get_profesores(self):
            return [
                Profesor(id=1, nombre="Ana", huella_id=12, activo=1),
                Profesor(id=2, nombre="Luis", huella_id=19, activo=1),
            ]

    recibido = {}

    def fake_identificar_via_red(*, huella_ids_validos=None):
        recibido["ids"] = huella_ids_validos
        return 19

    monkeypatch.setattr(huella_service, "DBManager", FakeDBManager)
    monkeypatch.setattr(huella_service, "_identificar_via_red", fake_identificar_via_red)

    profesor_id = huella_service.identificar_huella()

    assert profesor_id == 2
    assert recibido["ids"] == {12, 19}
