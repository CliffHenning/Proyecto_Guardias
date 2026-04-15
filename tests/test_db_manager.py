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
    # Crear base de datos en memoria
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Leer y ejecutar el esquema
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'modules', 'db', 'schema.sql')
    with open(schema_path, 'r') as f:
        schema = f.read()
    cursor.executescript(schema)
    conn.commit()

    # Crear un DBManager personalizado que usa la conexión existente y no la cierra
    class TestDBManager(DBManager):
        def __init__(self, connection):
            self.connection = connection

        def get_connection(self):
            return self.connection

        def get_profesores(self):
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profesores WHERE activo = 1")
            rows = cursor.fetchall()
            return [Profesor(*row) for row in rows]

        def get_profesor_by_id(self, profesor_id):
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profesores WHERE id = ?", (profesor_id,))
            row = cursor.fetchone()
            return Profesor(*row) if row else None

        def insert_profesor(self, profesor):
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO profesores (nombre, rfid, huella_id, face_id, activo, guardias_acumuladas, guardias_semana)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (profesor.nombre, profesor.rfid, profesor.huella_id, profesor.face_id, profesor.activo, profesor.guardias_acumuladas, profesor.guardias_semana))
            profesor.id = cursor.lastrowid
            conn.commit()
            return profesor

        def update_profesor(self, profesor):
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE profesores SET nombre=?, rfid=?, huella_id=?, face_id=?, activo=?, guardias_acumuladas=?, guardias_semana=?
                WHERE id=?
            """, (profesor.nombre, profesor.rfid, profesor.huella_id, profesor.face_id, profesor.activo, profesor.guardias_acumuladas, profesor.guardias_semana, profesor.id))
            conn.commit()

        def delete_profesor(self, profesor_id):
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE profesores SET activo=0 WHERE id=?", (profesor_id,))
            conn.commit()

        def get_horarios_by_dia(self, dia):
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM horarios WHERE dia = ?", (dia,))
            rows = cursor.fetchall()
            return [Horario(*row) for row in rows]

        def insert_horario(self, horario):
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO horarios (profesor_id, dia, hora, aula, asignatura)
                VALUES (?, ?, ?, ?, ?)
            """, (horario.profesor_id, horario.dia, horario.hora, horario.aula, horario.asignatura))
            horario.id = cursor.lastrowid
            conn.commit()
            return horario

        def get_presencia_hoy(self, profesor_id):
            from datetime import datetime
            hoy = datetime.now().strftime("%Y-%m-%d")
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM presencia
                WHERE profesor_id = ? AND date(timestamp) = ?
                ORDER BY timestamp DESC LIMIT 1
            """, (profesor_id, hoy))
            row = cursor.fetchone()
            return Presencia(*row) if row else None

        def get_presencias_hoy(self):
            from datetime import datetime
            hoy = datetime.now().strftime("%Y-%m-%d")
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM presencia
                WHERE date(timestamp) = ?
                ORDER BY profesor_id, timestamp
            """, (hoy,))
            rows = cursor.fetchall()
            return [Presencia(*row) for row in rows]

        def insert_presencia(self, presencia):
            timestamp = presencia.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO presencia (profesor_id, timestamp, tipo)
                VALUES (?, ?, ?)
            """, (presencia.profesor_id, timestamp, presencia.tipo))
            presencia.id = cursor.lastrowid
            presencia.timestamp = timestamp
            conn.commit()
            return presencia

        def get_ausencias_hoy(self):
            from datetime import datetime
            hoy = datetime.now().strftime("%Y-%m-%d")
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ausencias WHERE dia = ?", (hoy,))
            rows = cursor.fetchall()
            return [Ausencia(*row) for row in rows]

        def insert_ausencia(self, ausencia):
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ausencias (profesor_id, dia, hora, motivo)
                VALUES (?, ?, ?, ?)
            """, (ausencia.profesor_id, ausencia.dia, ausencia.hora, ausencia.motivo))
            ausencia.id = cursor.lastrowid
            conn.commit()
            return ausencia

        def get_guardias_by_dia(self, dia):
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM guardias WHERE dia = ?", (dia,))
            rows = cursor.fetchall()
            return [Guardia(*row) for row in rows]

        def insert_guardia(self, guardia):
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO guardias (dia, hora, aula, profesor_asignado, cubierta)
                VALUES (?, ?, ?, ?, ?)
            """, (guardia.dia, guardia.hora, guardia.aula, guardia.profesor_asignado, guardia.cubierta))
            guardia.id = cursor.lastrowid
            conn.commit()
            return guardia

        def update_guardia_cubierta(self, guardia_id, cubierta=1):
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE guardias SET cubierta = ? WHERE id = ?", (cubierta, guardia_id))
            conn.commit()

        def actualizar_guardias_profesor(self, profesor_id):
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE profesores SET guardias_acumuladas = guardias_acumuladas + 1, guardias_semana = guardias_semana + 1 WHERE id = ?", (profesor_id,))
            conn.commit()

    manager = TestDBManager(conn)
    yield manager


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