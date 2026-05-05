import sys
import os
import platform
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from modules.db.db_manager import DBManager

# ── Configuración de red ────────────────────────────────────────────────────
# URL base del servidor de huellas en la Raspberry Pi.
# Se puede sobreescribir con la variable de entorno PIFINGER_URL.
# Ejemplo: export PIFINGER_URL=http://192.168.1.50:5001
_PIFINGER_URL_DEFAULT = "http://192.168.208.120:5001"
_RUTA_IDENTIFICACION_CACHE = None
_METODO_IDENTIFICACION_CACHE = None
_RUTA_ENROLADO_CACHE = None
_METODO_ENROLADO_CACHE = None


def _pifinger_url() -> str:
    return os.environ.get("PIFINGER_URL", _PIFINGER_URL_DEFAULT).rstrip("/")


def _timeout_lectura_red() -> int:
    valor = os.environ.get("PIFINGER_TIMEOUT", "5").strip()
    try:
        timeout = int(valor)
    except ValueError:
        timeout = 5
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


def _rutas_enrolado() -> list[str]:
    ruta_preferida = os.environ.get("PIFINGER_ENROLL_PATH", "").strip()

    if ruta_preferida:
        if not ruta_preferida.startswith("/"):
            ruta_preferida = f"/{ruta_preferida}"
        return [ruta_preferida]

    global _RUTA_ENROLADO_CACHE
    if _RUTA_ENROLADO_CACHE:
        return [_RUTA_ENROLADO_CACHE]

    return [
        "/register_fingerprint",
        "/enroll",
        "/enrolar",
        "/register",
        "/add",
        "/add_fingerprint",
    ]


def _metodos_enrolado() -> list[str]:
    metodo_preferido = os.environ.get("PIFINGER_ENROLL_METHOD", "").strip().upper()

    if metodo_preferido in {"GET", "POST"}:
        return [metodo_preferido]

    global _METODO_ENROLADO_CACHE
    if _METODO_ENROLADO_CACHE in {"GET", "POST"}:
        return [_METODO_ENROLADO_CACHE]

    return ["POST", "GET"]


def _timeout_enrolado_red() -> int:
    valor = os.environ.get("PIFINGER_ENROLL_TIMEOUT", "40").strip()
    try:
        timeout = int(valor)
    except ValueError:
        timeout = 40
    return max(10, timeout)


def _delay_vinculacion_segundos() -> int:
    valor = os.environ.get("PIFINGER_BIND_DELAY", "10").strip()
    try:
        segundos = int(valor)
    except ValueError:
        segundos = 10
    return max(0, segundos)


def _parsear_respuesta_identificacion(datos, huella_ids_validos=None):
    """Normaliza respuestas JSON/texto del servidor de huellas.

    Devuelve:
      (huella_id:int, None) cuando hay match con ID.
      (None, mensaje) cuando hay error o FAIL.
    """
    if isinstance(datos, dict):
        resultado = datos.get("result")

        # compare_fingerprint() devuelve True (boolean) — coincidencia sin ID
        if resultado is True or datos.get("matched") is True or datos.get("ok") is True:
            # Si hay un único ID registrado en la BD, es el único candidato posible
            if huella_ids_validos and len(huella_ids_validos) == 1:
                return next(iter(huella_ids_validos)), None
            return None, "MATCH_SIN_ID"

        resultado = str(resultado or "").strip()
        resultado_upper = resultado.upper()
        resultado_lower = resultado.lower()

        if resultado.strip().lower() in {"no data", "no_data", "waiting"}:
            return None, "NO_DATA"

        if "please input fingerprint to compare" in resultado_lower:
            return None, "NO_DATA"

        # Mensaje de proceso de registro en el buffer — ignorar durante identificación
        if "input fingerprint" in resultado_lower or "move finger away" in resultado_lower:
            return None, "NO_DATA"

        if datos.get("ok") and ("huella_id" in datos or "id" in datos or "fingerprint_id" in datos):
            huella_id = int(datos.get("huella_id", datos.get("id", datos.get("fingerprint_id"))))
            return huella_id, None

        # Soporta respuestas PiFinger como:
        # {'result': 'Matched!\n<R>PASS_0</R>\n<S>DS=7E</S>\n'}
        patron_embebido = re.search(r"PASS[_\s:|]*(\d+)", resultado_upper)
        if patron_embebido:
            return int(patron_embebido.group(1)), None

        if resultado_upper == "PASS":
            if "huella_id" in datos or "id" in datos or "fingerprint_id" in datos:
                huella_id = int(datos.get("huella_id", datos.get("id", datos.get("fingerprint_id"))))
                return huella_id, None
            return None, "El servidor devolvio PASS, pero sin ID de huella."

        if datos.get("ok") is False or "FAIL" in resultado_upper:
            return None, str(datos.get("error", datos.get("result", "FAIL")))

        return None, f"Respuesta inesperada: {datos}"

    texto = str(datos or "").strip()
    texto_upper = texto.upper()
    texto_lower = texto.lower()
    if "please input fingerprint to compare" in texto_lower:
        return None, "NO_DATA"
    # Respuesta de proceso de registro en el buffer — ignorar durante identificación
    if "input fingerprint" in texto_lower or "move finger away" in texto_lower:
        return None, "NO_DATA"
    if texto_upper.startswith("PASS"):
        # Soporta: PASS 7, PASS:7, PASS|7
        partes = texto.replace(":", " ").replace("|", " ").split()
        for parte in partes[1:]:
            if parte.isdigit():
                return int(parte), None
        patron_pass = re.search(r"PASS[_\s:|]*(\d+)", texto_upper)
        if patron_pass:
            return int(patron_pass.group(1)), None
        return None, "Respuesta PASS sin ID numerico."
    if texto_upper.startswith("FAIL"):
        return None, texto
    return None, f"Respuesta no reconocida: {texto}"


def _parsear_respuesta_enrolado(datos):
    """Normaliza respuestas del servidor de huellas para el alta/enrolado."""
    if isinstance(datos, dict):
        if str(datos.get("result", "")).strip().lower() in {"no data", "no_data", "waiting"}:
            return None, "NO_DATA"

        if datos.get("ok") and ("huella_id" in datos or "id" in datos or "fingerprint_id" in datos):
            huella_id = int(datos.get("huella_id", datos.get("id", datos.get("fingerprint_id"))))
            return huella_id, None

        resultado = str(datos.get("result", ""))
        resultado_upper = resultado.upper()

        # Respuesta de registro tipo "Input fingerprint #7 for the first capture..."
        patron_registro = re.search(r'input fingerprint\s*#(\d+)', resultado, re.IGNORECASE)
        if patron_registro:
            return int(patron_registro.group(1)), None

        if resultado_upper in {"PASS", "OK", "ENROLLED", "ENROLADO"}:
            if "huella_id" in datos or "id" in datos or "fingerprint_id" in datos:
                huella_id = int(datos.get("huella_id", datos.get("id", datos.get("fingerprint_id"))))
                return huella_id, None
            return None, "El servidor confirmó alta, pero sin ID de huella."

        if datos.get("ok") is False or resultado_upper in {"FAIL", "ERROR"}:
            return None, str(datos.get("error", datos.get("result", "FAIL")))

        return None, f"Respuesta inesperada: {datos}"

    texto = str(datos or "").strip()
    texto_upper = texto.upper()
    # Respuesta de registro en texto plano
    patron_registro_txt = re.search(r'input fingerprint\s*#(\d+)', texto, re.IGNORECASE)
    if patron_registro_txt:
        return int(patron_registro_txt.group(1)), None
    if texto_upper.startswith(("PASS", "OK", "ENROLLED", "ENROLADO")):
        partes = texto.replace(":", " ").replace("|", " ").split()
        for parte in partes[1:]:
            if parte.isdigit():
                return int(parte), None
        return None, "Respuesta de alta sin ID numerico."
    if texto_upper.startswith(("FAIL", "ERROR")):
        return None, texto
    return None, f"Respuesta no reconocida: {texto}"


def _modo_manual_habilitado() -> bool:
    valor = os.environ.get("ALLOW_MANUAL_HUELLA", "0").strip().lower()
    return valor in {"1", "true", "yes", "on"}


# ── Modos de identificación ─────────────────────────────────────────────────

def _identificar_via_red(huella_ids_validos=None) -> int | None:
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

                    print(f"[DEBUG] Respuesta cruda del sensor: {repr(crudo)}")
                    print(f"[DEBUG] Datos parseados: {datos}")
                    print(f"[DEBUG] IDs válidos en BD: {huella_ids_validos}")

                    huella_id, mensaje = _parsear_respuesta_identificacion(datos, huella_ids_validos)
                    print(f"[DEBUG] Parser → huella_id={huella_id}, mensaje={mensaje}")
                    if huella_id is not None:
                        if huella_ids_validos is not None and huella_id not in huella_ids_validos:
                            print(
                                f"Huella detectada. ID={huella_id} ignorado por no estar registrada en la base local."
                            )
                            ruta_activa = ruta
                            metodo_activo = metodo
                            _RUTA_IDENTIFICACION_CACHE = ruta
                            _METODO_IDENTIFICACION_CACHE = metodo
                            hubo_espera_sensor = True
                            break
                        print(f"Huella detectada. ID={huella_id}")
                        return huella_id
                    if mensaje == "NO_DATA" or mensaje == "MATCH_SIN_ID":
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
    db_manager = DBManager()
    profesores = db_manager.get_profesores()
    huella_ids_registrados = {
        profesor.huella_id for profesor in profesores if profesor.huella_id is not None
    }

    # Flujo principal: comparar huella en memoria del sensor remoto (Raspberry Pi)
    huella_id = _identificar_via_red(
        huella_ids_validos=huella_ids_registrados if huella_ids_registrados else None
    )

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

    for profesor in profesores:
        if profesor.huella_id == huella_id:
            print(f"Profesor identificado: {profesor.nombre}")
            return profesor.id

    print(f"Huella no registrada: ID {huella_id}")
    return None


def enrolar_huella_remota(profesor_id=None, huella_id_preferida=None):
    """Solicita al servidor de la Raspberry el alta de una nueva huella."""
    try:
        import json
        import urllib.error
        import urllib.request

        timeout = _timeout_enrolado_red()
        rutas = _rutas_enrolado()
        metodos = _metodos_enrolado()
        payload = {}
        if profesor_id is not None:
            payload["profesor_id"] = int(profesor_id)
        if huella_id_preferida is not None:
            payload["huella_id"] = int(huella_id_preferida)

        ultimo_error = "No se encontró un endpoint de enrolado válido en la Raspberry Pi."
        rutas_no_disponibles = 0
        total_intentos = 0

        print(f"Iniciando enrolado de huella (timeout: {timeout}s)...")
        for ruta in rutas:
            url = f"{_pifinger_url()}{ruta}"
            for metodo in metodos:
                total_intentos += 1
                try:
                    if metodo == "POST":
                        data = json.dumps(payload).encode("utf-8")
                        req = urllib.request.Request(
                            url=url,
                            data=data,
                            method="POST",
                            headers={"Content-Type": "application/json"},
                        )
                    else:
                        query = ""
                        if payload:
                            query = "?" + "&".join(f"{k}={v}" for k, v in payload.items())
                        req = urllib.request.Request(url=f"{url}{query}", method="GET")

                    print(f"Conectando con servidor de huellas: {url} [{metodo}]")
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        crudo = resp.read().decode()

                    try:
                        datos = json.loads(crudo)
                    except json.JSONDecodeError:
                        datos = crudo

                    huella_id, mensaje = _parsear_respuesta_enrolado(datos)
                    if huella_id is not None:
                        global _RUTA_ENROLADO_CACHE, _METODO_ENROLADO_CACHE
                        _RUTA_ENROLADO_CACHE = ruta
                        _METODO_ENROLADO_CACHE = metodo
                        print(f"Alta de huella completada. ID={huella_id}")
                        return huella_id, None

                    if mensaje and mensaje != "NO_DATA":
                        ultimo_error = f"{mensaje} en {ruta} [{metodo}]"

                except urllib.error.HTTPError as http_error:
                    if http_error.code in {404, 405}:
                        rutas_no_disponibles += 1
                        ultimo_error = f"Ruta/metodo no disponible: {ruta} [{metodo}]"
                        continue
                    try:
                        detalle = http_error.read().decode(errors="ignore").strip()
                    except Exception:
                        detalle = ""
                    ultimo_error = f"HTTP {http_error.code} en {ruta} [{metodo}] {detalle}".strip()
                except urllib.error.URLError as net_error:
                    ultimo_error = f"No se pudo conectar con {_pifinger_url()}: {net_error}"
                except Exception as ex:
                    ultimo_error = f"Error inesperado en enrolado: {ex}"

        if total_intentos > 0 and rutas_no_disponibles == total_intentos:
            return None, (
                "El servidor de huellas no expone endpoint de alta. "
                "Configura PIFINGER_ENROLL_PATH/PIFINGER_ENROLL_METHOD con la ruta real "
                "o usa la vinculación por huella existente."
            )

        return None, ultimo_error
    except Exception as ex:
        return None, f"Error preparando enrolado remoto: {ex}"


def registrar_huella_profesor(profesor_id, db_path="ies.db", huella_id_preferida=None):
    """Enrola huella en Raspberry Pi y guarda el huella_id en la base de datos."""
    db_manager = DBManager(db_path)
    profesor = db_manager.get_profesor_by_id(profesor_id)
    if profesor is None:
        return False, "Profesor no encontrado", None

    huella_id, error = enrolar_huella_remota(
        profesor_id=profesor_id,
        huella_id_preferida=huella_id_preferida,
    )

    # Fallback: algunos servidores PiFinger solo exponen /scan (identificación),
    # no alta remota. En ese caso vinculamos una huella ya existente al profesor.
    if huella_id is None and error and "no expone endpoint de alta" in error.lower():
        import time
        espera = _delay_vinculacion_segundos()
        if espera > 0:
            print(f"Esperando {espera}s antes de leer huella para vinculación...")
            time.sleep(espera)
        huella_id = _identificar_via_red()
        if huella_id is None:
            return False, (
                "No hay endpoint de alta y tampoco se detectó una huella existente para vincular."
            ), None

        actualizados = db_manager.set_profesor_huella_id(profesor_id, huella_id)
        if actualizados < 1:
            return False, "No se pudo guardar el ID de huella en la base de datos", None

        return True, (
            f"Servidor sin alta remota. Se vinculó la huella existente ID {huella_id} a {profesor.nombre}."
        ), huella_id

    if huella_id is None:
        return False, error or "No se pudo completar el enrolado de huella", None

    actualizados = db_manager.set_profesor_huella_id(profesor_id, huella_id)
    if actualizados < 1:
        return False, "No se pudo guardar el ID de huella en la base de datos", None

    return True, f"Huella registrada para {profesor.nombre}. ID: {huella_id}", huella_id


# ── Gestión del sensor (borrado) ────────────────────────────────────────────

def borrar_huella_sensor(huella_id: int) -> tuple[bool, str]:
    """Elimina una huella del sensor de la Raspberry Pi por su ID.

    Requiere que finger_server.py exponga GET /delete/<id> o GET /delete?id=<id>.
    """
    import urllib.request
    import urllib.error
    import json

    if not isinstance(huella_id, int) or huella_id < 0:
        return False, "ID de huella inválido"

    base = _pifinger_url()
    intentos = [
        (f"{base}/delete/{huella_id}", "GET"),
        (f"{base}/delete?id={huella_id}", "GET"),
        (f"{base}/remove/{huella_id}", "GET"),
        (f"{base}/remove?id={huella_id}", "GET"),
    ]

    ultimo_error = "El sensor no expone endpoint de borrado individual. Añade /delete/<id> a finger_server.py."
    for url, metodo in intentos:
        try:
            req = urllib.request.Request(url=url, method=metodo)
            with urllib.request.urlopen(req, timeout=10) as resp:
                crudo = resp.read().decode()
            try:
                datos = json.loads(crudo)
            except json.JSONDecodeError:
                datos = crudo

            if isinstance(datos, dict):
                resultado = str(datos.get("result", "")).upper()
                if datos.get("ok") or resultado in {"OK", "PASS", "DELETED"}:
                    return True, f"Huella ID={huella_id} eliminada del sensor"
                ultimo_error = str(datos.get("error", datos.get("result", "Error desconocido")))
            else:
                texto = str(datos).strip().upper()
                if texto.startswith(("OK", "PASS", "DELET")):
                    return True, f"Huella ID={huella_id} eliminada del sensor"
                ultimo_error = str(datos)

        except urllib.error.HTTPError as e:
            if e.code in {404, 405}:
                continue
            ultimo_error = f"HTTP {e.code} al intentar borrar huella"
        except Exception as e:
            ultimo_error = f"Error de conexión: {e}"

    return False, ultimo_error


def borrar_todas_huellas_sensor() -> tuple[bool, str]:
    """Elimina TODAS las huellas almacenadas en el sensor de la Raspberry Pi.

    Requiere que finger_server.py exponga GET /delete_all o GET /clear.
    """
    import urllib.request
    import urllib.error
    import json

    base = _pifinger_url()
    intentos = [
        (f"{base}/delete_all", "GET"),
        (f"{base}/clear", "GET"),
        (f"{base}/remove_all", "GET"),
        (f"{base}/reset", "GET"),
    ]

    ultimo_error = "El sensor no expone endpoint de borrado total. Añade /delete_all a finger_server.py."
    for url, metodo in intentos:
        try:
            req = urllib.request.Request(url=url, method=metodo)
            with urllib.request.urlopen(req, timeout=15) as resp:
                crudo = resp.read().decode()
            try:
                datos = json.loads(crudo)
            except json.JSONDecodeError:
                datos = crudo

            if isinstance(datos, dict):
                resultado = str(datos.get("result", "")).upper()
                if datos.get("ok") or resultado in {"OK", "PASS", "CLEARED", "DELETED"}:
                    return True, "Todas las huellas eliminadas del sensor"
                ultimo_error = str(datos.get("error", datos.get("result", "Error desconocido")))
            else:
                texto = str(datos).strip().upper()
                if texto.startswith(("OK", "PASS", "CLEAR", "DELET")):
                    return True, "Todas las huellas eliminadas del sensor"
                ultimo_error = str(datos)

        except urllib.error.HTTPError as e:
            if e.code in {404, 405}:
                continue
            ultimo_error = f"HTTP {e.code} al intentar borrar todas las huellas"
        except Exception as e:
            ultimo_error = f"Error de conexión: {e}"

    return False, ultimo_error
