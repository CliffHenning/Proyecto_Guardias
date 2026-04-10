class Guardia:
    """
    Representa una clase/aula que necesita ser cubierta debido a la ausencia
    de un profesor en una hora concreta.

    Este es un modelo de dominio temporal, no persistido en BD,
    utilizado durante el proceso de cálculo de guardias.
    """

    def __init__(self, dia, hora, aula, profesor_ausente_id=None):
        """
        Args:
            dia: Día de la semana (ej: 'Lunes')
            hora: Hora del día (ej: 1, 2, 3...)
            aula: Aula que necesita cobertura (ej: 'Aula 101')
            profesor_ausente_id: ID del profesor ausente (opcional)
        """
        self.dia = dia
        self.hora = hora
        self.aula = aula
        self.profesor_ausente_id = profesor_ausente_id
        self.profesor_asignado = None
        self.prioridad = 0

    def asignar_profesor(self, profesor_id):
        """Asigna un profesor a esta guardia."""
        self.profesor_asignado = profesor_id

    def esta_cubierta(self):
        """Verifica si la guardia tiene profesor asignado."""
        return self.profesor_asignado is not None

    def __str__(self):
        return f"Guardia: {self.dia} {self.hora}h - {self.aula}"

    def __repr__(self):
        return self.__str__()


class ProfesorDisponible:
    """
    Representa a un profesor que puede realizar guardia en una hora concreta.
    Contiene los datos necesarios para aplicar los criterios de prioridad.

    Este es un modelo de dominio temporal, no persistido en BD,
    utilizado durante el proceso de cálculo de guardias.
    """

    def __init__(self, profesor, hora_disponible):
        """
        Args:
            profesor: Objeto Profesor de db.models
            hora_disponible: Hora en la que está disponible
        """
        self.profesor = profesor
        self.hora_disponible = hora_disponible
        self.puntuacion_prioridad = self._calcular_puntuacion_prioridad()

    def _calcular_puntuacion_prioridad(self):
        """
        Calcula la puntuación de prioridad para ordenar profesores.
        Criterios (orden de importancia):
        1. Menos guardias en la semana actual
        2. Menos guardias acumuladas totales

        Returns:
            tuple: (guardias_semana, guardias_acumuladas) para ordenación
        """
        return (self.profesor.guardias_semana, self.profesor.guardias_acumuladas)

    def puede_hacer_guardia(self, hora_solicitada):
        """
        Verifica si el profesor puede hacer guardia en la hora solicitada.

        Args:
            hora_solicitada: Hora para la que se solicita guardia

        Returns:
            bool: True si puede hacer guardia en esa hora
        """
        return self.hora_disponible == hora_solicitada and self.profesor.activo == 1

    def incrementar_contadores_guardia(self):
        """Incrementa los contadores de guardias del profesor."""
        self.profesor.guardias_semana += 1
        self.profesor.guardias_acumuladas += 1

    def __str__(self):
        return f"ProfesorDisponible: {self.profesor.nombre} (Guardias semana: {self.profesor.guardias_semana}, Total: {self.profesor.guardias_acumuladas})"

    def __repr__(self):
        return self.__str__()

    def __lt__(self, other):
        """Permite ordenar profesores por prioridad (menor puntuación = mayor prioridad)."""
        return self.puntuacion_prioridad < other.puntuacion_prioridad