import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.db.models import Profesor, Horario, Presencia, Ausencia
from modules.guardias.models import Guardia, ProfesorDisponible
from modules.guardias.reglas import determinar_profesores_disponibles, calcular_ranking_profesores, asignar_guardias
from modules.guardias.motor import MotorGuardias


class StubDbManager:
    def __init__(self, horarios_by_dia=None):
        self.horarios_by_dia = horarios_by_dia or {}

    # Retorna horarios simulados por día

    def get_horarios_by_dia(self, dia):
        return self.horarios_by_dia.get(dia, [])


def test_determinar_profesores_disponibles_calcula_carga_lectiva_y_devuelve_disponible():
    profesor = Profesor(id=1, nombre="RFID Profesor", rfid="ABC123", activo=1, guardias_acumuladas=0, guardias_semana=0)
    presencias = [Presencia(profesor_id=1, timestamp="2026-04-09 08:00:00", tipo="entrada")]
    ausencias = []

    horarios = [Horario(profesor_id=1, dia="Lunes", hora=1, aula="A101", asignatura="Matemáticas")]
    db_manager = StubDbManager(horarios_by_dia={"Lunes": horarios, "Martes": [], "Miércoles": [], "Jueves": [], "Viernes": []})

    disponibles = determinar_profesores_disponibles([profesor], presencias, ausencias, 1, db_manager)

    assert len(disponibles) == 1
    disponible = disponibles[0]
    assert disponible.profesor.id == 1
    assert disponible.hora_disponible == 1
    assert disponible.profesor.carga_lectiva == 1
    assert disponible.profesor.rfid == "ABC123"


def test_profesor_disponible_puede_hacer_guardia_y_activo():
    profesor = Profesor(id=10, nombre="Profesor Disponible", activo=1, guardias_acumuladas=0, guardias_semana=0)
    disponible = ProfesorDisponible(profesor, hora_disponible=2)

    assert disponible.puede_hacer_guardia(2)
    assert not disponible.puede_hacer_guardia(1)


def test_profesor_disponible_inactivo_no_puede_hacer_guardia():
    profesor = Profesor(id=11, nombre="Profesor Inactivo", activo=0, guardias_acumuladas=0, guardias_semana=0)
    disponible = ProfesorDisponible(profesor, hora_disponible=2)

    assert not disponible.puede_hacer_guardia(2)


def test_calcular_ranking_profesores_resuelve_empate_por_carga_lectiva():
    profesor1 = Profesor(id=1, nombre="Profesor A", guardias_acumuladas=0, guardias_semana=0)
    profesor2 = Profesor(id=2, nombre="Profesor B", guardias_acumuladas=0, guardias_semana=0)
    profesor1.carga_lectiva = 3
    profesor2.carga_lectiva = 1

    disp1 = ProfesorDisponible(profesor1, hora_disponible=1)
    disp2 = ProfesorDisponible(profesor2, hora_disponible=1)

    ranking = calcular_ranking_profesores([disp1, disp2])

    assert [item.profesor.id for item in ranking] == [2, 1]


def test_asignar_guardias_solo_asigna_quien_esta_disponible_para_la_hora():
    guardia = Guardia(dia="Lunes", hora=2, aula="A101", profesor_ausente_id=99)

    prof1 = Profesor(id=1, nombre="Profesor A", activo=1, guardias_acumuladas=0, guardias_semana=0)
    prof2 = Profesor(id=2, nombre="Profesor B", activo=1, guardias_acumuladas=0, guardias_semana=0)

    disp1 = ProfesorDisponible(prof1, hora_disponible=1)
    disp2 = ProfesorDisponible(prof2, hora_disponible=2)

    result_guardias = asignar_guardias([guardia], [disp1, disp2])

    assert result_guardias[0].profesor_asignado == 2
    assert prof1.guardias_semana == 0
    assert prof1.guardias_acumuladas == 0
    assert prof2.guardias_semana == 1
    assert prof2.guardias_acumuladas == 1


def test_calcular_ranking_profesores_orden_correcto():
    profesor1 = Profesor(id=1, nombre="Profesor A", guardias_acumuladas=0, guardias_semana=1)
    profesor2 = Profesor(id=2, nombre="Profesor B", guardias_acumuladas=1, guardias_semana=0)
    profesor3 = Profesor(id=3, nombre="Profesor C", guardias_acumuladas=0, guardias_semana=0)

    profesor1.carga_lectiva = 3
    profesor2.carga_lectiva = 2
    profesor3.carga_lectiva = 5

    disp1 = ProfesorDisponible(profesor1, hora_disponible=1)
    disp2 = ProfesorDisponible(profesor2, hora_disponible=1)
    disp3 = ProfesorDisponible(profesor3, hora_disponible=1)

    ranking = calcular_ranking_profesores([disp1, disp2, disp3])

    assert [item.profesor.id for item in ranking] == [3, 1, 2]


def test_asignar_guardias_asigna_mejor_profesor_segun_ranking():
    guardia = Guardia(dia="Lunes", hora=1, aula="A101", profesor_ausente_id=99)

    prof1 = Profesor(id=1, nombre="Profesor A", activo=1, guardias_acumuladas=0, guardias_semana=0)
    prof2 = Profesor(id=2, nombre="Profesor B", activo=1, guardias_acumuladas=0, guardias_semana=1)

    disp1 = ProfesorDisponible(prof1, hora_disponible=1)
    disp2 = ProfesorDisponible(prof2, hora_disponible=1)

    result_guardias = asignar_guardias([guardia], [disp1, disp2])

    assert result_guardias[0].profesor_asignado == 1
    assert prof1.guardias_semana == 1
    assert prof1.guardias_acumuladas == 1
    assert prof2.guardias_semana == 1
    assert prof2.guardias_acumuladas == 0


def test_motor_guardias_integration_asigna_guardia_a_profesor_presente(monkeypatch):
    motor = MotorGuardias(db_path=":memory:")

    profesores = [
        Profesor(id=1, nombre="RFID1", rfid="RFID1", activo=1, guardias_acumuladas=0, guardias_semana=0),
        Profesor(id=2, nombre="RFID2", rfid="RFID2", activo=1, guardias_acumuladas=0, guardias_semana=1),
    ]
    presencias = [Presencia(profesor_id=1, timestamp="2026-04-09 08:00:00", tipo="entrada")]
    ausencias = [Ausencia(profesor_id=99, dia="2026-04-09", hora=1, motivo="Enfermedad")]

    class StubManager:
        def get_profesores(self):
            return profesores

        def get_presencias_hoy(self):
            return presencias

        def get_ausencias_hoy(self):
            return ausencias

        def get_horarios_by_dia(self, dia):
            return [Horario(profesor_id=99, dia=dia, hora=1, aula="A101", asignatura="Matemáticas")]

    motor.db_manager = StubManager()

    resultado = motor.calcular_guardias(dia="2026-04-09")

    assert isinstance(resultado, dict)
    assert len(resultado["guardias"]) == 1
    guardia_asignada = resultado["guardias"][0]
    assert guardia_asignada.aula == "A101"
    assert guardia_asignada.profesor_asignado == 1

    ranking_ids = [item.profesor.id for item in resultado["ranking_profesores"]]
    assert ranking_ids == [1]
    assert ranking_ids[0] == 1


# --- Pruebas de modelos de dominio (1.1.5.4) ---

def test_guardia_atributos_iniciales_correctos():
    """Un objeto Guardia recién creado tiene los atributos esperados."""
    guardia = Guardia(dia="Lunes", hora=2, aula="Aula 101", profesor_ausente_id=5)

    assert guardia.dia == "Lunes"
    assert guardia.hora == 2
    assert guardia.aula == "Aula 101"
    assert guardia.profesor_ausente_id == 5
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

    assert disponible.puntuacion_prioridad == (2, 3)


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
