import os
import sqlite3
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.db.db_manager import DBManager
from modules.db.models import Ausencia, Guardia, Horario, Presencia, Profesor


@pytest.fixture
def db_manager():
    """Proporciona un DBManager con SQLite en memoria para pruebas de acceso a datos."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    schema_path = os.path.join(os.path.dirname(__file__), "..", "modules", "db", "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as file:
        cursor.executescript(file.read())
    conn.commit()

    class NoCloseConnection:
        def __init__(self, connection):
            self._connection = connection

        def close(self):
            return None

        def __getattr__(self, name):
            return getattr(self._connection, name)

    class TestDBManager(DBManager):
        def __init__(self, connection):
            self.connection = connection

        def get_connection(self):
            return self.connection

    manager = TestDBManager(NoCloseConnection(conn))
    yield manager
    conn.close()


def test_insert_and_get_profesor(db_manager):
    profesor = Profesor(nombre="Juan Pérez", departamento="Matemáticas", huella_id=12, activo=1)

    inserted = db_manager.insert_profesor(profesor)
    retrieved = db_manager.get_profesor_by_id(inserted.id)

    assert inserted.id is not None
    assert retrieved.nombre == "Juan Pérez"
    assert retrieved.departamento == "Matemáticas"
    assert retrieved.huella_id == 12
    assert retrieved.activo == 1


def test_update_profesor(db_manager):
    profesor = db_manager.insert_profesor(Profesor(nombre="Pedro Sánchez", huella_id=44, activo=1))
    profesor.nombre = "Pedro Sánchez Updated"
    profesor.guardias_acumuladas = 5

    db_manager.update_profesor(profesor)

    retrieved = db_manager.get_profesor_by_id(profesor.id)
    assert retrieved.nombre == "Pedro Sánchez Updated"
    assert retrieved.guardias_acumuladas == 5


def test_insert_and_get_horarios_by_dia(db_manager):
    profesor = db_manager.insert_profesor(Profesor(nombre="Test Profesor", huella_id=66, activo=1))
    horario = Horario(
        profesor_id=profesor.id,
        dia="Lunes",
        hora=1,
        tipo="clase",
        aula="A101",
        asignatura="Matemáticas",
    )

    inserted = db_manager.insert_horario(horario)
    horarios = db_manager.get_horarios_by_dia("Lunes")

    assert inserted.id is not None
    assert len(horarios) == 1
    assert horarios[0].tipo == "clase"
    assert horarios[0].asignatura == "Matemáticas"


def test_insert_and_get_presencia_hoy(db_manager):
    profesor = db_manager.insert_profesor(Profesor(nombre="Test Presencia", huella_id=77, activo=1))
    presencia = Presencia(profesor_id=profesor.id, tipo="entrada")

    inserted = db_manager.insert_presencia(presencia)
    last_presencia = db_manager.get_presencia_hoy(profesor.id)

    assert inserted.id is not None
    assert last_presencia.tipo == "entrada"
    assert last_presencia.profesor_id == profesor.id


def test_insert_and_get_ausencias_hoy(db_manager):
    hoy = datetime.now().strftime("%Y-%m-%d")
    profesor = db_manager.insert_profesor(Profesor(nombre="Test Ausencia", huella_id=99, activo=1))
    ausencia = Ausencia(profesor_id=profesor.id, dia=hoy, hora=2, motivo="Enfermedad")

    inserted = db_manager.insert_ausencia(ausencia)
    ausencias = db_manager.get_ausencias_hoy()

    assert inserted.id is not None
    assert len(ausencias) >= 1
    assert ausencias[-1].motivo == "Enfermedad"


def test_insert_and_get_guardias_by_dia(db_manager):
    profesor = db_manager.insert_profesor(Profesor(nombre="Test Guardia", huella_id=0, activo=1))
    guardia = Guardia(
        dia="Martes",
        hora=3,
        aula="B202",
        asignatura="Guardia",
        profesor_ausente_id=15,
        profesor_cubre_id=profesor.id,
        cubierta=0,
    )

    inserted = db_manager.insert_guardia(guardia)
    guardias = db_manager.get_guardias_by_dia("Martes")

    assert inserted.id is not None
    assert len(guardias) == 1
    assert guardias[0].aula == "B202"
    assert guardias[0].profesor_cubre_id == profesor.id


def test_update_guardia_cubierta(db_manager):
    profesor = db_manager.insert_profesor(Profesor(nombre="Test Update Guardia", huella_id=121, activo=1))
    guardia = db_manager.insert_guardia(
        Guardia(
            dia="Miércoles",
            hora=4,
            aula="C303",
            asignatura="Guardia",
            profesor_ausente_id=22,
            profesor_cubre_id=profesor.id,
            cubierta=0,
        )
    )

    db_manager.update_guardia_cubierta(guardia.id, cubierta=1)

    updated_guardia = db_manager.get_guardias_by_dia("Miércoles")[0]
    assert updated_guardia.cubierta == 1


def test_registrar_guardia_realizada_actualiza_contadores_y_persistencia(db_manager):
    profesor = db_manager.insert_profesor(Profesor(nombre="Profesor Guardia", huella_id=201, activo=1))

    registrado = db_manager.registrar_guardia_realizada(
        "Lunes",
        2,
        "A101",
        profesor.id,
        asignatura="Guardia",
        profesor_ausente_id=9,
    )

    actualizado = db_manager.get_profesor_by_id(profesor.id)
    guardias = db_manager.get_guardias_by_dia("Lunes")

    assert registrado is True
    assert actualizado.guardias_acumuladas == 1
    assert actualizado.guardias_semana == 1
    assert len(guardias) == 1
    assert guardias[0].profesor_ausente_id == 9
    assert guardias[0].profesor_cubre_id == profesor.id
    assert guardias[0].cubierta == 1


def test_replace_guardias_calculadas_persiste_resultado_del_calculo(db_manager):
    guardias = [
        Guardia(dia="2026-04-16", hora=1, aula="A101", asignatura="Matemáticas", profesor_ausente_id=1, profesor_cubre_id=3, cubierta=0),
        Guardia(dia="2026-04-16", hora=2, aula="A102", asignatura="Lengua", profesor_ausente_id=2, profesor_cubre_id=4, cubierta=0),
    ]

    db_manager.replace_guardias_calculadas("2026-04-16", guardias)

    persistidas = db_manager.get_guardias_by_dia("2026-04-16")
    assert len(persistidas) == 2
    assert persistidas[0].profesor_ausente_id == 1
    assert persistidas[0].profesor_cubre_id == 3
    assert persistidas[0].cubierta == 0