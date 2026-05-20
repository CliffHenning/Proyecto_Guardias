from modules.db.db_manager import DBManager
from modules.db.models import Presencia


def identificar_huella():
    """En tests se monkeypatchea este método.

    Implementación real:
    - En la app se usa modules.presencia.huella_service.identificar_huella
    - En este módulo mantenemos una función intermedia para que sea fácil de testear.
    """

    from modules.presencia.huella_service import identificar_huella as _identificar_huella

    return _identificar_huella()


def identificar_profesor():
    """Identifica al profesor según el método configurado.

    - METODO_PRESENCIA=huella -> usa identificar_huella
    - Si el método no es soportado -> ValueError

    En tests se valida que el comportamiento es el esperado mediante monkeypatch.
    """

    import os

    metodo = os.environ.get("METODO_PRESENCIA", "huella").strip().lower()

    if metodo == "huella":
        return identificar_huella()

    raise ValueError(f"Método de presencia desconocido: {metodo}")


def registrar_presencia(profesor_id, db_path="ies.db"):
    db_manager = DBManager(db_path)

    ultima_presencia = db_manager.get_presencia_hoy(profesor_id)

    if ultima_presencia and ultima_presencia.tipo == 'entrada':
        tipo = 'salida'
    else:
        tipo = 'entrada'

    presencia = Presencia(profesor_id=profesor_id, tipo=tipo)
    db_manager.insert_presencia(presencia)

    if tipo == 'entrada':
        ausencias_activas = db_manager.get_ausencias_profesor_hoy(profesor_id)
        if ausencias_activas:
            db_manager.delete_ausencias_profesor_hoy(profesor_id)

    return tipo


def obtener_estado_actual(db_path="ies.db"):
    db_manager = DBManager(db_path)
    profesores = db_manager.get_profesores()
    presencias_hoy = db_manager.get_presencias_hoy()

    estado = {}

    for profesor in profesores:
        presencias_profesor = sorted(
            [p for p in presencias_hoy if p.profesor_id == profesor.id],
            key=lambda p: p.timestamp,
        )

        presente = bool(presencias_profesor) and presencias_profesor[-1].tipo == 'entrada'

        estado[profesor.id] = {
            'nombre': profesor.nombre,
            'presente': presente,
            'ultima_accion': presencias_profesor[-1].tipo if presencias_profesor else None,
            'timestamp': presencias_profesor[-1].timestamp if presencias_profesor else None,
        }

    return estado

