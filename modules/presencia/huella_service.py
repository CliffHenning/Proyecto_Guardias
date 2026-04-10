import sys
import os
import platform

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from modules.db.db_manager import DBManager


def identificar_huella():
    """
    Identifica al profesor mediante lector de huella dactilar usando PiFinger.

    Investigación realizada:
    - Dispositivo: Lector de huella PiFinger (SKU 21253)
    - Comunicación: UART (RS232/TTL) a 9600 bps
    - Librería: pyserial (pip install pyserial)
    - Puerto serial: Generalmente /dev/ttyAMA0 o /dev/ttyUSB0 en Raspberry Pi
    - Protocolo: Comandos binarios específicos del PiFinger para:
      * GetImage: Capturar imagen de dedo
      * ImgToTz: Convertir imagen a template biométrico
      * Match: Comparar templates
      * GetUser: Obtener ID de usuario registrado
    - Registro de huellas: Se realiza con secuencia Enroll (3 capturas del mismo dedo)
    - Lectura de ID: El sensor devuelve el ID (0-127) asociado a la huella coincidente
    - Mapeo ID a profesor: Almacenar el ID en el campo huella_id de la tabla profesores

    Nota: En desarrollo (Windows), permite entrada manual del ID de huella para testing.
    """
    if platform.system() == "Linux":
        try:
            import serial
        except ImportError:
            print("Error: Librería pyserial no instalada. Instale con: pip install pyserial")
            return None

        try:
            puerto = "/dev/ttyAMA0"
            ser = serial.Serial(puerto, 9600, timeout=1)

            print("Acerque su dedo al lector de huella...")
            print("(Nota: Esta es una implementación base. El flujo completo del PiFinger requiere")
            print(" secuencia: GetImage -> ImgToTz -> Match -> GetUser)")

            huella_id = None
            try:
                # En un flujo real, aquí iría:
                # 1. Enviar comando GetImage
                # 2. Enviar comando ImgToTz (para procesar imagen a template)
                # 3. Enviar comando Match (para buscar coincidencia)
                # 4. Parsear respuesta binaria y extraer ID
                respuesta = ser.read(10)  # Placeholder: leer respuesta del sensor
                # Parsear respuesta para extraer huella_id
                # huella_id = int(respuesta[4])  # Ejemplo

            except Exception as e:
                print(f"Error al comunicar con PiFinger: {e}")
                return None
            finally:
                ser.close()

            if huella_id is None:
                print("No se detectó huella válida")
                return None

            huella_id_str = str(huella_id)
            print(f"Huella detectada con ID: {huella_id_str}")

        except (FileNotFoundError, Exception) as e:
            print(f"Error al acceder al puerto serial: {e}")
            print("Intente con /dev/ttyUSB0 o verifique que el PiFinger está conectado.")
            return None
    else:
        print("Modo desarrollo: Ingrese el ID de huella manualmente:")
        huella_id_str = input("ID de huella (0-127): ").strip()
        if not huella_id_str:
            print("ID vacío")
            return None
        try:
            int(huella_id_str)
        except ValueError:
            print("El ID debe ser numérico")
            return None

    db_manager = DBManager()
    profesores = db_manager.get_profesores()

    for profesor in profesores:
        if profesor.huella_id == huella_id_str:
            print(f"Profesor identificado: {profesor.nombre}")
            return profesor.id

    print(f"Huella no registrada: ID {huella_id_str}")
    return None
