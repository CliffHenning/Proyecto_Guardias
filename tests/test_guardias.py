import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.db.models import Profesor, Horario, Presencia, Ausencia
from modules.guardias.models import Guardia, ProfesorDisponible
from modules.guardias.motor import MotorGuardias, obtener_dia_semana_es, obtener_hora_guardia_actual


def test_motor_guardias_integration_sugiere_profesor_para_la_guardia_calculada():
    motor = MotorGuardias(db_path=":memory:")

    profesores = [
        Profesor(id=1, nombre="RFID1", rfid="RFID1", activo=1, guardias_acumuladas=0, guardias_semana=0),
        Profesor(id=2, nombre="RFID2", rfid="RFID2", activo=1, guardias_acumuladas=0, guardias_semana=1),
    ]
    presencias = [Presencia(profesor_id=1, timestamp="2026-04-09 08:00:00", tipo="entrada")]
    ausencias = [Ausencia(profesor_id=99, dia="2026-04-09", hora=1, motivo="Enfermedad")]

    class StubManager:
        def __init__(self):
            self.guardias_reemplazadas = None

        def get_profesores(self):
            return profesores

        def get_presencias_hoy(self, dia=None):
            return presencias

        def get_ausencias_hoy(self, dia=None):
            return ausencias

        def get_horarios_by_dia(self, dia):
            return [
                Horario(profesor_id=99, dia=dia, hora=1, aula="A101", asignatura="Matemáticas"),
                Horario(profesor_id=1, dia=dia, hora=1, aula="Guardia", asignatura="Guardia"),
            ]

        def replace_guardias_calculadas(self, dia, guardias):
            self.guardias_reemplazadas = (dia, guardias)

    motor.db_manager = StubManager()

    resultado = motor.calcular_guardias(dia="2026-04-09")

    assert isinstance(resultado, dict)
    assert len(resultado["guardias"]) == 1
    guardia_asignada = resultado["guardias"][0]
    assert guardia_asignada.aula == "A101"
    assert guardia_asignada.profesor_asignado == 1
    assert motor.db_manager.guardias_reemplazadas[0] == "2026-04-09"

    ranking_ids = [item.profesor.id for item in resultado["ranking_profesores"]]
    assert ranking_ids == [1]
    assert ranking_ids[0] == 1


def test_motor_guardias_no_reutiliza_el_mismo_profesor_en_dos_ausencias_simultaneas():
    motor = MotorGuardias(db_path=":memory:")

    profesores = [
        Profesor(id=3, nombre="Profesor Guardia 1", activo=1, guardias_acumuladas=0, guardias_semana=0),
        Profesor(id=4, nombre="Profesor Guardia 2", activo=1, guardias_acumuladas=1, guardias_semana=0),
    ]
    presencias = [
        Presencia(profesor_id=3, timestamp="2026-04-09 08:00:00", tipo="entrada"),
        Presencia(profesor_id=4, timestamp="2026-04-09 08:00:00", tipo="entrada"),
    ]
    ausencias = [
        Ausencia(profesor_id=11, dia="2026-04-09", hora=1, motivo="Enfermedad"),
        Ausencia(profesor_id=12, dia="2026-04-09", hora=1, motivo="Enfermedad"),
    ]

    class StubManager:
        def __init__(self):
            self.guardias_reemplazadas = None

        def get_profesores(self):
            return profesores

        def get_presencias_hoy(self, dia=None):
            return presencias

        def get_ausencias_hoy(self, dia=None):
            return ausencias

        def get_horarios_by_dia(self, dia):
            return [
                Horario(profesor_id=11, dia=dia, hora=1, aula="A101", asignatura="Matemáticas"),
                Horario(profesor_id=12, dia=dia, hora=1, aula="A102", asignatura="Lengua"),
                Horario(profesor_id=3, dia=dia, hora=1, aula="Guardia", asignatura="Guardia"),
                Horario(profesor_id=4, dia=dia, hora=1, aula="Guardia", asignatura="Guardia"),
            ]

        def replace_guardias_calculadas(self, dia, guardias):
            self.guardias_reemplazadas = (dia, guardias)

    motor.db_manager = StubManager()

    resultado = motor.calcular_guardias(dia="2026-04-09")

    asignados = [guardia.profesor_asignado for guardia in resultado["guardias"]]

    assert asignados == [3, 4]
    assert motor.db_manager.guardias_reemplazadas[0] == "2026-04-09"


def test_obtener_dia_semana_es_no_depende_del_locale():
    fecha = datetime.strptime("2026-04-16", "%Y-%m-%d")

    assert obtener_dia_semana_es(fecha) == "Jueves"


def test_obtener_hora_guardia_actual_aplica_margen_de_tolerancia():
    antes = datetime.strptime("2026-04-15 08:54:00", "%Y-%m-%d %H:%M:%S")
    despues = datetime.strptime("2026-04-15 08:55:00", "%Y-%m-%d %H:%M:%S")

    assert obtener_hora_guardia_actual(antes, margen_minutos=10) is None
    assert obtener_hora_guardia_actual(despues, margen_minutos=10) == 1


def test_motor_detecta_ausencias_automaticas_del_tramo_actual():
    class StubManager:
        def __init__(self):
            self.ausencias = {}

        def get_horarios_by_dia(self, dia):
            return [
                Horario(profesor_id=10, dia=dia, hora=1, aula="A101", asignatura="Matemáticas"),
                Horario(profesor_id=20, dia=dia, hora=1, aula="Guardia", asignatura="Guardia"),
                Horario(profesor_id=30, dia=dia, hora=1, aula="B201", asignatura="Lengua"),
            ]

        def get_presencias_hoy(self, fecha=None):
            return [Presencia(profesor_id=30, timestamp=f"{fecha} 08:00:00", tipo="entrada")]

        def ensure_ausencia(self, ausencia):
            clave = (ausencia.profesor_id, ausencia.dia, ausencia.hora)
            self.ausencias.setdefault(clave, ausencia)
            return self.ausencias[clave]

    momento = datetime.strptime("2026-04-15 08:56:00", "%Y-%m-%d %H:%M:%S")
    motor = MotorGuardias(db_path=":memory:")
    motor.db_manager = StubManager()

    ausencias = motor.detectar_ausencias_automaticas(ahora=momento, margen_minutos=10)

    assert len(ausencias) == 1
    assert ausencias[0].profesor_id == 10
    assert ausencias[0].hora == 1
    assert ausencias[0].motivo == "Ausencia detectada automáticamente"


def test_motor_ignora_ausencias_sobre_tramos_de_guardia():
    motor = MotorGuardias(db_path=":memory:")

    profesores = [
        Profesor(id=1, nombre="Profesor Guardia", activo=1, guardias_acumuladas=0, guardias_semana=0),
        Profesor(id=2, nombre="Profesor Cobertura", activo=1, guardias_acumuladas=0, guardias_semana=0),
    ]
    presencias = [Presencia(profesor_id=2, timestamp="2026-04-16 08:00:00", tipo="entrada")]
    ausencias = [Ausencia(profesor_id=1, dia="2026-04-16", hora=1, motivo="Sin fichaje")]

    class StubManager:
        def get_profesores(self):
            return profesores

        def get_presencias_hoy(self, dia=None):
            return presencias

        def get_ausencias_hoy(self, dia=None):
            return ausencias

        def get_horarios_by_dia(self, dia):
            return [
                Horario(profesor_id=1, dia=dia, hora=1, aula="Guardia", asignatura="Guardia"),
                Horario(profesor_id=2, dia=dia, hora=1, aula="Guardia", asignatura="Guardia"),
            ]

    motor.db_manager = StubManager()

    resultado = motor.calcular_guardias(dia="2026-04-16")

    assert resultado["guardias"] == []


# --- Pruebas de modelos de dominio (1.1.5.4) ---

def test_guardia_atributos_iniciales_correctos():
    """Un objeto Guardia recién creado tiene los atributos esperados."""
    guardia = Guardia(dia="Lunes", hora=2, aula="Aula 101", profesor_ausente_id=5, asignatura="Matemáticas")

    assert guardia.dia == "Lunes"
    assert guardia.hora == 2
    assert guardia.aula == "Aula 101"
    assert guardia.profesor_ausente_id == 5
    assert guardia.asignatura == "Matemáticas"
    assert guardia.profesor_asignado is None
    assert guardia.prioridad == 0


def test_guardia_no_cubierta_inicialmente():
    """Una guardia recién creada no está cubierta."""
    guardia = Guardia(dia="Martes", hora=3, aula="Aula 202")

    assert not guardia.esta_cubierta()


def test_guardia_cubierta_tras_asignar_profesor():
    """Tras asignar un profesor, la guardia queda cubierta."""
    guardia = Guardia(dia="Miércoles", hora=1, aula="Aula 303")

    guardia.asignar_profesor(7)

    assert guardia.esta_cubierta()
    assert guardia.profesor_asignado == 7


def test_guardia_sin_profesor_ausente_es_valida():
    """Una guardia puede crearse sin especificar profesor ausente."""
    guardia = Guardia(dia="Jueves", hora=4, aula="Aula 104")

    assert guardia.profesor_ausente_id is None
    assert guardia.asignatura is None
    assert not guardia.esta_cubierta()


def test_profesor_disponible_atributos_iniciales():
    """ProfesorDisponible almacena correctamente el profesor y la hora."""
    profesor = Profesor(id=1, nombre="Ana García", activo=1, guardias_acumuladas=3, guardias_semana=1)
    disponible = ProfesorDisponible(profesor, hora_disponible=4)

    assert disponible.hora_disponible == 4
    assert disponible.profesor is profesor


def test_profesor_disponible_puntuacion_prioridad_calculada_al_crear():
    """La puntuación de prioridad se calcula correctamente en la construcción."""
    profesor = Profesor(id=1, nombre="Ana García", activo=1, guardias_acumuladas=3, guardias_semana=2)
    disponible = ProfesorDisponible(profesor, hora_disponible=4)

    assert disponible.puntuacion_prioridad == (3, 2, 0)


def test_profesor_disponible_puede_hacer_guardia_hora_correcta():
    """Un profesor activo puede hacer guardia en su hora disponible."""
    profesor = Profesor(id=1, nombre="Ana García", activo=1)
    disponible = ProfesorDisponible(profesor, hora_disponible=2)

    assert disponible.puede_hacer_guardia(2)


def test_profesor_disponible_no_puede_hacer_guardia_hora_incorrecta():
    """Un profesor activo no puede hacer guardia en una hora distinta a la suya."""
    profesor = Profesor(id=1, nombre="Ana García", activo=1)
    disponible = ProfesorDisponible(profesor, hora_disponible=2)

    assert not disponible.puede_hacer_guardia(5)


def test_profesor_disponible_inactivo_no_puede_hacer_guardia_en_su_hora():
    """Un profesor inactivo no puede hacer guardia aunque la hora coincida."""
    profesor = Profesor(id=2, nombre="Luis Pérez", activo=0)
    disponible = ProfesorDisponible(profesor, hora_disponible=2)

    assert not disponible.puede_hacer_guardia(2)


def test_profesor_disponible_incrementar_contadores_actualiza_semana_y_acumuladas():
    """incrementar_contadores_guardia incrementa en 1 ambos contadores."""
    profesor = Profesor(id=1, nombre="Ana García", activo=1, guardias_acumuladas=2, guardias_semana=1)
    disponible = ProfesorDisponible(profesor, hora_disponible=1)

    disponible.incrementar_contadores_guardia()

    assert disponible.profesor.guardias_semana == 2
    assert disponible.profesor.guardias_acumuladas == 3


def test_profesor_disponible_compatible_con_sorted_para_motor():
    """ProfesorDisponible admite ordenación con sorted(), compatible con el motor de guardias."""
    pA = ProfesorDisponible(
        Profesor(id=1, nombre="A", activo=1, guardias_acumuladas=2, guardias_semana=2),
        hora_disponible=1
    )
    pB = ProfesorDisponible(
        Profesor(id=2, nombre="B", activo=1, guardias_acumuladas=0, guardias_semana=0),
        hora_disponible=1
    )

    resultado = sorted([pA, pB])

    assert resultado[0].profesor.id == 2


def test_guardia_compatible_con_profesor_disponible_asignado():
    """Un objeto Guardia acepta el id del profesor devuelto por ProfesorDisponible."""
    profesor = Profesor(id=10, nombre="Carlos Ruiz", activo=1)
    disponible = ProfesorDisponible(profesor, hora_disponible=3)
    guardia = Guardia(dia="Viernes", hora=3, aula="Aula 501")

    guardia.asignar_profesor(disponible.profesor.id)

    assert guardia.profesor_asignado == 10
    assert guardia.esta_cubierta()
