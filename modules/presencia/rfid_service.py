import sys
import os
import platform

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from modules.db.db_manager import DBManager

def identificar_rfid():
    """
    Identifica al profesor mediante RFID usando MFRC522.

    Investigación realizada:
    - Dispositivo: RFID HAT para Raspberry Pi (SKU 20003) basado en MFRC522
    - Comunicación: SPI (Serial Peripheral Interface)
    - Librería: mfrc522 (instalar con: pip install mfrc522)
    - Detección del dispositivo: El HAT se conecta a los pines SPI de la Raspberry Pi.
      Para detectar: Habilitar SPI en raspi-config, luego el módulo se detecta automáticamente.
    - Lectura del UID: Usar SimpleMFRC522().read() que devuelve (id, text), donde id es el UID.
    - Mapeo UID a profesor: Almacenar el UID en la base de datos en el campo rfid de la tabla profesores,
      luego buscar coincidencia.

    Nota: En desarrollo (Windows), permite entrada manual para testing.
    """
    # Verificar si estamos en Raspberry Pi (Linux)
    if platform.system() == "Linux":
        try:
            from mfrc522 import SimpleMFRC522  # type: ignore
        except ImportError:
            print("Error: Librería mfrc522 no instalada. Instale con: pip install mfrc522")
            return None

        reader = SimpleMFRC522()

        print("Acerque la tarjeta RFID al lector...")
        try:
            id, text = reader.read()
            uid = str(id)  # Convertir a string para comparación
            print(f"UID leído: {uid}")
        except Exception as e:
            print(f"Error al leer RFID: {e}")
            return None
    else:
        # Modo desarrollo: entrada manual
        print("Modo desarrollo: Ingrese el UID de la tarjeta RFID manualmente:")
        uid = input("UID: ").strip()
        if not uid:
            print("UID vacío")
            return None

    # Buscar profesor por RFID
    db_manager = DBManager()
    profesores = db_manager.get_profesores()

    for profesor in profesores:
        if profesor.rfid == uid:
            print(f"Profesor identificado: {profesor.nombre}")
            return profesor.id

    print(f"UID no registrado: {uid}")
    return None