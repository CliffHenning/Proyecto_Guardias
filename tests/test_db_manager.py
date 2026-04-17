import pytest
import sqlite3
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.db.db_manager import DBManager
from modules.db.models import Profesor, Horario, Presencia, Ausencia, Guardia


@pytest.fixture
def db_manager():
    """Fixture que proporciona un DBManager con base de datos SQLite en memoria."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    schema_path = os.path.join(os.path.dirname(__file__), '..', 'modules', 'db', 'schema.sql')
    with open(schema_path, 'r') as f:
        schema = f.read()
    cursor.executescript(schema)
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
    """Prueba la inserción y recuperación de un profesor."""
    profesor = Profesor(nombre="Juan Pérez", rfid="123456789", activo=1)
    inserted = db_manager.insert_profesor(profesor)
    assert inserted.id is not None

    retrieved = db_manager.get_profesor_by_id(inserted.id)
    assert retrieved.nombre == "Juan Pérez"
    assert retrieved.rfid == "123456789"
    assert retrieved.activo == 1


def test_get_profesores(db_manager):
    """Prueba la obtención de todos los profesores activos."""
    # Insertar varios profesores
    prof1 = Profesor(nombre="Ana García", rfid="111111111", activo=1)
    prof2 = Profesor(nombre="Carlos López", rfid="222222222", activo=0)  # Inactivo
    prof3 = Profesor(nombre="María Rodríguez", rfid="333333333", activo=1)

    db_manager.insert_profesor(prof1)
    db_manager.insert_profesor(prof2)
    db_manager.insert_profesor(prof3)

    profesores = db_manager.get_profesores()
    active_profesores = [p for p in profesores if p.activo == 1]
    assert len(active_profesores) == 2  # Solo los activos


def test_update_profesor(db_manager):
    """Prueba la actualización de un profesor."""
    profesor = Profesor(nombre="Pedro Sánchez", rfid="444444444", activo=1)
    inserted = db_manager.insert_profesor(profesor)

    # Actualizar
    inserted.nombre = "Pedro Sánchez Updated"
    inserted.guardias_acumuladas = 5
    db_manager.update_profesor(inserted)

    retrieved = db_manager.get_profesor_by_id(inserted.id)
    assert retrieved.nombre == "Pedro Sánchez Updated"
    assert retrieved.guardias_acumuladas == 5


def test_delete_profesor(db_manager):
    """Prueba la eliminación suave de un profesor."""
    profesor = Profesor(nombre="Luis Martín", rfid="555555555", activo=1)
    inserted = db_manager.insert_profesor(profesor)

    db_manager.delete_profesor(inserted.id)

    retrieved = db_manager.get_profesor_by_id(inserted.id)
    assert retrieved.activo == 0  # Eliminado suavemente


def test_registrar_guardia_realizada_actualiza_contadores_y_persistencia(db_manager):
    """Registrar una guardia debe incrementar contadores y dejar traza en la tabla guardias."""
    profesor = db_manager.insert_profesor(Profesor(nombre="Profesor Guardia", rfid="RG1", activo=1))

    registrado = db_manager.registrar_guardia_realizada("Lunes", 2, "A101", profesor.id)

    actualizado = db_manager.get_profesor_by_id(profesor.id)
    guardias = db_manager.get_guardias_by_dia("Lunes")

    assert registrado is True
    assert actualizado.guardias_acumuladas == 1
    assert actualizado.guardias_semana == 1
    assert len(guardias) == 1
    assert guardias[0].hora == 2
    assert guardias[0].aula == "A101"
    assert guardias[0].profesor_asignado == profesor.id
    assert guardias[0].cubierta == 1


def test_registrar_guardia_realizada_no_duplica_contadores(db_manager):
    """Una guardia ya registrada no debe incrementar de nuevo los contadores."""
    profesor = db_manager.insert_profesor(Profesor(nombre="Profesor Unico", rfid="RU1", activo=1))

    primer_registro = db_manager.registrar_guardia_realizada("Martes", 3, "B202", profesor.id)
    segundo_registro = db_manager.registrar_guardia_realizada("Martes", 3, "B202", profesor.id)

    actualizado = db_manager.get_profesor_by_id(profesor.id)
    guardias = db_manager.get_guardias_by_dia("Martes")

    assert primer_registro is True
    assert segundo_registro is False
    assert actualizado.guardias_acumuladas == 1
    assert actualizado.guardias_semana == 1
    assert len(guardias) == 1


def test_delete_ausencias_profesor_hoy_elimina_ausencias_activas(db_manager):
    """La eliminación de ausencias activas del día debe afectar solo al profesor indicado."""
    profesor_1 = db_manager.insert_profesor(Profesor(nombre="Profesor Uno", rfid="A1", activo=1))
    profesor_2 = db_manager.insert_profesor(Profesor(nombre="Profesor Dos", rfid="A2", activo=1))
    hoy = datetime.now().strftime("%Y-%m-%d")

    db_manager.insert_ausencia(Ausencia(profesor_id=profesor_1.id, dia=hoy, hora=1, motivo="Ausencia 1"))
    db_manager.insert_ausencia(Ausencia(profesor_id=profesor_1.id, dia=hoy, hora=2, motivo="Ausencia 2"))
    db_manager.insert_ausencia(Ausencia(profesor_id=profesor_2.id, dia=hoy, hora=1, motivo="Ausencia 3"))

    deleted = db_manager.delete_ausencias_profesor_hoy(profesor_1.id, hoy)
    ausencias_prof_1 = db_manager.get_ausencias_profesor_hoy(profesor_1.id, hoy)
    ausencias_prof_2 = db_manager.get_ausencias_profesor_hoy(profesor_2.id, hoy)

    assert deleted == 2
    assert ausencias_prof_1 == []
    assert len(ausencias_prof_2) == 1


def test_get_guardia_cubierta_devuelve_la_guardia_registrada(db_manager):
    """Debe poder recuperarse la guardia cubierta de un tramo concreto."""
    profesor = db_manager.insert_profesor(Profesor(nombre="Profesor Cobertura", rfid="RC1", activo=1))
    db_manager.registrar_guardia_realizada("Jueves", 1, "A101", profesor.id)

    guardia = db_manager.get_guardia_cubierta("Jueves", 1, "A101")

    assert guardia is not None
    assert guardia.profesor_asignado == profesor.id


def test_insert_and_get_horarios_by_dia(db_manager):
    """Prueba la inserción y consulta de horarios por día."""
    # Primero insertar un profesor
    profesor = Profesor(nombre="Test Profesor", rfid="666666666", activo=1)
    prof_inserted = db_manager.insert_profesor(profesor)

    horario = Horario(profesor_id=prof_inserted.id, dia="Lunes", hora=1, aula="A101", asignatura="Matemáticas")
    inserted = db_manager.insert_horario(horario)
    assert inserted.id is not None

    horarios = db_manager.get_horarios_by_dia("Lunes")
    assert len(horarios) == 1
    assert horarios[0].asignatura == "Matemáticas"


def test_insert_and_get_presencia_hoy(db_manager):
    """Prueba la inserción y consulta de presencia para hoy."""
    # Insertar profesor
    profesor = Profesor(nombre="Test Presencia", rfid="777777777", activo=1)
    prof_inserted = db_manager.insert_profesor(profesor)

    presencia = Presencia(profesor_id=prof_inserted.id, tipo="entrada")
    inserted = db_manager.insert_presencia(presencia)
    assert inserted.id is not None

    # Obtener la última presencia de hoy
    last_presencia = db_manager.get_presencia_hoy(prof_inserted.id)
    assert last_presencia.tipo == "entrada"
    assert last_presencia.profesor_id == prof_inserted.id


def test_insert_presencia_guarda_timestamp_local(db_manager):
    """La presencia debe guardarse con la hora local actual y no con UTC de SQLite."""
    profesor = Profesor(nombre="Test Timestamp", rfid="171717171", activo=1)
    prof_inserted = db_manager.insert_profesor(profesor)

    antes = datetime.now().replace(microsecond=0)
    presencia = Presencia(profesor_id=prof_inserted.id, tipo="entrada")
    inserted = db_manager.insert_presencia(presencia)
    despues = datetime.now().replace(microsecond=0)

    timestamp_guardado = datetime.strptime(inserted.timestamp, "%Y-%m-%d %H:%M:%S")

    assert antes <= timestamp_guardado <= despues


def test_get_presencias_hoy(db_manager):
    """Prueba la obtención de todas las presencias para hoy."""
    # Insertar otro profesor y presencia
    profesor2 = Profesor(nombre="Test Presencia 2", rfid="888888888", activo=1)
    prof2_inserted = db_manager.insert_profesor(profesor2)

    presencia2 = Presencia(profesor_id=prof2_inserted.id, tipo="salida")
    db_manager.insert_presencia(presencia2)

    presencias = db_manager.get_presencias_hoy()
    assert len(presencias) >= 1  # Al menos la insertada


def test_insert_and_get_ausencias_hoy(db_manager):
    """Prueba la inserción y consulta de ausencias para hoy."""
    from datetime import datetime
    hoy = datetime.now().strftime("%Y-%m-%d")

    # Insert profesor
    profesor = Profesor(nombre="Test Ausencia", rfid="999999999", activo=1)
    prof_inserted = db_manager.insert_profesor(profesor)

    ausencia = Ausencia(profesor_id=prof_inserted.id, dia=hoy, hora=2, motivo="Enfermedad")
    inserted = db_manager.insert_ausencia(ausencia)
    assert inserted.id is not None

    ausencias = db_manager.get_ausencias_hoy()
    assert len(ausencias) >= 1
    assert ausencias[-1].motivo == "Enfermedad"


def test_ensure_ausencia_no_duplica_registros(db_manager):
    """ensure_ausencia debe devolver la misma ausencia si ya existe en profesor, día y hora."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    profesor = db_manager.insert_profesor(Profesor(nombre="Test Ensure Ausencia", rfid="141414141", activo=1))

    primera = db_manager.ensure_ausencia(Ausencia(profesor_id=profesor.id, dia=hoy, hora=2, motivo="Automática"))
    segunda = db_manager.ensure_ausencia(Ausencia(profesor_id=profesor.id, dia=hoy, hora=2, motivo="Automática"))
    ausencias = db_manager.get_ausencias_profesor_hoy(profesor.id, hoy)

    assert primera.id == segunda.id
    assert len(ausencias) == 1


def test_insert_and_get_guardias_by_dia(db_manager):
    """Prueba la inserción y consulta de guardias por día."""
    # Insertar profesor
    profesor = Profesor(nombre="Test Guardia", rfid="000000000", activo=1)
    prof_inserted = db_manager.insert_profesor(profesor)

    guardia = Guardia(dia="Martes", hora=3, aula="B202", profesor_asignado=prof_inserted.id, cubierta=0)
    inserted = db_manager.insert_guardia(guardia)
    assert inserted.id is not None

    guardias = db_manager.get_guardias_by_dia("Martes")
    assert len(guardias) >= 1
    assert guardias[-1].aula == "B202"


def test_update_guardia_cubierta(db_manager):
    """Prueba la actualización de una guardia como cubierta."""
    # Insertar guardia
    profesor = Profesor(nombre="Test Update Guardia", rfid="121212121", activo=1)
    prof_inserted = db_manager.insert_profesor(profesor)

    guardia = Guardia(dia="Miércoles", hora=4, aula="C303", profesor_asignado=prof_inserted.id, cubierta=0)
    inserted = db_manager.insert_guardia(guardia)

    db_manager.update_guardia_cubierta(inserted.id, cubierta=1)

    guardias = db_manager.get_guardias_by_dia("Miércoles")
    updated_guardia = next((g for g in guardias if g.id == inserted.id), None)
    assert updated_guardia.cubierta == 1


def test_actualizar_guardias_profesor(db_manager):
    """Prueba la actualización de los contadores de guardias del profesor."""
    profesor = Profesor(nombre="Test Counters", rfid="131313131", activo=1, guardias_acumuladas=0, guardias_semana=0)
    inserted = db_manager.insert_profesor(profesor)

    db_manager.actualizar_guardias_profesor(inserted.id)

    retrieved = db_manager.get_profesor_by_id(inserted.id)
    assert retrieved.guardias_acumuladas == 1
    assert retrieved.guardias_semana == 1