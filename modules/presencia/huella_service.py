import os
import platform
import re

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

    return ["GET", "POST"]


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


def _extraer_id_de_resultado(texto):
    if texto is None:
        return None
    texto = str(texto or "").strip()
    if not texto:
        return None

    texto_upper = texto.upper()
    match = re.search(r'^(?:PASS|OK|ENROLLED|ENROLADO)[_\s:|]*(\d+)', texto_upper)
    if match:
        return int(match.group(1))
    return None


def _extraer_slot_de_resultado(valor):
    """Extrae el slot real del sensor: 0, "#0", "slot 0", "PASS_0", etc."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor

    texto = str(valor or "").strip()
    if not texto:
        return None

    if texto.isdigit():
        return int(texto)

    for patron in (
        r"#\s*(\d+)",
        r"\bslot(?:_id)?\b[\s:=#-]*(\d+)",
        r"\b(?:huella_id|fingerprint_id|id)\b[\s:=#-]*(\d+)",
    ):
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return _extraer_id_de_resultado(texto)


def _texto_sensor(valor):
    if valor is None:
        return ""
    if isinstance(valor, (list, tuple)):
        return "\n".join(_texto_sensor(item) for item in valor)
    if isinstance(valor, dict):
        return "\n".join(_texto_sensor(item) for item in valor.values())
    return str(valor or "")


def _parsear_respuesta_identificacion(datos, huella_ids_validos=None):
    """Normaliza respuestas JSON/texto del servidor de huellas.

    Devuelve:
      (huella_id:int, None) cuando hay match con ID.
      (None, mensaje) cuando hay error o FAIL.
    """
    if isinstance(datos, dict):
        resultado = datos.get("result")
        texto_completo = _texto_sensor(
            [datos.get("result"), datos.get("raw"), datos.get("message"), datos.get("error")]
        )
        texto_completo_upper = texto_completo.upper()
        texto_completo_lower = texto_completo.lower()

        patron_pass_completo = re.search(r"PASS[_\s:|]*(\d+)", texto_completo_upper)
        if patron_pass_completo:
            return int(patron_pass_completo.group(1)), None

        if (
            "please input fingerprint to compare" in texto_completo_lower
            or "input fingerprint" in texto_completo_lower
            or "move finger away" in texto_completo_lower
            or "cancel" in texto_completo_lower
        ):
            return None, "NO_DATA"

        # match genérico del servidor
        # OJO: algunos servidores devuelven ok=true/Matched!... con un PASS_<n> embebido.
        # En ese caso, NO debemos retornar MATCH_SIN_ID sin intentar extraer el número.
        if resultado is True or datos.get("matched") is True or datos.get("ok") is True:
            # Prioridad 1: extraer PASS_<n> del resultado (p.ej. "Matched!\n<R>PASS_0</R>")
            # para obtener huella_id real.
            resultado_raw = str(datos.get("raw", datos.get("result", "")) or "").strip()
            if resultado_raw:
                m_pass = re.search(r"PASS[_\s:|]*(\d+)", resultado_raw.upper())
                if m_pass:
                    return int(m_pass.group(1)), None

            # Prioridad 2: si el sistema solo permite un candidato posible, usarlo.
            if huella_ids_validos and len(huella_ids_validos) == 1:
                return next(iter(huella_ids_validos)), None

            # Prioridad 3: match sin ID numérico explícito.
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

        for clave in ("slot", "slot_id", "huella_id", "id", "fingerprint_id"):
            huella_id = _extraer_slot_de_resultado(datos.get(clave))
            if huella_id is not None:
                return huella_id, None

        huella_id = _extraer_slot_de_resultado(resultado)
        if huella_id is not None:
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

        if (
            datos.get("ok") is False
            or "FAIL" in resultado_upper
            or "FAIL" in texto_completo_upper
            or "MISMATCH" in texto_completo_upper
            or "NO COINCIDE" in texto_completo_upper
        ):
            return None, "NO_MATCH"

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
        return None, "NO_MATCH"
    if "MISMATCH" in texto_upper or "NO COINCIDE" in texto_upper:
        return None, "NO_MATCH"
    return None, f"Respuesta no reconocida: {texto}"


def _parsear_respuesta_enrolado(datos):
    """Normaliza respuestas del servidor de huellas para el alta/enrolado."""
    if isinstance(datos, dict):
        if str(datos.get("result", "")).strip().lower() in {"no data", "no_data", "waiting"}:
            return None, "NO_DATA"

        for clave in ("slot", "slot_id", "huella_id", "id", "fingerprint_id"):
            huella_id = _extraer_slot_de_resultado(datos.get(clave))
            if huella_id is not None:
                return huella_id, None

        resultado = str(datos.get("result", ""))
        resultado_upper = resultado.upper()

        huella_id = _extraer_slot_de_resultado(resultado)
        if huella_id is not None:
            return huella_id, None

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
    huella_id = _extraer_slot_de_resultado(texto)
    if huella_id is not None:
        return huella_id, None
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
                        # Normalizar tipos por seguridad (int vs str)
                        try:
                            huella_id_int = int(huella_id)
                        except (TypeError, ValueError):
                            huella_id_int = None

                        if huella_id_int is None:
                            ultimo_error = f"ID de huella invalido: {huella_id}"
                            continue

                        if huella_ids_validos is not None:
                            ids_locales = {int(x) for x in huella_ids_validos}
                            if huella_id_int not in ids_locales:
                                print(
                                    f"Huella detectada. ID={huella_id_int} ignorado por no estar registrada en la base local."
                                )
                                ruta_activa = ruta
                                metodo_activo = metodo
                                _RUTA_IDENTIFICACION_CACHE = ruta
                                _METODO_IDENTIFICACION_CACHE = metodo
                                hubo_espera_sensor = True
                                break

                        print(f"Huella detectada. ID={huella_id_int}")
                        return huella_id_int
                    if mensaje in {"NO_DATA", "MATCH_SIN_ID", "NO_MATCH"}:
                        ruta_activa = ruta
                        metodo_activo = metodo
                        _RUTA_IDENTIFICACION_CACHE = ruta
                        _METODO_IDENTIFICACION_CACHE = metodo
                        hubo_espera_sensor = True
                        if mensaje == "NO_MATCH":
                            ultimo_error = "No coincide ninguna huella registrada durante la ventana de lectura."
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
        print("Revise red, IP real de la Pi y que el servidor server.py esté activo.")
        return False
    except Exception as e:
        print(f"FAIL: Error inesperado durante la prueba ({e}).")
        return False

# ── Función principal ───────────────────────────────────────────────────────

def borrar_huellas_remotas():
    """Solicita al servidor PiFinger borrar las huellas almacenadas en el sensor."""
    import json
    import urllib.error
    import urllib.request

    rutas = ["/delete_all", "/clear", "/reset", "/borrar_huellas"]
    ultimo_error = None

    for ruta in rutas:
        url = f"{_pifinger_url()}{ruta}"
        try:
            req = urllib.request.Request(url=url, method="POST")
            with urllib.request.urlopen(req, timeout=_timeout_lectura_red()) as resp:
                crudo = resp.read().decode(errors="ignore")

            try:
                datos = json.loads(crudo)
            except json.JSONDecodeError:
                datos = crudo

            if isinstance(datos, dict):
                ok = datos.get("ok") is True or str(datos.get("result", "")).upper() == "OK"
                if ok:
                    return True, "Se borraron las huellas del sensor."
                ultimo_error = datos.get("error") or datos.get("message") or str(datos)
            elif "OK" in str(datos).upper() or "PASS" in str(datos).upper():
                return True, "Se borraron las huellas del sensor."
            else:
                ultimo_error = str(datos)

        except urllib.error.HTTPError as http_error:
            if http_error.code in {404, 405}:
                ultimo_error = f"Ruta/metodo no disponible: {ruta}"
                continue
            ultimo_error = f"HTTP {http_error.code} al borrar huellas"
        except Exception as ex:
            ultimo_error = str(ex)

    return False, ultimo_error or "No se pudieron borrar las huellas del sensor."


def _siguiente_slot_libre(profesores, limite=128):
    usados = {
        int(profesor.huella_id)
        for profesor in profesores
        if profesor.huella_id is not None
    }
    for slot in range(limite):
        if slot not in usados:
            return slot
    return None


def identificar_huella(db_path: str = "ies.db"):

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
    print(f"[HUELLA][DEBUG] DB_PATH usado en identificar_huella: {db_path}")
    db_manager = DBManager(db_path)
    profesores = db_manager.get_profesores()
    huella_ids_registrados = {
        int(profesor.huella_id) for profesor in profesores if profesor.huella_id is not None
    }
    print(
        f"[HUELLA][DEBUG] Profesores activos leidos: {len(profesores)}; "
        f"huella_ids validos: {sorted(huella_ids_registrados)}"
    )
    if not huella_ids_registrados:
        print(
            "[HUELLA][DEBUG] La BD no devolvio huella_id activos. "
            f"Revise DB_PATH={db_path} y que profesores.huella_id no este vacio."
        )

    # Flujo principal: comparar huella en memoria del sensor remoto (Raspberry Pi)
    # Importante: no pasar None para evitar saltos silenciosos en la validación.
    huella_id = _identificar_via_red(
        huella_ids_validos=huella_ids_registrados
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

    profesor = db_manager.get_profesor_por_huella_id(huella_id)
    if profesor is not None:
        print(f"Profesor identificado: {profesor.nombre} (huella_id={huella_id})")
        return int(huella_id)

    print(f"Huella no registrada: ID {huella_id}")
    return None


def enrolar_huella_remota(profesor_id=None, huella_id_preferida=None, db_path: str = "ies.db"):

    """Alta simplificada: el PiFinger expone /register/<nombre> en GET."""
    if profesor_id is None:
        return None, "Profesor no proporcionado"

    db_manager = DBManager(db_path)
    profesor = db_manager.get_profesor_by_id(int(profesor_id))
    if profesor is None:
        return None, "Profesor no encontrado"

    import json
    import urllib.error
    import urllib.request
    from urllib.parse import quote, urlencode

    url = f"{_pifinger_url()}/register/{quote(str(profesor.nombre))}"
    if huella_id_preferida is not None:
        url = f"{url}?{urlencode({'slot': int(huella_id_preferida)})}"
    try:
        timeout = _timeout_enrolado_red()
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            crudo = resp.read().decode(errors="ignore")

        try:
            datos = json.loads(crudo)
        except json.JSONDecodeError:
            datos = crudo

        huella_id, error = _parsear_respuesta_enrolado(datos)
        if huella_id is not None:
            return int(huella_id), None

        if isinstance(datos, dict) and datos.get("ok") is True:
            return None, f"Alta OK pero sin slot en respuesta: {datos}"

        # error conocido
        if isinstance(datos, dict):
            return None, datos.get("error") or datos.get("message") or error or str(datos)

        return None, error or str(datos)

    except urllib.error.HTTPError as ex:
        try:
            detalle = ex.read().decode(errors="ignore").strip()
        except Exception:
            detalle = ""
        mensaje = f"HTTP {ex.code} llamando a endpoint /register/<nombre>"
        if detalle:
            mensaje = f"{mensaje}: {detalle}"
        return None, mensaje
    except Exception as ex:
        return None, f"Error llamando a endpoint /register/<nombre>: {ex}"



def registrar_huella_profesor(profesor_id, db_path="ies.db", huella_id_preferida=None):

    """Enrola huella en Raspberry Pi y guarda el huella_id en la base de datos."""
    db_manager = DBManager(db_path)
    profesor = db_manager.get_profesor_by_id(profesor_id)
    if profesor is None:
        return False, "Profesor no encontrado", None

    if huella_id_preferida is None:
        huella_id_preferida = _siguiente_slot_libre(db_manager.get_profesores())
    if huella_id_preferida is None:
        return False, "No quedan slots libres de huella en la base de datos", None

    huella_id, error = enrolar_huella_remota(
        profesor_id=profesor_id,
        huella_id_preferida=huella_id_preferida,
        db_path=db_path,
    )

    # IMPORTANTE: para evitar escaneos adicionales durante el registro,
    # no hacemos fallback por vinculación vía /scan.
    if huella_id is None:
        return False, error or "No se pudo completar el enrolado de huella", None


    actualizados = db_manager.set_profesor_huella_id(profesor_id, huella_id)
    if actualizados < 1:
        return False, "No se pudo guardar el ID de huella en la base de datos", None

    # IMPORTANTE: no hacemos verificación adicional del ID tras el enrolado.
    # El servidor PiFinger ya devuelve el ID asignado durante el registro.
    final_message = f"Huella registrada para {profesor.nombre}. ID: {huella_id}"

    return True, final_message, huella_id

