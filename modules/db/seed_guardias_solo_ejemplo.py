"""Inserta GUARDIAS de ejemplo directamente en la tabla `guardias`.

Esto está pensado para debug rápido:
- NO crea profesores
- NO crea horarios
- NO crea ausencias

Solo inserta filas con valores de ejemplo en `guardias`.

Uso:
  python modules/db/seed_guardias_solo_ejemplo.py --db ies.db --dia 2026-04-15

Si ya existen guardias para ese `dia`, se reemplazan (se borran primero las del día).
"""

from __future__ import annotations

import argparse
import os
import sys
import sqlite3
from datetime import datetime


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def _parse_fecha(dia: str) -> str:
    # Valida formato YYYY-MM-DD
    datetime.strptime(dia, "%Y-%m-%d")
    return dia


def seed_guardias(db_path: str, dia: str) -> int:
    dia = _parse_fecha(dia)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        # Borramos guardias del día para que el seed sea idempotente
        cur.execute("DELETE FROM guardias WHERE dia = ?", (dia,))

        # Ejemplo: 3 guardias en el mismo aula/hora
        # Nota: `id_profesor_ausente` e `id_profesor_cubre` apuntan a IDs existentes.
        # Si no existen en tu BD, SQLite puede fallar por FK (depende del esquema).
        # Si eso pasa, debes ajustar IDs para que apunten a profesores reales.
        ejemplos = [
            (dia, 1, "A101", "Matemáticas", 1, 2, 0),
            (dia, 2, "A101", "Lengua", 1, 3, 0),
            (dia, 3, "B202", "Historia", 4, 2, 1),
        ]

        cur.executemany(
            """
            INSERT INTO guardias (dia, hora, aula, asignatura, id_profesor_ausente, id_profesor_cubre, cubierta)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ejemplos,
        )

        conn.commit()
        # Devuelve cuántas guardias quedan para ese día
        cur.execute("SELECT COUNT(*) FROM guardias WHERE dia = ?", (dia,))
        return int(cur.fetchone()[0])
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", dest="db_path", default="ies.db")
    parser.add_argument("--dia", dest="dia", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    n = seed_guardias(args.db_path, args.dia)
    print(f"[seed_guardias_solo_ejemplo] OK. Guardias insertadas para {args.dia}: {n}")


if __name__ == "__main__":
    main()

