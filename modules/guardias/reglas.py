"""
Módulo de reglas para el cálculo de guardias.
Contiene las funciones que definen las reglas de negocio para determinar
disponibilidad de profesores y asignación de guardias.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from modules.guardias.models import ProfesorDisponible


def determinar_profesores_disponibles(profesores, presencias, ausencias, hora, db_manager, dia_semana=None):
    """
    Determina qué profesores están disponibles para hacer guardia en una hora específica.
    Un profesor está disponible si:
    - Está presente (último registro de presencia es 'entrada')
    - No está ausente en esa hora

    Args:
        profesores: Lista de objetos Profesor
        presencias: Lista de objetos Presencia del día
        ausencias: Lista de objetos Ausencia del día
        hora: Hora específica (int)
        db_manager: Instancia de DBManager para acceder a horarios

    Returns:
        list: Lista de objetos ProfesorDisponible con carga_lectiva calculada
    """
    disponibles = []
    for profesor in profesores:
        ausente_hora = any(a.profesor_id == profesor.id and a.hora == hora for a in ausencias)
        if ausente_hora:
            continue

        horarios_dia = db_manager.get_horarios_by_dia(dia_semana) if dia_semana else []
        tiene_clase_hora = any(
            horario.profesor_id == profesor.id and horario.hora == hora
            for horario in horarios_dia
        )
        if tiene_clase_hora:
            continue

        presencias_profesor = sorted([p for p in presencias if p.profesor_id == profesor.id], key=lambda p: p.timestamp)
        if presencias_profesor and presencias_profesor[-1].tipo == 'entrada':
            carga_lectiva = calcular_carga_lectiva(profesor.id, db_manager)
            profesor.carga_lectiva = carga_lectiva
            profesor_disp = ProfesorDisponible(profesor, hora)
            disponibles.append(profesor_disp)
    return disponibles


def calcular_carga_lectiva(profesor_id, db_manager):
    """
    Calcula la carga lectiva semanal de un profesor (número de horas).

    Args:
        profesor_id: ID del profesor
        db_manager: Instancia de DBManager

    Returns:
        int: Número de horas lectivas semanales
    """
    dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
    carga = 0
    for dia in dias:
        horarios = db_manager.get_horarios_by_dia(dia)
        carga += len([h for h in horarios if h.profesor_id == profesor_id])
    return carga


def calcular_ranking_profesores(profesores_disponibles):
    """
    Calcula el ranking de profesores disponibles ordenado por prioridad.
    Criterios jerárquicos:
    1. Menor número de guardias acumuladas
    2. Menor número de guardias en la semana actual
    3. Menor carga lectiva

    Args:
        profesores_disponibles: Lista de ProfesorDisponible

    Returns:
        list: Lista ordenada de ProfesorDisponible (mejor prioridad primero)
    """
    for prof_disp in profesores_disponibles:
        prof_disp.puntuacion_prioridad = (
            prof_disp.profesor.guardias_acumuladas,
            prof_disp.profesor.guardias_semana,
            getattr(prof_disp.profesor, 'carga_lectiva', 0)
        )
    return sorted(profesores_disponibles)


def asignar_guardias(guardias, ranking_profesores):
    """
    Asigna profesores a las guardias según el ranking.

    Args:
        guardias: Lista de objetos Guardia
        ranking_profesores: Lista ordenada de ProfesorDisponible

    Returns:
        list: Lista de guardias con profesores asignados
    """
    for guardia in guardias:
        for profesor_disp in ranking_profesores:
            if profesor_disp.puede_hacer_guardia(guardia.hora):
                guardia.asignar_profesor(profesor_disp.profesor.id)
                profesor_disp.incrementar_contadores_guardia()
                break
    return guardias