import sys
import os
import platform

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from modules.db.db_manager import DBManager

# ── Configuración de red ────────────────────────────────────────────────────
# URL base del servidor de huellas en la Raspberry Pi.
# Se puede sobreescribir con la variable de entorno PIFINGER_URL.
# Ejemplo: export PIFINGER_URL=http://192.168.1.50:5001
_PIFINGER_URL_DEFAULT = "http://192.168.208.120:5001"
_RUTA_IDENTIFICACION_CACHE = None
_METODO_IDENTIFICACION_CACHE = None


def _pifinger_url() -> str:
    return os.environ.get("PIFINGER_URL", _PIFINGER_URL_DEFAULT).rstrip("/")


def _timeout_lectura_red() -> int:
    valor = os.environ.get("PIFINGER_TIMEOUT", "20").strip()
    try:
        timeout = int(valor)
    except ValueError:
        timeout = 20
    return max(5, timeout)


def _rutas_identificacion() -> list[str]:
    ruta_preferida = os.environ.get("PIFINGER_IDENTIFY_PATH", "").strip()

    if ruta_preferida:
        if not ruta_preferida.startswith("/"):
            ruta_preferida = f"/{ruta_preferida}"
        return [ruta_preferida]

    global _RUTA_IDENTIFICACION_CACHE
    if _RUTA_IDENTIFICACION_CACHE:
        return [_RUTA_IDENTIFICACION_CACHE]

    rutas = [
        "/scan",
        "/identificar",
        "/identify",
        "/match",
        "/verify",
        "/compare",
        "/compare_fp",
    ]
    normalizadas = []
    for ruta in rutas:
        if not ruta:
            continue
        if not ruta.startswith("/"):
            ruta = f"/{ruta}"
        if ruta not in normalizadas:
            normalizadas.append(ruta)
    return normalizadas


def _metodos_identificacion() -> list[str]:
    metodo_preferido = os.environ.get("PIFINGER_IDENTIFY_METHOD", "").strip().upper()

    if metodo_preferido in {"GET", "POST"}:
        return [metodo_preferido]

    global _METODO_IDENTIFICACION_CACHE
    if _METODO_IDENTIFICACION_CACHE in {"GET", "POST"}:
        return [_METODO_IDENTIFICACION_CACHE]

    metodos = ["GET", "POST"]
    normalizados = []
    for metodo in metodos:
        if metodo in {"GET", "POST"} and metodo not in normalizados:
            normalizados.append(metodo)
    return normalizados


def _parsear_respuesta_identificacion(datos):
    """Normaliza respuestas JSON/texto del servidor de huellas.

    Devuelve:
      (huella_id:int, None) cuando hay match con ID.
      (None, mensaje) cuando hay error o FAIL.
    """
    if isinstance(datos, dict):
        if str(datos.get("result", "")).strip().lower() in {"no data", "no_data", "waiting"}:
            return None, "NO_DATA"

        if datos.get("ok") and ("huella_id" in datos or "id" in datos or "fingerprint_id" in datos):
            huella_id = int(datos.get("huella_id", datos.get("id", datos.get("fingerprint_id"))))
            return huella_id, None

        if str(datos.get("result", "")).upper() == "PASS":
            if "huella_id" in datos or "id" in datos or "fingerprint_id" in datos:
                huella_id = int(datos.get("huella_id", datos.get("id", datos.get("fingerprint_id"))))
                return huella_id, None
            return None, "El servidor devolvio PASS, pero sin ID de huella."

        if datos.get("ok") is False or str(datos.get("result", "")).upper() == "FAIL":
            return None, str(datos.get("error", datos.get("result", "FAIL")))

        return None, f"Respuesta inesperada: {datos}"

    texto = str(datos or "").strip()
    texto_upper = texto.upper()
    if texto_upper.startswith("PASS"):
        # Soporta: PASS 7, PASS:7, PASS|7
        partes = texto.replace(":", " ").replace("|", " ").split()
        for parte in partes[1:]:
            if parte.isdigit():
                return int(parte), None
        return None, "Respuesta PASS sin ID numerico."
    if texto_upper.startswith("FAIL"):
        return None, texto
    return None, f"Respuesta no reconocida: {texto}"


def _modo_manual_habilitado() -> bool:
    valor = os.environ.get("ALLOW_MANUAL_HUELLA", "0").strip().lower()
    return valor in {"1", "true", "yes", "on"}


# ── Modos de identificación ─────────────────────────────────────────────────

def _identificar_via_red() -> int | None:
    """
    Llama al servidor Flask de la Raspberry Pi y devuelve el huella_id como entero.
    Usa la variable de entorno PIFINGER_URL (o el valor por defecto).
    """
    try:
        import time
        import urllib.request
        import urllib.error
        import json

        timeout = _timeout_lectura_red()
        rutas = _rutas_identificacion()
        metodos = _metodos_identificacion()
        poll_interval = 0.7
        deadline = time.monotonic() + timeout
        print(f"Acerque su dedo al lector... (espera maxima: {timeout}s)")

        ultimo_error = None
        ruta_activa = None
        metodo_activo = None
        ultimo_log_endpoint = None
        while time.monotonic() < deadline:
            hubo_espera_sensor = False
            hubo_ruta_valida = False

            rutas_iter = [ruta_activa] if ruta_activa else rutas
            metodos_iter = [metodo_activo] if metodo_activo else metodos

            for ruta in rutas_iter:
                url = f"{_pifinger_url()}{ruta}"
                for metodo in metodos_iter:
                    endpoint_actual = f"{url} [{metodo}]"
                    if endpoint_actual != ultimo_log_endpoint:
                        print(f"Conectando con servidor de huellas: {endpoint_actual}")
                        ultimo_log_endpoint = endpoint_actual
                    try:
                        req = urllib.request.Request(url=url, method=metodo)
                        with urllib.request.urlopen(req, timeout=min(5, timeout)) as resp:
                            crudo = resp.read().decode()
                        try:
                            datos = json.loads(crudo)
                        except json.JSONDecodeError:
                            datos = crudo
                    except urllib.error.HTTPError as http_error:
                        if http_error.code in {404, 405}:
                            ultimo_error = f"Ruta/metodo no disponible: {ruta} [{metodo}]"
                            continue
                        raise

                    hubo_ruta_valida = True
                    global _RUTA_IDENTIFICACION_CACHE, _METODO_IDENTIFICACION_CACHE
                    _RUTA_IDENTIFICACION_CACHE = ruta
                    _METODO_IDENTIFICACION_CACHE = metodo

                    huella_id, mensaje = _parsear_respuesta_identificacion(datos)
                    if huella_id is not None:
                        print(f"Huella detectada. ID={huella_id}")
                        return huella_id
                    if mensaje == "NO_DATA":
                        ruta_activa = ruta
                        metodo_activo = metodo
                        _RUTA_IDENTIFICACION_CACHE = ruta
                        _METODO_IDENTIFICACION_CACHE = metodo
                        hubo_espera_sensor = True
                        break
                    if mensaje:
                        if str(mensaje).upper().startswith("FAIL"):
                            print(f"El sensor respondio: {mensaje}")
                            return None
                        ultimo_error = f"{mensaje} en {ruta} [{metodo}]"

                if hubo_espera_sensor:
                    break

            if hubo_espera_sensor:
                time.sleep(poll_interval)
                continue

            # Si no hay ninguna ruta valida, o no hay datos de espera del sensor, salir.
            if not hubo_ruta_valida:
                break
            break

        if ultimo_error:
            print(ultimo_error)
        return None

    except TimeoutError:
        print("Tiempo de espera agotado: no se detecto ningun dedo en el lector.")
        return None
    except Exception as e:
        print(f"Error al comunicar con el servidor de huellas ({_pifinger_url()}): {e}")
        print("Verifique que la Raspberry Pi esta encendida y el servidor activo.")
        return None


def _identificar_serial_local() -> int | None:
    """
    Lee el PiFinger directamente por serial (solo en Linux / Raspberry Pi).
    Flujo: getImage -> convertImage -> searchTemplate
    """
    try:
        from pyfingerprint.pyfingerprint import PyFingerprint  # type: ignore[import]
    except ImportError:
        print("Error: Instale pyfingerprint en la Raspberry Pi: pip install pyfingerprint")
        return None

    import time

    puerto = os.environ.get("PIFINGER_PORT", "/dev/ttyAMA0")
    try:
        sensor = PyFingerprint(puerto, 57600, 0xFFFFFFFF, 0x00000000)
        if not sensor.verifyPassword():
            print("Error: Contraseña del sensor PiFinger incorrecta.")
            return None
    except Exception as e:
        print(f"Error al conectar con PiFinger en {puerto}: {e}")
        return None

    print("Acerque su dedo al lector de huella...")
    timeout = 10
    inicio = time.time()
    while time.time() - inicio < timeout:
        if sensor.readImage():
            break
        time.sleep(0.1)
    else:
        print("Tiempo agotado: no se detectó dedo.")
        return None

    try:
        sensor.convertImage(0x01)
        posicion, precision = sensor.searchTemplate()
    except Exception as e:
        print(f"Error al procesar huella: {e}")
        return None

    if posicion == -1:
        print("Huella no reconocida.")
        return None

    print(f"Huella detectada. ID={posicion}  Precisión={precision}")
    return int(posicion)


def _identificar_manual() -> int | None:
    """Modo desarrollo: entrada manual del ID."""
    print("Modo desarrollo: Ingrese el ID de huella manualmente:")
    huella_id_texto = input("ID de huella (0-127): ").strip()
    if not huella_id_texto:
        print("ID vacío")
        return None
    try:
        huella_id = int(huella_id_texto)
    except ValueError:
        print("El ID debe ser numérico")
        return None
    return huella_id


def probar_conexion_raspberry(ip: str = "192.208.120", port: int = 5001, timeout: int = 3) -> bool:
    """
    Prueba sencilla de conexión al servidor de huellas en la Raspberry Pi.

    Devuelve:
      True  -> PASS (hay conexión y /health responde con ok=True)
      False -> FAIL (sin conexión o respuesta inválida)
    """
    import json
    import urllib.error
    import urllib.request

    partes = ip.split(".")
    if len(partes) != 4:
        print(f"FAIL: La IP '{ip}' no parece válida (se esperaban 4 bloques).")
        print("Ejemplo correcto: 192.168.1.120")
        return False

    url = f"http://{ip}:{port}/health"
    print(f"Intentando conectar con Raspberry Pi en: {url}")

    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())

        if payload.get("ok") is True or str(payload.get("status", "")).lower() == "ok":
            print("PASS: Conexión correcta con la Raspberry Pi.")
            return True

        print(f"FAIL: El servidor respondió, pero no en estado OK: {payload}")
        return False

    except urllib.error.URLError as e:
        print(f"FAIL: No se pudo conectar ({e}).")
        print("Revise red, IP real de la Pi y que el servidor finger_server.py esté activo.")
        return False
    except Exception as e:
        print(f"FAIL: Error inesperado durante la prueba ({e}).")
        return False


# ── Función principal ───────────────────────────────────────────────────────

def identificar_huella():
    """
    Identifica al profesor mediante huella dactilar.

        Estrategia de selección automática:
            1. Intenta SIEMPRE cliente HTTP hacia Raspberry Pi (Windows/Linux/Mac)
            2. Si falla y estamos en Linux, intenta serial local (ejecutándose en la Pi)
            3. Solo si ALLOW_MANUAL_HUELLA=1, permite entrada manual (desarrollo)

    Variables de entorno:
      PIFINGER_URL   URL del servidor de huellas, p.ej. http://192.168.1.50:5001
      PIFINGER_PORT  Puerto serial en Linux, por defecto /dev/ttyAMA0
      ALLOW_MANUAL_HUELLA  1 para habilitar fallback manual de ID
    """
    # Flujo principal: comparar huella en memoria del sensor remoto (Raspberry Pi)
    huella_id = _identificar_via_red()

    # Fallback 1: si la app corre en la propia Raspberry, intentar serial local
    if huella_id is None and platform.system() == "Linux":
        huella_id = _identificar_serial_local()

    # Fallback 2 (solo desarrollo): entrada manual explícitamente habilitada
    if huella_id is None and _modo_manual_habilitado():
        huella_id = _identificar_manual()

    if huella_id is None:
        if not _modo_manual_habilitado():
            print("No se pudo identificar huella desde Raspberry Pi/sensor.")
            print("Para pruebas manuales, establezca ALLOW_MANUAL_HUELLA=1.")
        return None

    # Resolver huella_id → profesor
    db_manager = DBManager()
    profesores = db_manager.get_profesores()

    for profesor in profesores:
        if profesor.huella_id == huella_id:
            print(f"Profesor identificado: {profesor.nombre}")
            return profesor.id

    print(f"Huella no registrada: ID {huella_id}")
    return None
