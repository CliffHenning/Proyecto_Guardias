import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from datetime import datetime
import locale
from modules.db.db_manager import DBManager
from modules.guardias.reglas import determinar_profesores_disponibles, calcular_ranking_profesores, asignar_guardias
from modules.guardias.models import Guardia

"""
Motor de cálculo de guardias.
Coordina el proceso de cálculo de guardias, obteniendo datos a través de db_manager
y aplicando reglas definidas en reglas.py.
"""

try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Spanish_Spain')
    except locale.Error:
        pass


class MotorGuardias:
    """
    Motor responsable de calcular las guardias para un día determinado.
    """

    def __init__(self, db_path="ies.db"):
        self.db_manager = DBManager(db_path)

    def calcular_guardias(self, dia=None):
        """
        Calcula las guardias para el día especificado o el día actual.

        Args:
            dia: Día en formato 'YYYY-MM-DD'

        Returns:
            dict: {
                'ranking_profesores': lista ordenada de ProfesorDisponible,
                'guardias': lista de objetos Guardia con asignaciones
            }
        """
        if dia is None:
            dia = datetime.now().strftime("%Y-%m-%d")

        profesores = self.db_manager.get_profesores()
        presencias = self.db_manager.get_presencias_hoy(dia)
        ausencias = self.db_manager.get_ausencias_hoy(dia)

        guardias = []
        for ausencia in ausencias:
            fecha = datetime.strptime(ausencia.dia, "%Y-%m-%d")
            dia_semana = fecha.strftime("%A").capitalize()
            horarios_profesor = self.db_manager.get_horarios_by_dia(dia_semana)
            horario_ausente = next((h for h in horarios_profesor if h.profesor_id == ausencia.profesor_id and h.hora == ausencia.hora), None)
            if horario_ausente:
                guardia = Guardia(dia_semana, ausencia.hora, horario_ausente.aula, ausencia.profesor_id)
                guardias.append(guardia)

        horas_con_guardias = set(g.hora for g in guardias)
        profesores_disponibles_global = set()

        for hora in horas_con_guardias:
            profesores_disponibles_hora = determinar_profesores_disponibles(profesores, presencias, ausencias, hora, self.db_manager)
            profesores_disponibles_global.update(profesores_disponibles_hora)

        ranking_profesores = calcular_ranking_profesores(list(profesores_disponibles_global))

        guardias_asignadas = asignar_guardias(guardias, ranking_profesores)

        return {
            'ranking_profesores': ranking_profesores,
            'guardias': guardias_asignadas
        }