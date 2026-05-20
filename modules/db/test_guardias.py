import sqlite3
from collections import defaultdict

conn = sqlite3.connect("ies.db")
cursor = conn.cursor()

FECHAS = {
    "Lunes": "2026-05-18",
    "Martes": "2026-05-19",
    "Miércoles": "2026-05-20",
    "Jueves": "2026-05-21",
    "Viernes": "2026-05-22",
}

AUSENCIAS_POR_DIA = {
    "Lunes": 2,
    "Martes": 1,
    "Miércoles": 3,
    "Jueves": 2,
    "Viernes": 1,
}

# =====================================================
# HORAS DONDE HAY PROFESORES DE GUARDIA
# =====================================================

cursor.execute("""
SELECT dia, hora
FROM horarios
WHERE tipo = 'guardia'
""")

guardias_disponibles = defaultdict(set)

for dia, hora in cursor.fetchall():
    guardias_disponibles[dia].add(hora)

# =====================================================
# GENERAR AUSENCIAS REALES
# =====================================================

for dia_semana, cantidad in AUSENCIAS_POR_DIA.items():

    fecha_real = FECHAS[dia_semana]

    print(f"\n===== {dia_semana} =====")

    cursor.execute("""
    SELECT
        profesor_id,
        hora,
        aula,
        asignatura
    FROM horarios
    WHERE dia = ?
    AND tipo = 'clase'
    """, (dia_semana,))

    horarios = cursor.fetchall()

    candidatos_validos = []

    for profesor_id, hora, aula, asignatura in horarios:

        # solo horas donde existe guardia
        if hora in guardias_disponibles[dia_semana]:

            candidatos_validos.append(
                (
                    profesor_id,
                    hora,
                    aula,
                    asignatura
                )
            )

    usados = set()
    insertados = 0

    for profesor_id, hora, aula, asignatura in candidatos_validos:

        if insertados >= cantidad:
            break

        clave = (profesor_id, hora)

        if clave in usados:
            continue

        usados.add(clave)

        # =========================
        # INSERT AUSENCIA
        # =========================

        cursor.execute("""
        INSERT INTO ausencias (
            profesor_id,
            dia,
            hora,
            motivo
        )
        VALUES (?, ?, ?, ?)
        """, (
            profesor_id,
            fecha_real,
            hora,
            f'Ausencia automática de prueba ({dia_semana})'
        ))

        # =========================
        # INSERT GUARDIA
        # =========================

        cursor.execute("""
        INSERT INTO guardias (
            dia,
            hora,
            aula,
            asignatura,
            id_profesor_ausente,
            id_profesor_cubre,
            cubierta
        )
        VALUES (?, ?, ?, ?, ?, NULL, 0)
        """, (
            fecha_real,
            hora,
            aula,
            asignatura,
            profesor_id
        ))

        print(
            f"Profesor {profesor_id} ausente "
            f"hora {hora} -> {asignatura}"
        )

        insertados += 1

conn.commit()

print("\nGuardias y ausencias generadas correctamente")

conn.close()