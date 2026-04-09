import os
from modules.presencia.rfid_service import identificar_rfid
#from modules.presencia.huella_service import identificar_huella
#from modules.presencia.facial_service import identificar_facial
from modules.db.db_manager import DBManager
from modules.db.models import Presencia

def identificar_profesor():
    metodo = os.getenv("METODO_PRESENCIA", "rfid")  # valor por defecto
    if metodo == "rfid":
        return identificar_rfid()
    #elif metodo == "huella":
    #    return identificar_huella()
    #elif metodo == "facial":
    #    return identificar_facial()
    else:
        raise ValueError(f"Método de presencia desconocido: {metodo}")

def registrar_presencia(profesor_id):
    """Registra entrada o salida del profesor."""
    db_manager = DBManager()

    # Obtener último registro de presencia del día
    ultima_presencia = db_manager.get_presencia_hoy(profesor_id)

    # Determinar si es entrada o salida
    if ultima_presencia and ultima_presencia.tipo == 'entrada':
        tipo = 'salida'
    else:
        tipo = 'entrada'

    # Crear y guardar el registro
    presencia = Presencia(profesor_id=profesor_id, tipo=tipo)
    db_manager.insert_presencia(presencia)

    return tipo

def obtener_estado_actual():
    """Obtiene el estado actual de todos los profesores (presente/ausente)."""
    db_manager = DBManager()
    profesores = db_manager.get_profesores()
    presencias_hoy = db_manager.get_presencias_hoy()

    estado = {}
    for profesor in profesores:
        # Obtener presencias del profesor ordenadas por timestamp
        presencias_profesor = sorted([p for p in presencias_hoy if p.profesor_id == profesor.id],
                                   key=lambda p: p.timestamp)
        # Si el último registro es 'entrada', está presente
        presente = presencias_profesor and presencias_profesor[-1].tipo == 'entrada'
        estado[profesor.id] = {
            'nombre': profesor.nombre,
            'presente': presente,
            'ultima_accion': presencias_profesor[-1].tipo if presencias_profesor else None,
            'timestamp': presencias_profesor[-1].timestamp if presencias_profesor else None
        }

    return estado