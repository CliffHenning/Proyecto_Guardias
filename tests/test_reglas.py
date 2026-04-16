import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import describir_hora, describir_horas
from modules.db.models import Profesor
from modules.guardias.models import ProfesorDisponible
from modules.guardias.reglas import calcular_ranking_profesores


def test_describir_hora_devuelve_tramo_real_del_centro():
    assert describir_hora(1) == "1 (8:45-9:45)"
    assert describir_hora(11) == "11 (19:20-20:10)"


def test_describir_horas_agrupa_varias_horas_ordenadas():
    assert describir_horas([4, 1, 3]) == "1 (8:45-9:45), 3 (10:25-11:15), 4 (11:45-12:35)"


def test_profesor_disponible_activo_y_hora_disponible():
    profesor = Profesor(id=1, nombre="Profesor Activo", activo=1, guardias_acumuladas=0, guardias_semana=0)
    disponible = ProfesorDisponible(profesor, hora_disponible=3)

    assert disponible.puede_hacer_guardia(3)
    assert not disponible.puede_hacer_guardia(2)


def test_profesor_disponible_inactivo_no_es_disponible():
    profesor = Profesor(id=2, nombre="Profesor Inactivo", activo=0, guardias_acumuladas=0, guardias_semana=0)
    disponible = ProfesorDisponible(profesor, hora_disponible=3)

    assert not disponible.puede_hacer_guardia(3)


def test_calcular_ranking_profesores_prioridad_jerarquica():
    prof1 = Profesor(id=1, nombre="Profesor A", activo=1, guardias_acumuladas=2, guardias_semana=1)
    prof2 = Profesor(id=2, nombre="Profesor B", activo=1, guardias_acumuladas=1, guardias_semana=2)
    prof3 = Profesor(id=3, nombre="Profesor C", activo=1, guardias_acumuladas=0, guardias_semana=0)

    prof1.carga_lectiva = 4
    prof2.carga_lectiva = 3
    prof3.carga_lectiva = 5

    disp1 = ProfesorDisponible(prof1, hora_disponible=1)
    disp2 = ProfesorDisponible(prof2, hora_disponible=1)
    disp3 = ProfesorDisponible(prof3, hora_disponible=1)

    ranking = calcular_ranking_profesores([disp1, disp2, disp3])

    assert [item.profesor.id for item in ranking] == [3, 2, 1]


def test_calcular_ranking_profesores_resuelve_empate_por_guardias_semana():
    """Con iguales guardias_acumuladas, gana quien tiene menos guardias_semana."""
    prof1 = Profesor(id=1, nombre="Profesor A", activo=1, guardias_acumuladas=1, guardias_semana=3)
    prof2 = Profesor(id=2, nombre="Profesor B", activo=1, guardias_acumuladas=1, guardias_semana=1)

    prof1.carga_lectiva = 3
    prof2.carga_lectiva = 3

    disp1 = ProfesorDisponible(prof1, hora_disponible=1)
    disp2 = ProfesorDisponible(prof2, hora_disponible=1)

    ranking = calcular_ranking_profesores([disp1, disp2])

    assert [item.profesor.id for item in ranking] == [2, 1]


def test_calcular_ranking_profesores_resuelve_empate_por_carga_lectiva():
    prof1 = Profesor(id=1, nombre="Profesor A", activo=1, guardias_acumuladas=0, guardias_semana=0)
    prof2 = Profesor(id=2, nombre="Profesor B", activo=1, guardias_acumuladas=0, guardias_semana=0)

    prof1.carga_lectiva = 5
    prof2.carga_lectiva = 2

    disp1 = ProfesorDisponible(prof1, hora_disponible=1)
    disp2 = ProfesorDisponible(prof2, hora_disponible=1)

    ranking = calcular_ranking_profesores([disp1, disp2])

    assert [item.profesor.id for item in ranking] == [2, 1]


def test_incrementar_contadores_guardia_actualiza_ambos_contadores():
    """incrementar_contadores_guardia debe aumentar guardias_semana y guardias_acumuladas en 1."""
    profesor = Profesor(id=1, nombre="Profesor A", activo=1, guardias_acumuladas=2, guardias_semana=1)
    disponible = ProfesorDisponible(profesor, hora_disponible=2)

    disponible.incrementar_contadores_guardia()

    assert disponible.profesor.guardias_semana == 2
    assert disponible.profesor.guardias_acumuladas == 3
