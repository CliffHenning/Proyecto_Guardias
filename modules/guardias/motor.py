import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from datetime import datetime
from modules.db.db_manager import DBManager
from modules.db.models import Ausencia
from modules.guardias.reglas import determinar_profesores_disponibles, calcular_ranking_profesores
from modules.guardias.models import Guardia
from config import TRAMOS_HORARIOS

"""
Motor de cálculo de guardias.
Coordina el proceso de cálculo de guardias, obteniendo datos a través de db_manager
y aplicando reglas definidas en reglas.py.
"""

DIAS_SEMANA_ES = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
]


def _parsear_hora_inicio(tramo):
    inicio, _fin = tramo.split("-")
    return datetime.strptime(inicio, "%H:%M").time()


def obtener_hora_guardia_actual(fecha_hora=None, margen_minutos=10):
    """Devuelve la hora lectiva actual cuando ha vencido el margen de tolerancia."""
    fecha_hora = fecha_hora or datetime.now()
    ahora = fecha_hora.time()

    for hora, tramo in TRAMOS_HORARIOS.items():
        inicio = _parsear_hora_inicio(tramo)
        inicio_con_margen = datetime.combine(fecha_hora.date(), inicio)
        inicio_con_margen = inicio_con_margen.replace(second=0, microsecond=0)
        inicio_con_margen = inicio_con_margen.timestamp() + (margen_minutos * 60)
        if fecha_hora.timestamp() < inicio_con_margen:
            continue

        siguiente_tramo = TRAMOS_HORARIOS.get(hora + 1)
        if siguiente_tramo is None:
            return hora

        inicio_siguiente = _parsear_hora_inicio(siguiente_tramo)
        if ahora < inicio_siguiente:
            return hora

    return None


def obtener_dia_semana_es(fecha):
    """Devuelve el nombre del día en español sin depender del locale del sistema."""
    return DIAS_SEMANA_ES[fecha.weekday()]


class MotorGuardias:
    """
    Motor responsable de calcular las guardias para un día determinado.
    """

    def __init__(self, db_path="ies.db"):
        self.db_manager = DBManager(db_path)

    def detectar_ausencias_automaticas(self, ahora=None, margen_minutos=10):
        """Registra ausencias automáticas del tramo actual para docentes sin fichaje de entrada."""
        ahora = ahora or datetime.now()
        if ahora.weekday() > 4:
            return []

        hora_actual = obtener_hora_guardia_actual(ahora, margen_minutos=margen_minutos)
        if hora_actual is None:
            return []

        fecha = ahora.strftime("%Y-%m-%d")
        dia_semana = obtener_dia_semana_es(ahora)
        horarios = self.db_manager.get_horarios_by_dia(dia_semana)
        horarios_hora_actual = [horario for horario in horarios if horario.hora == hora_actual]
        if not horarios_hora_actual:
            return []

        presencias = self.db_manager.get_presencias_hoy(fecha)
        ultima_presencia_por_profesor = {}
        for presencia in presencias:
            ultima_presencia_por_profesor[presencia.profesor_id] = presencia

        ausencias = []
        for horario in horarios_hora_actual:
            ultima_presencia = ultima_presencia_por_profesor.get(horario.profesor_id)
            if ultima_presencia is not None and ultima_presencia.tipo == "entrada":
                continue

            ausencia = self.db_manager.ensure_ausencia(
                Ausencia(
                    profesor_id=horario.profesor_id,
                    dia=fecha,
                    hora=hora_actual,
                    motivo="Ausencia detectada automáticamente",
                )
            )
            ausencias.append(ausencia)

        return ausencias

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
            dia_semana = obtener_dia_semana_es(fecha)
            horarios_profesor = self.db_manager.get_horarios_by_dia(dia_semana)
            horario_ausente = next((h for h in horarios_profesor if h.profesor_id == ausencia.profesor_id and h.hora == ausencia.hora), None)
            guardia = Guardia(
                ausencia.dia,
                ausencia.hora,
                horario_ausente.aula if horario_ausente else "Aula por determinar",
                ausencia.profesor_id,
                asignatura=horario_ausente.asignatura if horario_ausente else "Sin asignatura",
            )
            guardias.append(guardia)

        horas_con_guardias = set(g.hora for g in guardias)
        profesores_disponibles_global = set()

        for hora in horas_con_guardias:
            fecha_guardia = next(g.dia for g in guardias if g.hora == hora)
            dia_semana = obtener_dia_semana_es(datetime.strptime(fecha_guardia, "%Y-%m-%d"))
            profesores_disponibles_hora = determinar_profesores_disponibles(
                profesores,
                presencias,
                ausencias,
                hora,
                self.db_manager,
                dia_semana=dia_semana,
            )
            profesores_disponibles_global.update(profesores_disponibles_hora)

        ranking_profesores = calcular_ranking_profesores(list(profesores_disponibles_global))

        return {
            'ranking_profesores': ranking_profesores,
            'guardias': guardias
        }