class Profesor:
    def __init__(self, id=None, nombre=None, rfid=None, huella_id=None, face_id=None, activo=1, guardias_acumuladas=0, guardias_semana=0):
        self.id = id
        self.nombre = nombre
        self.rfid = rfid
        self.huella_id = huella_id
        self.face_id = face_id
        self.activo = activo
        self.guardias_acumuladas = guardias_acumuladas
        self.guardias_semana = guardias_semana

class Horario:
    def __init__(self, id=None, profesor_id=None, dia=None, hora=None, aula=None, asignatura=None):
        self.id = id
        self.profesor_id = profesor_id
        self.dia = dia
        self.hora = hora
        self.aula = aula
        self.asignatura = asignatura

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
    def __init__(self, id=None, dia=None, hora=None, aula=None, profesor_asignado=None, cubierta=0):
        self.id = id
        self.dia = dia
        self.hora = hora
        self.aula = aula
        self.profesor_asignado = profesor_asignado
        self.cubierta = cubierta