import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.db.models import Profesor
from modules.presencia import huella_service
from modules.presencia.huella_service import (
    _parsear_respuesta_identificacion,
    _parsear_respuesta_enrolado,
    borrar_huellas_remotas,
)


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


def test_parsear_respuesta_identificacion_ignora_buffer_cancel_ok_fail():
    datos = {
        "message": "No coincide",
        "ok": False,
        "raw": [
            "<R>CANCEL</R>\n<R>OK</R>\nPlease input fingerprint to compare.\n",
            "Mismatch!\n<R>FAIL</R>\n",
        ],
    }

    huella_id, error = _parsear_respuesta_identificacion(datos)

    assert huella_id is None
    assert error == "NO_DATA"


def test_parsear_respuesta_identificacion_mismatch_no_aborta_como_fail():
    huella_id, error = _parsear_respuesta_identificacion(
        {"message": "No coincide", "ok": False, "raw": ["Mismatch!\n<R>FAIL</R>\n"]}
    )

    assert huella_id is None
    assert error == "NO_MATCH"


def test_parsear_respuesta_identificacion_pass_en_raw_tiene_prioridad():
    huella_id, error = _parsear_respuesta_identificacion(
        {"message": "ok", "ok": False, "raw": ["<R>PASS_0</R>\n"]}
    )

    assert huella_id == 0
    assert error is None


def test_parsear_respuesta_enrolado_pass_id_en_dict():
    huella_id, error = _parsear_respuesta_enrolado({"result": "PASS_14"})

    assert huella_id == 14
    assert error is None


def test_parsear_respuesta_enrolado_slot_en_dict():
    huella_id, error = _parsear_respuesta_enrolado({"ok": True, "slot": "#0"})

    assert huella_id == 0
    assert error is None


def test_parsear_respuesta_enrolado_slot_en_texto():
    huella_id, error = _parsear_respuesta_enrolado("#7")

    assert huella_id == 7
    assert error is None


def test_siguiente_slot_libre_usa_primer_hueco():
    profesores = [
        Profesor(id=1, nombre="Ana", huella_id=0, activo=1),
        Profesor(id=2, nombre="Luis", huella_id=2, activo=1),
    ]

    assert huella_service._siguiente_slot_libre(profesores) == 1


def test_borrar_huellas_remotas_ok(monkeypatch):
    import urllib.request

    class FakeResp:
        def __init__(self, data):
            self._data = data

        def read(self):
            return self._data.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(huella_service, "_pifinger_url", lambda: "http://192.168.208.120:5001")
    monkeypatch.setattr(huella_service, "_timeout_lectura_red", lambda: 5)
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: FakeResp('{"result":"OK","ok":true}'))

    ok, mensaje = borrar_huellas_remotas()

    assert ok is True
    assert "borraron" in mensaje.lower()


def test_registrar_huella_profesor_fallback_vincula_huella_existente(monkeypatch):
    recibido = {}

    class FakeDBManager:
        def __init__(self, _db_path):
            self.guardado = None

        def get_profesor_by_id(self, profesor_id):
            return Profesor(id=profesor_id, nombre="Ana", huella_id=None, activo=1)

        def get_profesores(self):
            return [Profesor(id=9, nombre="Sergio", huella_id=0, activo=1)]

        def set_profesor_huella_id(self, profesor_id, huella_id):
            self.guardado = (profesor_id, huella_id)
            return 1

    monkeypatch.setattr(huella_service, "DBManager", FakeDBManager)
    def fake_enrolar_huella_remota(**kwargs):
        recibido["slot"] = kwargs["huella_id_preferida"]
        return 7, None

    monkeypatch.setattr(huella_service, "enrolar_huella_remota", fake_enrolar_huella_remota)
    monkeypatch.setattr(huella_service, "_identificar_via_red", lambda: 7)

    ok, mensaje, huella_id = huella_service.registrar_huella_profesor(1, db_path="ies.db")

    assert ok is True
    assert huella_id == 7
    assert "ID: 7" in mensaje
    assert recibido["slot"] == 1


def test_registrar_huella_profesor_fallback_sin_huella_detectada(monkeypatch):
    class FakeDBManager:
        def __init__(self, _db_path):
            pass

        def get_profesor_by_id(self, profesor_id):
            return Profesor(id=profesor_id, nombre="Luis", huella_id=None, activo=1)

        def get_profesores(self):
            return []

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
    assert "El servidor de huellas no expone endpoint de alta" in mensaje


def test_registrar_huella_profesor_no_reescanea_tras_register(monkeypatch):
    saved = []

    class FakeDBManager:
        def __init__(self, _db_path):
            pass

        def get_profesor_by_id(self, profesor_id):
            return Profesor(id=profesor_id, nombre="Luis", huella_id=None, activo=1)

        def set_profesor_huella_id(self, profesor_id, huella_id):
            saved.append((profesor_id, huella_id))
            return 1

        def get_profesor_por_huella_id(self, huella_id):
            return None

    monkeypatch.setattr(huella_service, "DBManager", FakeDBManager)
    monkeypatch.setattr(
        huella_service,
        "enrolar_huella_remota",
        lambda **_kwargs: (1, None),
    )
    monkeypatch.setattr(huella_service, "_identificar_via_red", lambda huella_ids_validos=None: 0)

    ok, mensaje, huella_id = huella_service.registrar_huella_profesor(
        1, db_path="ies.db", huella_id_preferida=15
    )

    assert ok is True
    assert huella_id == 1
    assert "ID: 1" in mensaje
    assert saved == [(1, 1)]


def test_identificar_huella_limita_la_busqueda_a_huellas_registradas(monkeypatch):
    class FakeDBManager:
        def __init__(self, _db_path="ies.db"):
            pass

        def get_profesores(self):
            return [
                Profesor(id=1, nombre="Ana", huella_id=12, activo=1),
                Profesor(id=2, nombre="Luis", huella_id=19, activo=1),
            ]

        def get_profesor_por_huella_id(self, huella_id):
            return Profesor(id=2, nombre="Luis", huella_id=huella_id, activo=1)

    recibido = {}

    def fake_identificar_via_red(*, huella_ids_validos=None):
        recibido["ids"] = huella_ids_validos
        return 19

    monkeypatch.setattr(huella_service, "DBManager", FakeDBManager)
    monkeypatch.setattr(huella_service, "_identificar_via_red", fake_identificar_via_red)

    huella_id = huella_service.identificar_huella()

    assert huella_id == 19
    assert recibido["ids"] == {12, 19}


def test_identificar_huella_forza_serial_local(monkeypatch):
    class FakeDBManager:
        def __init__(self, _db_path="ies.db"):
            pass

        def get_profesores(self):
            return [Profesor(id=1, nombre="Ana", huella_id=12, activo=1)]

        def get_profesor_por_huella_id(self, huella_id):
            return Profesor(id=1, nombre="Ana", huella_id=huella_id, activo=1)

    monkeypatch.setattr(huella_service, "DBManager", FakeDBManager)
    monkeypatch.setenv("PIFINGER_MODE", "local")
    monkeypatch.setattr(huella_service.platform, "system", lambda: "Linux")
    monkeypatch.setattr(huella_service, "_identificar_serial_local", lambda: 12)
    monkeypatch.setattr(huella_service, "_identificar_via_red", lambda *args, **kwargs: None)

    huella_id = huella_service.identificar_huella()

    assert huella_id == 12
