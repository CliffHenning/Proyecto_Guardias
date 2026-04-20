import sqlite3
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from modules.db.models import Profesor, Horario, Presencia, Ausencia, Guardia

class DBManager:
    def __init__(self, db_path="ies.db"):
        self.db_path = db_path

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def _ensure_profesores_schema(self, conn):
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(profesores)")
        columnas = {row[1] for row in cursor.fetchall()}
        if "departamento" not in columnas:
            cursor.execute("ALTER TABLE profesores ADD COLUMN departamento TEXT")
            conn.commit()

    def _ensure_horarios_schema(self, conn):
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(horarios)")
        columnas = {row[1] for row in cursor.fetchall()}
        if "tipo" not in columnas:
            cursor.execute("ALTER TABLE horarios ADD COLUMN tipo TEXT")
            cursor.execute(
                """
                UPDATE horarios
                SET tipo = CASE
                    WHEN lower(trim(coalesce(asignatura, ''))) = 'guardia' THEN 'guardia'
                    ELSE 'clase'
                END
                WHERE tipo IS NULL
                """
            )
            conn.commit()

    def _ensure_guardias_schema(self, conn):
        """Asegura que la tabla guardias contiene las columnas esperadas."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(guardias)")
        columnas = {row[1] for row in cursor.fetchall()}
        if "asignatura" not in columnas:
            cursor.execute("ALTER TABLE guardias ADD COLUMN asignatura TEXT")
        if "id_profesor_ausente" not in columnas:
            cursor.execute("ALTER TABLE guardias ADD COLUMN id_profesor_ausente INTEGER")
        if "id_profesor_cubre" not in columnas:
            cursor.execute("ALTER TABLE guardias ADD COLUMN id_profesor_cubre INTEGER")
        if "profesor_asignado" in columnas:
            cursor.execute(
                """
                UPDATE guardias
                SET id_profesor_cubre = COALESCE(id_profesor_cubre, profesor_asignado)
                WHERE profesor_asignado IS NOT NULL
                """
            )
        conn.commit()

    def _ensure_schema(self, conn):
        self._ensure_profesores_schema(conn)
        self._ensure_horarios_schema(conn)
        self._ensure_guardias_schema(conn)

    # ==================== PROFESORES ====================

    def get_profesores(self):
        """Obtiene todos los profesores activos."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, nombre, departamento, rfid, huella_id, face_id, activo, guardias_acumuladas, guardias_semana
            FROM profesores WHERE activo = 1
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [Profesor(*row) for row in rows]

    def get_profesor_by_id(self, profesor_id):
        """Obtiene un profesor por ID."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, nombre, departamento, rfid, huella_id, face_id, activo, guardias_acumuladas, guardias_semana
            FROM profesores WHERE id = ?
            """,
            (profesor_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return Profesor(*row) if row else None

    def insert_profesor(self, profesor):
        """Inserta un nuevo profesor."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO profesores (nombre, departamento, rfid, huella_id, face_id, activo, guardias_acumuladas, guardias_semana)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (profesor.nombre, profesor.departamento, profesor.rfid, profesor.huella_id, profesor.face_id, profesor.activo, profesor.guardias_acumuladas, profesor.guardias_semana))
        profesor.id = cursor.lastrowid
        conn.commit()
        conn.close()
        return profesor

    def update_profesor(self, profesor):
        """Actualiza un profesor."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE profesores SET nombre=?, departamento=?, rfid=?, huella_id=?, face_id=?, activo=?, guardias_acumuladas=?, guardias_semana=?
            WHERE id=?
        """, (profesor.nombre, profesor.departamento, profesor.rfid, profesor.huella_id, profesor.face_id, profesor.activo, profesor.guardias_acumuladas, profesor.guardias_semana, profesor.id))
        conn.commit()
        conn.close()

    def delete_profesor(self, profesor_id):
        """Elimina un profesor (desactiva)."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("UPDATE profesores SET activo=0 WHERE id=?", (profesor_id,))
        conn.commit()
        conn.close()

    # ==================== HORARIOS ====================

    def get_horarios_by_dia(self, dia):
        """Obtiene los horarios de un día."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT id, profesor_id, dia, hora, tipo, aula, asignatura FROM horarios WHERE dia = ?", (dia,))
        rows = cursor.fetchall()
        conn.close()
        return [Horario(*row) for row in rows]

    def insert_horario(self, horario):
        """Inserta un nuevo horario."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        tipo = horario.tipo or ("guardia" if horario.es_guardia() else "clase")
        cursor.execute("""
            INSERT INTO horarios (profesor_id, dia, hora, tipo, aula, asignatura)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (horario.profesor_id, horario.dia, horario.hora, tipo, horario.aula, horario.asignatura))
        horario.id = cursor.lastrowid
        horario.tipo = tipo
        conn.commit()
        conn.close()
        return horario

    # ==================== PRESENCIA ====================

    def get_presencia_hoy(self, profesor_id, fecha=None):
        """Obtiene el último registro de presencia del día para un profesor."""
        from datetime import datetime
        fecha = fecha or datetime.now().strftime("%Y-%m-%d")
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM presencia
            WHERE profesor_id = ? AND date(timestamp) = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (profesor_id, fecha))
        row = cursor.fetchone()
        conn.close()
        return Presencia(*row) if row else None

    def get_presencias_hoy(self, fecha=None):
        """Obtiene todos los registros de presencia del día."""
        from datetime import datetime
        fecha = fecha or datetime.now().strftime("%Y-%m-%d")
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM presencia
            WHERE date(timestamp) = ?
            ORDER BY profesor_id, timestamp
        """, (fecha,))
        rows = cursor.fetchall()
        conn.close()
        return [Presencia(*row) for row in rows]

    def insert_presencia(self, presencia):
        """Registra entrada o salida."""
        timestamp = presencia.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO presencia (profesor_id, timestamp, tipo)
            VALUES (?, ?, ?)
        """, (presencia.profesor_id, timestamp, presencia.tipo))
        presencia.id = cursor.lastrowid
        presencia.timestamp = timestamp
        conn.commit()
        conn.close()
        return presencia

    # ==================== AUSENCIAS ====================

    def get_ausencias_hoy(self, fecha=None):
        """Obtiene las ausencias del día."""
        from datetime import datetime
        fecha = fecha or datetime.now().strftime("%Y-%m-%d")
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ausencias WHERE dia = ?", (fecha,))
        rows = cursor.fetchall()
        conn.close()
        return [Ausencia(*row) for row in rows]

    def get_fechas_con_ausencias(self):
        """Devuelve las fechas con ausencias registradas, de más reciente a más antigua."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT dia FROM ausencias ORDER BY dia DESC")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def get_ultima_fecha_con_ausencias(self):
        """Devuelve la última fecha con ausencias registradas."""
        fechas = self.get_fechas_con_ausencias()
        return fechas[0] if fechas else None

    def get_ausencias_profesor_hoy(self, profesor_id, fecha=None):
        """Obtiene las ausencias activas de un profesor para el día indicado."""
        from datetime import datetime
        fecha = fecha or datetime.now().strftime("%Y-%m-%d")
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM ausencias WHERE profesor_id = ? AND dia = ? ORDER BY hora",
            (profesor_id, fecha),
        )
        rows = cursor.fetchall()
        conn.close()
        return [Ausencia(*row) for row in rows]

    def get_ausencia_profesor_hora(self, profesor_id, fecha, hora):
        """Obtiene la ausencia activa de un profesor para una hora concreta."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM ausencias WHERE profesor_id = ? AND dia = ? AND hora = ? LIMIT 1",
            (profesor_id, fecha, hora),
        )
        row = cursor.fetchone()
        conn.close()
        return Ausencia(*row) if row else None

    def insert_ausencia(self, ausencia):
        """Inserta una nueva ausencia."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ausencias (profesor_id, dia, hora, motivo)
            VALUES (?, ?, ?, ?)
        """, (ausencia.profesor_id, ausencia.dia, ausencia.hora, ausencia.motivo))
        ausencia.id = cursor.lastrowid
        conn.commit()
        conn.close()
        return ausencia

    def ensure_ausencia(self, ausencia):
        """Inserta una ausencia solo si todavía no existe para profesor, día y hora."""
        existente = self.get_ausencia_profesor_hora(ausencia.profesor_id, ausencia.dia, ausencia.hora)
        if existente is not None:
            return existente
        return self.insert_ausencia(ausencia)

    def delete_ausencias_profesor_hoy(self, profesor_id, fecha=None):
        """Elimina las ausencias activas de un profesor para el día indicado."""
        from datetime import datetime
        fecha = fecha or datetime.now().strftime("%Y-%m-%d")
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ausencias WHERE profesor_id = ? AND dia = ?", (profesor_id, fecha))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    # ==================== GUARDIAS ====================

    def get_guardias_by_dia(self, dia):
        """Obtiene las guardias de un día."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, dia, hora, aula, asignatura, id_profesor_ausente, id_profesor_cubre, cubierta
            FROM guardias WHERE dia = ?
            ORDER BY hora, aula, id
            """,
            (dia,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [Guardia(*row) for row in rows]

    def get_guardia_cubierta(self, dia, hora, aula, profesor_ausente_id=None):
        """Obtiene una guardia registrada para un tramo concreto."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        if profesor_ausente_id is None:
            cursor.execute(
                """
                SELECT id, dia, hora, aula, asignatura, id_profesor_ausente, id_profesor_cubre, cubierta
                FROM guardias
                WHERE dia = ? AND hora = ? AND aula = ? AND cubierta = 1
                ORDER BY id DESC
                LIMIT 1
                """,
                (dia, hora, aula),
            )
        else:
            cursor.execute(
                """
                SELECT id, dia, hora, aula, asignatura, id_profesor_ausente, id_profesor_cubre, cubierta
                FROM guardias
                WHERE dia = ? AND hora = ? AND aula = ? AND cubierta = 1 AND id_profesor_ausente = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (dia, hora, aula, profesor_ausente_id),
            )
        row = cursor.fetchone()
        conn.close()
        return Guardia(*row) if row else None

    def replace_guardias_calculadas(self, dia, guardias):
        """Sustituye las guardias calculadas no confirmadas de un día por el cálculo actual."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM guardias WHERE dia = ? AND cubierta = 0", (dia,))

        for guardia in guardias:
            cursor.execute(
                """
                SELECT id FROM guardias
                WHERE dia = ? AND hora = ? AND aula = ? AND cubierta = 1 AND id_profesor_ausente = ?
                LIMIT 1
                """,
                (guardia.dia, guardia.hora, guardia.aula, guardia.profesor_ausente_id),
            )
            if cursor.fetchone():
                continue

            cursor.execute(
                """
                INSERT INTO guardias (dia, hora, aula, asignatura, id_profesor_ausente, id_profesor_cubre, cubierta)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    guardia.dia,
                    guardia.hora,
                    guardia.aula,
                    guardia.asignatura,
                    guardia.profesor_ausente_id,
                    guardia.profesor_cubre_id,
                ),
            )

        conn.commit()
        conn.close()

    def insert_guardia(self, guardia):
        """Inserta una nueva guardia."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO guardias (dia, hora, aula, asignatura, id_profesor_ausente, id_profesor_cubre, cubierta)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (guardia.dia, guardia.hora, guardia.aula, guardia.asignatura, guardia.profesor_ausente_id, guardia.profesor_cubre_id, guardia.cubierta))
        guardia.id = cursor.lastrowid
        conn.commit()
        conn.close()
        return guardia

    def update_guardia_cubierta(self, guardia_id, cubierta=1):
        """Marca una guardia como cubierta."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("UPDATE guardias SET cubierta = ? WHERE id = ?", (cubierta, guardia_id))
        conn.commit()
        conn.close()

    def guardia_ya_registrada(self, dia, hora, aula, profesor_asignado=None, profesor_ausente_id=None):
        """Indica si una guardia ya fue registrada previamente."""
        guardia = self.get_guardia_cubierta(dia, hora, aula, profesor_ausente_id=profesor_ausente_id)
        if guardia is None:
            return False
        if profesor_asignado is None:
            return True
        return guardia.profesor_cubre_id == profesor_asignado

    def registrar_guardia_realizada(self, dia, hora, aula, profesor_asignado, asignatura=None, profesor_ausente_id=None):
        """Registra una guardia realizada y actualiza los contadores del profesor."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        parametros = [dia, hora, aula]
        filtro_ausente = ""
        if profesor_ausente_id is not None:
            filtro_ausente = " AND id_profesor_ausente = ?"
            parametros.append(profesor_ausente_id)

        cursor.execute(
            f"""
            SELECT id FROM guardias
            WHERE dia = ? AND hora = ? AND aula = ? AND cubierta = 1{filtro_ausente}
            LIMIT 1
            """,
            tuple(parametros),
        )
        if cursor.fetchone():
            conn.close()
            return False

        cursor.execute(
            f"""
            SELECT id FROM guardias
            WHERE dia = ? AND hora = ? AND aula = ? AND cubierta = 0{filtro_ausente}
            ORDER BY id DESC
            LIMIT 1
            """,
            tuple(parametros),
        )
        fila_calculada = cursor.fetchone()

        if fila_calculada:
            cursor.execute(
                """
                UPDATE guardias
                SET asignatura = ?, id_profesor_cubre = ?, cubierta = 1
                WHERE id = ?
                """,
                (asignatura, profesor_asignado, fila_calculada[0]),
            )
        else:
            cursor.execute(
                """
                INSERT INTO guardias (dia, hora, aula, asignatura, id_profesor_ausente, id_profesor_cubre, cubierta)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (dia, hora, aula, asignatura, profesor_ausente_id, profesor_asignado),
            )
        cursor.execute(
            """
            UPDATE profesores
            SET guardias_acumuladas = guardias_acumuladas + 1,
                guardias_semana = guardias_semana + 1
            WHERE id = ?
            """,
            (profesor_asignado,),
        )
        conn.commit()
        conn.close()
        return True

    def actualizar_guardias_profesor(self, profesor_id):
        """Incrementa los contadores de guardias para un profesor."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("UPDATE profesores SET guardias_acumuladas = guardias_acumuladas + 1, guardias_semana = guardias_semana + 1 WHERE id = ?", (profesor_id,))
        conn.commit()
        conn.close()

    def reset_guardias_semana(self):
        """Resetea el contador de guardias de la semana."""
        conn = self.get_connection()
        self._ensure_schema(conn)
        cursor = conn.cursor()
        cursor.execute("UPDATE profesores SET guardias_semana = 0")
        conn.commit()
        conn.close()