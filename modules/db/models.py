GUARDIA_ASIGNATURA = "guardia"


def _normalizar_asignatura(valor):
    return (valor or "").strip().casefold()


class Profesor:
    def __init__(self, id=None, nombre=None, departamento=None, rfid=None, huella_id=None, face_id=None, activo=1, guardias_acumuladas=0, guardias_semana=0):
        self.id = id
        self.nombre = nombre
        self.departamento = departamento
        self.rfid = rfid
        self.huella_id = huella_id
        self.face_id = face_id
        self.activo = activo
        self.guardias_acumuladas = guardias_acumuladas
        self.guardias_semana = guardias_semana

class Horario:
    def __init__(self, id=None, profesor_id=None, dia=None, hora=None, tipo=None, aula=None, asignatura=None):
        self.id = id
        self.profesor_id = profesor_id
        self.dia = dia
        self.hora = hora
        self.tipo = tipo
        self.aula = aula
        self.asignatura = asignatura

    def es_guardia(self):
        return (self.tipo or "").strip().casefold() == GUARDIA_ASIGNATURA or _normalizar_asignatura(self.asignatura) == GUARDIA_ASIGNATURA

    def es_clase_lectiva(self):
        tipo_normalizado = (self.tipo or "").strip().casefold()
        if tipo_normalizado == "libre":
            return False
        if tipo_normalizado == "clase":
            return True
        return not self.es_guardia()

class Presencia:
    def __init__(self, id=None, profesor_id=None, timestamp=None, tipo=None):
        self.id = id
        self.profesor_id = profesor_id
        self.timestamp = timestamp
        self.tipo = tipo

class Ausencia:
    def __init__(self, id=None, profesor_id=None, dia=None, hora=None, motivo=None):
        self.id = id
        self.profesor_id = profesor_id
        self.dia = dia
        self.hora = hora
        self.motivo = motivo

class Guardia:
    def __init__(self, id=None, dia=None, hora=None, aula=None, asignatura=None, profesor_ausente_id=None, profesor_cubre_id=None, cubierta=0):
        self.id = id
        self.dia = dia
        self.hora = hora
        self.aula = aula
        self.asignatura = asignatura
        self.profesor_ausente_id = profesor_ausente_id
        self.profesor_cubre_id = profesor_cubre_id
        self.cubierta = cubierta

    @property
    def profesor_asignado(self):
        return self.profesor_cubre_id

    @profesor_asignado.setter
    def profesor_asignado(self, value):
        self.profesor_cubre_id = value