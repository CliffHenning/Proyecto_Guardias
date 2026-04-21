import sqlite3
from contextlib import contextmanager
from datetime import datetime

from modules.db.models import Profesor, Horario, Presencia, Ausencia, Guardia


class DBManager:
    def __init__(self, db_path="ies.db"):
        self.db_path = db_path

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    @contextmanager
    def _connection(self):
        conn = self.get_connection()
        try:
            self._ensure_schema(conn)
            yield conn
        finally:
            conn.close()

    def _fetch_all(self, query, params=(), model_cls=None):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
        if model_cls is None:
            return rows
        return [model_cls(*row) for row in rows]

    def _fetch_one(self, query, params=(), model_cls=None):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
        if row is None or model_cls is None:
            return row
        return model_cls(*row)

    def _insert(self, query, params=()):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            lastrowid = cursor.lastrowid
            conn.commit()
        return lastrowid

    def _execute_write(self, query, params=()):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rowcount = cursor.rowcount
            conn.commit()
        return rowcount

    def _fecha_hoy(self, fecha=None):
        return fecha or datetime.now().strftime("%Y-%m-%d")

    def _timestamp_actual(self, timestamp=None):
        return timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _ensure_profesores_schema(self, conn):
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(profesores)")
        columnas = {row[1] for row in cursor.fetchall()}
        schema_actualizado = False
        if "departamento" not in columnas:
            cursor.execute("ALTER TABLE profesores ADD COLUMN departamento TEXT")
            schema_actualizado = True
        if "huella_id" not in columnas:
            cursor.execute("ALTER TABLE profesores ADD COLUMN huella_id TEXT")
            schema_actualizado = True
        if schema_actualizado:
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
        return self._fetch_all(
            """
            SELECT id, nombre, departamento, huella_id, activo, guardias_acumuladas, guardias_semana
            FROM profesores WHERE activo = 1
            """,
            model_cls=Profesor,
        )

    def get_profesor_by_id(self, profesor_id):
        """Obtiene un profesor por ID."""
        return self._fetch_one(
            """
            SELECT id, nombre, departamento, huella_id, activo, guardias_acumuladas, guardias_semana
            FROM profesores WHERE id = ?
            """,
            (profesor_id,),
            model_cls=Profesor,
        )

    def insert_profesor(self, profesor):
        """Inserta un nuevo profesor."""
        profesor.id = self._insert("""
            INSERT INTO profesores (nombre, departamento, huella_id, activo, guardias_acumuladas, guardias_semana)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (profesor.nombre, profesor.departamento, profesor.huella_id, profesor.activo, profesor.guardias_acumuladas, profesor.guardias_semana))
        return profesor

    def update_profesor(self, profesor):
        """Actualiza un profesor."""
        self._execute_write("""
            UPDATE profesores SET nombre=?, departamento=?, huella_id=?, activo=?, guardias_acumuladas=?, guardias_semana=?
            WHERE id=?
        """, (profesor.nombre, profesor.departamento, profesor.huella_id, profesor.activo, profesor.guardias_acumuladas, profesor.guardias_semana, profesor.id))

    def delete_profesor(self, profesor_id):
        """Elimina un profesor (desactiva)."""
        self._execute_write("UPDATE profesores SET activo=0 WHERE id=?", (profesor_id,))

    # ==================== HORARIOS ====================

    def get_horarios_by_dia(self, dia):
        """Obtiene los horarios de un día."""
        return self._fetch_all(
            "SELECT id, profesor_id, dia, hora, tipo, aula, asignatura FROM horarios WHERE dia = ?",
            (dia,),
            model_cls=Horario,
        )

    def insert_horario(self, horario):
        """Inserta un nuevo horario."""
        tipo = horario.tipo or ("guardia" if horario.es_guardia() else "clase")
        horario.id = self._insert("""
            INSERT INTO horarios (profesor_id, dia, hora, tipo, aula, asignatura)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (horario.profesor_id, horario.dia, horario.hora, tipo, horario.aula, horario.asignatura))
        horario.tipo = tipo
        return horario

    # ==================== PRESENCIA ====================

    def get_presencia_hoy(self, profesor_id, fecha=None):
        """Obtiene el último registro de presencia del día para un profesor."""
        fecha = self._fecha_hoy(fecha)
        return self._fetch_one("""
            SELECT * FROM presencia
            WHERE profesor_id = ? AND date(timestamp) = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (profesor_id, fecha), model_cls=Presencia)

    def get_presencias_hoy(self, fecha=None):
        """Obtiene todos los registros de presencia del día."""
        fecha = self._fecha_hoy(fecha)
        return self._fetch_all("""
            SELECT * FROM presencia
            WHERE date(timestamp) = ?
            ORDER BY profesor_id, timestamp
        """, (fecha,), model_cls=Presencia)

    def insert_presencia(self, presencia):
        """Registra entrada o salida."""
        timestamp = self._timestamp_actual(presencia.timestamp)
        presencia.id = self._insert("""
            INSERT INTO presencia (profesor_id, timestamp, tipo)
            VALUES (?, ?, ?)
        """, (presencia.profesor_id, timestamp, presencia.tipo))
        presencia.timestamp = timestamp
        return presencia

    # ==================== AUSENCIAS ====================

    def get_ausencias_hoy(self, fecha=None):
        """Obtiene las ausencias del día."""
        fecha = self._fecha_hoy(fecha)
        return self._fetch_all("SELECT * FROM ausencias WHERE dia = ?", (fecha,), model_cls=Ausencia)

    def get_fechas_con_ausencias(self):
        """Devuelve las fechas con ausencias registradas, de más reciente a más antigua."""
        rows = self._fetch_all("SELECT DISTINCT dia FROM ausencias ORDER BY dia DESC")
        return [row[0] for row in rows]

    def get_ausencias_profesor_hoy(self, profesor_id, fecha=None):
        """Obtiene las ausencias activas de un profesor para el día indicado."""
        fecha = self._fecha_hoy(fecha)
        return self._fetch_all(
            "SELECT * FROM ausencias WHERE profesor_id = ? AND dia = ? ORDER BY hora",
            (profesor_id, fecha),
            model_cls=Ausencia,
        )

    def get_ausencia_profesor_hora(self, profesor_id, fecha, hora):
        """Obtiene la ausencia activa de un profesor para una hora concreta."""
        return self._fetch_one(
            "SELECT * FROM ausencias WHERE profesor_id = ? AND dia = ? AND hora = ? LIMIT 1",
            (profesor_id, fecha, hora),
            model_cls=Ausencia,
        )

    def insert_ausencia(self, ausencia):
        """Inserta una nueva ausencia."""
        ausencia.id = self._insert("""
            INSERT INTO ausencias (profesor_id, dia, hora, motivo)
            VALUES (?, ?, ?, ?)
        """, (ausencia.profesor_id, ausencia.dia, ausencia.hora, ausencia.motivo))
        return ausencia

    def ensure_ausencia(self, ausencia):
        """Inserta una ausencia solo si todavía no existe para profesor, día y hora."""
        existente = self.get_ausencia_profesor_hora(ausencia.profesor_id, ausencia.dia, ausencia.hora)
        if existente is not None:
            return existente
        return self.insert_ausencia(ausencia)

    def delete_ausencias_profesor_hoy(self, profesor_id, fecha=None):
        """Elimina las ausencias activas de un profesor para el día indicado."""
        fecha = self._fecha_hoy(fecha)
        return self._execute_write("DELETE FROM ausencias WHERE profesor_id = ? AND dia = ?", (profesor_id, fecha))

    # ==================== GUARDIAS ====================

    def get_guardias_by_dia(self, dia):
        """Obtiene las guardias de un día."""
        return self._fetch_all(
            """
            SELECT id, dia, hora, aula, asignatura, id_profesor_ausente, id_profesor_cubre, cubierta
            FROM guardias WHERE dia = ?
            ORDER BY hora, aula, id
            """,
            (dia,),
            model_cls=Guardia,
        )

    def get_guardia_cubierta(self, dia, hora, aula, profesor_ausente_id=None):
        """Obtiene una guardia registrada para un tramo concreto."""
        if profesor_ausente_id is None:
            return self._fetch_one(
                """
                SELECT id, dia, hora, aula, asignatura, id_profesor_ausente, id_profesor_cubre, cubierta
                FROM guardias
                WHERE dia = ? AND hora = ? AND aula = ? AND cubierta = 1
                ORDER BY id DESC
                LIMIT 1
                """,
                (dia, hora, aula),
                model_cls=Guardia,
            )
        return self._fetch_one(
            """
            SELECT id, dia, hora, aula, asignatura, id_profesor_ausente, id_profesor_cubre, cubierta
            FROM guardias
            WHERE dia = ? AND hora = ? AND aula = ? AND cubierta = 1 AND id_profesor_ausente = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (dia, hora, aula, profesor_ausente_id),
            model_cls=Guardia,
        )

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
        guardia.id = self._insert("""
            INSERT INTO guardias (dia, hora, aula, asignatura, id_profesor_ausente, id_profesor_cubre, cubierta)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (guardia.dia, guardia.hora, guardia.aula, guardia.asignatura, guardia.profesor_ausente_id, guardia.profesor_cubre_id, guardia.cubierta))
        return guardia

    def update_guardia_cubierta(self, guardia_id, cubierta=1):
        """Marca una guardia como cubierta."""
        self._execute_write("UPDATE guardias SET cubierta = ? WHERE id = ?", (cubierta, guardia_id))

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

    def reset_guardias_semana(self):
        """Resetea el contador de guardias de la semana."""
        self._execute_write("UPDATE profesores SET guardias_semana = 0")