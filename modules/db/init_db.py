import sqlite3

def init_db():
    with open("modules/db/schema.sql", "r") as f:
        schema = f.read()

    conn = sqlite3.connect("ies.db")
    cursor = conn.cursor()

    cursor.executescript(schema)

    conn.commit()
    conn.close()

    print("Base de datos creada correctamente.")

if __name__ == "__main__":
    init_db()