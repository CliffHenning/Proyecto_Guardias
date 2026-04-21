import sqlite3


def _migrar_profesores_a_huella(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(profesores)")
    columnas = [row[1] for row in cursor.fetchall()]
    if not columnas or ("rfid" not in columnas and "face_id" not in columnas):
        return

    cursor.execute("ALTER TABLE profesores RENAME TO profesores_legacy")
    cursor.execute(
        """
        CREATE TABLE profesores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            departamento TEXT,
            huella_id TEXT,
            activo INTEGER DEFAULT 1,
            guardias_acumuladas INTEGER DEFAULT 0,
            guardias_semana INTEGER DEFAULT 0
        )
        """
    )
    cursor.execute(
        """
        INSERT INTO profesores (id, nombre, departamento, huella_id, activo, guardias_acumuladas, guardias_semana)
        SELECT id, nombre, departamento, huella_id, activo, guardias_acumuladas, guardias_semana
        FROM profesores_legacy
        """
    )
    cursor.execute("DROP TABLE profesores_legacy")
    conn.commit()

def init_db():
    with open("modules/db/schema.sql", "r", encoding="utf-8") as f:
        schema = f.read()

    conn = sqlite3.connect("ies.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='profesores'"
    )
    if cursor.fetchone():
        _migrar_profesores_a_huella(conn)

    cursor.executescript(schema)

    conn.commit()
    conn.close()

    print("Base de datos creada correctamente.")

if __name__ == "__main__":
    init_db()