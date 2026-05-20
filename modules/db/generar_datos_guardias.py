"""Script local de generación de datos de prueba para guardias.

Este fichero se conserva en el repo como utilidad local.

IMPORTANTE: NO debe llamarse test_*.py si se quiere evitar que pytest lo
interprete como suite de tests. Si quieres ejecutar pytest, elimínalo o
renómbralo.
"""

import sqlite3
from collections import defaultdict


def main(db_path: str = "ies.db") -> None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    fechas = {
        "Lunes": "2026-05-18",
        "Martes": "2026-05-19",
        "Miércoles": "2026-05-20",
        "Jueves": "2026-05-21",
        "Viernes": "2026-05-22",
    }

    ausencias_por_dia = {
        "Lunes": 2,
        "Martes": 1,
        "Miércoles": 3,
        "Jueves": 2,
        "Viernes": 1,
    }

    # Horas donde hay profesores de guardia
    cursor.execute(
        """
        SELECT dia, hora
        FROM horarios
        WHERE tipo = 'guardia'
        """
    )
    guardias_disponibles: dict[str, set[int]] = defaultdict(set)
    for dia, hora in cursor.fetchall():
        guardias_disponibles[dia].add(int(hora))

    # Generar ausencias y guardias de prueba
    for dia_semana, cantidad in ausencias_por_dia.items():
        fecha_real = fechas[dia_semana]
        print(f"\n===== {dia_semana} =====")

        cursor.execute(
            """
            SELECT profesor_id, hora, aula, asignatura
            FROM horarios
            WHERE dia = ? AND tipo = 'clase'
            """,
            (dia_semana,),
        )
        horarios = cursor.fetchall()

        candidatos_validos = [
            (profesor_id, int(hora), aula, asignatura)
            for profesor_id, hora, aula, asignatura in horarios
            if int(hora) in guardias_disponibles[dia_semana]
        ]

        usados: set[tuple[int, int]] = set()
        insertados = 0

        for profesor_id, hora, aula, asignatura in candidatos_validos:
            if insertados >= cantidad:
                break

            clave = (int(profesor_id), int(hora))
            if clave in usados:
                continue
            usados.add(clave)

            cursor.execute(
                """
                INSERT INTO ausencias (profesor_id, dia, hora, motivo)
                VALUES (?, ?, ?, ?)
                """,
                (
                    profesor_id,
                    fecha_real,
                    hora,
                    f"Ausencia automática de prueba ({dia_semana})",
                ),
            )

            cursor.execute(
                """
                INSERT INTO guardias (
                    dia, hora, aula, asignatura,
                    id_profesor_ausente, id_profesor_cubre, cubierta
                )
                VALUES (?, ?, ?, ?, ?, NULL, 0)
                """,
                (
                    fecha_real,
                    hora,
                    aula,
                    asignatura,
                    profesor_id,
                ),
            )

            print(f"Profesor {profesor_id} ausente hora {hora} -> {asignatura}")
            insertados += 1

    conn.commit()
    conn.close()
    print("\nGuardias y ausencias generadas correctamente")


if __name__ == "__main__":
    main()

