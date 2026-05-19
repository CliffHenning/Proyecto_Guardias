# Sistema de Gestión de Guardias

Aplicación web Flask para la gestión automática de guardias escolares con identificación por huella dactilar.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.3-green)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## Requisitos previos

- Python 3.9 o superior
- Git

## Instalación y puesta en marcha

```bash
# 1. Clona el repositorio
git clone https://github.com/CliffHenning/Proyecto_Guardias.git
cd Proyecto_Guardias

# 2. Crea el entorno virtual
python -m venv .venv

# 3. Actívalo (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# 4. Instala las dependencias
pip install -r requirements-presence.txt

# 5. Inicializa la base de datos (crea ies.db en la raíz del proyecto)
python -m modules.db.init_db

# 6. Arranca la aplicación
python app.py
```

La aplicación estará disponible en `http://127.0.0.1:5000`.

## Rutas principales

| Ruta | Método | Descripción |
|------|--------|-------------|
| `/` | GET | Página de inicio |
| `/presencia` | GET | Vista de control de presencia (UI) |
| `/presencia/confirmar-presencia-huella` | POST | Identifica huella y registra presencia automáticamente (JSON) |
| `/presencia/enrolar` | POST | Enrola huella para un profesor y guarda `huella_id` (JSON) |
| `/presencia/borrar-huella-bd` | POST | Borra huella en BD (flujo UI con redirect + flash) |
| `/guardias` | GET | Vista de guardias (UI) |
| `/guardias/registrar` | POST | Registra una guardia confirmada manualmente (UI) |
| `/horario` | GET | Vista de horario con ausencias (UI) |


## Horarios con guardia

En la tabla `horarios`, los tramos de guardia se representan con la asignatura `Guardia`. Esos tramos cuentan como disponibilidad para cubrir ausencias, pero no como carga lectiva ordinaria.

## Flujo actual de huella (registro y escaneo)

El sistema separa:
- **App principal (Windows):** Flask + lógica de presencia/guardias.
- **Servidor de huellas (Raspberry Pi):** API para identificar y enrolar huellas (PiFinger).

Regla importante:

```text
huella_id == slot del sensor
```

En la base de datos (tabla `profesores`), `profesores.huella_id` guarda el **slot real** del sensor.

### 1) Registro (enrolar huella)

Cuando se pulsa el enrolado desde la UI, la app Flask hace:

1. Se solicita un `profesor_id` (y opcional `huella_id_preferida`) vía `POST /presencia/enrolar`.
2. `registrar_huella_profesor()` calcula el **siguiente slot libre** consultando `ies.db`, o usa el `huella_id_preferida` si se proporciona.
3. Se llama a la Raspberry para enrolar (endpoint configurable vía variables de entorno). El servicio interpreta el slot devuelto por el PiFinger.
4. Se guarda el slot resultante en `profesores.huella_id`.

### 2) Escaneo (confirmar presencia)

Cuando se confirma presencia automática, la app hace:

1. Llamada `POST /presencia/confirmar-presencia-huella`.
2. `identificar_huella()` lee la huella desde la Raspberry (endpoint configurable) y devuelve el `huella_id` (slot) detectado.
3. Se busca el profesor con `DB: profesores.huella_id == huella_id`.
4. Se registra presencia con alternancia:
   - si el último estado era `entrada` ⇒ nuevo registro `salida`
   - si no hay entrada activa ⇒ nuevo registro `entrada`

### Parámetros soportados

**En API JSON (app principal):**
- `POST /presencia/enrolar`
  - `profesor_id` (int, requerido)
  - `huella_id_preferida` (int, opcional)
- `POST /presencia/confirmar-presencia-huella`
  - sin body obligatorio

**En el servidor/cliente de huellas (Raspberry / huella_service):**
- `PIFINGER_URL` (string)
- `PIFINGER_IDENTIFY_PATH` / `PIFINGER_IDENTIFY_METHOD`
- `PIFINGER_ENROLL_PATH` / `PIFINGER_ENROLL_METHOD`
- `PIFINGER_TIMEOUT`
- `PIFINGER_ENROLL_TIMEOUT`
- `PIFINGER_PORT`
- `ALLOW_MANUAL_HUELLA` (opcional, desarrollo)


## Variables de entorno

El método de identificación del profesorado se controla mediante la variable de entorno `METODO_PRESENCIA`:

```bash
# Modo huella (por defecto)
$env:METODO_PRESENCIA = "huella"
```

Si no se define, el sistema usa `huella` como valor predeterminado.

### Servidor de huellas Raspberry Pi

La URL del servidor remoto se configura con `PIFINGER_URL`:

```powershell
$env:PIFINGER_URL = "http://192.168.208.120:5001"
```

Si no se define, se usa el valor por defecto configurado en `modules/presencia/huella_service.py`.

#### Identificación (scan/match)

- Rutas (path) intentadas para identificación (en orden): por defecto intenta varias opciones como `GET /scan`, `GET /identify`, etc.
- Puedes forzar path/método con:

```powershell
$env:PIFINGER_IDENTIFY_PATH = "/scan"          # opcional
$env:PIFINGER_IDENTIFY_METHOD = "GET"         # GET o POST (opcional)
```

#### Enrolado (register)

- Rutas (path) intentadas para enrolado (en orden): por defecto intenta varias opciones como `POST /register_fingerprint`, `POST /enroll`, etc.
- Puedes forzar path/método con:

```powershell
$env:PIFINGER_ENROLL_PATH = "/register_fingerprint"  # opcional
$env:PIFINGER_ENROLL_METHOD = "POST"                  # GET o POST (opcional)
```


### Modo de identificación local para Raspberry Pi

Si instalas y ejecutas la app directamente en la Raspberry Pi con un lector de huella compatible, puedes forzar el uso del sensor serie local:

```bash
# Usa el sensor serie local en lugar de depender de un servidor remoto
$env:PIFINGER_MODE = "local"
# o
$env:PIFINGER_FORCE_LOCAL = "1"
```

Esto hace que la aplicación intente usar `pyfingerprint` y el puerto serie local antes de probar cualquier servidor remoto.

## Ejecutar los tests

```bash
# Todos los tests
python -m pytest tests/ -v

# Con informe HTML
python -m pytest tests/ --html=report.html --self-contained-html
```

Tambien puedes validar con un solo comando usando el script de PowerShell:

```powershell
# Solo tests (recomendado para comprobacion rapida)
.\scripts\validar.ps1

# Tests + informe HTML
.\scripts\validar.ps1 -HtmlReport

# Tests + docs MkDocs
.\scripts\validar.ps1 -Docs
```

## Documentación técnica

```bash
# Servidor local de documentación (requiere mkdocs y mkdocs-material)
pip install mkdocs mkdocs-material
python -m mkdocs serve
```

La documentación estará disponible en `http://127.0.0.1:8000`.

## Estructura del proyecto

```
proyecto_guardias/
├── app.py                  # Punto de entrada Flask
├── mkdocs.yml              # Configuración de la documentación
├── requirements-presence.txt
├── modules/
│   ├── db/                 # Base de datos SQLite (DBManager, modelos, esquema)
│   ├── guardias/           # Motor de cálculo de guardias y reglas de negocio
│   └── presencia/          # Identificación del profesorado (huella)
├── templates/              # Plantillas HTML
├── static/                 # Archivos estáticos
├── docs/                   # Fuente de la documentación MkDocs
└── tests/                  # Suite de tests pytest
```

## Ejemplos de uso (curl) y respuestas JSON

### Confirmar presencia automática

`POST /presencia/confirmar-presencia-huella`

Ejemplo:

```bash
curl -sS -X POST http://127.0.0.1:5000/presencia/confirmar-presencia-huella \
  -H "Content-Type: application/x-www-form-urlencoded"
```

Respuestas:

- **200** (huella identificada y profesor encontrado):

```json
{
  "ok": true,
  "tipo": "entrada",
  "nombre": "Nombre Profesor",
  "profesor_id": 1,
  "huella_id": 0,
  "mensaje": "Nombre Profesor: presente"
}
```

- **400** (no se detecta ninguna huella):

```json
{"ok": false, "mensaje": "No se detectó ninguna huella"}
```

- **404** (huella detectada pero no registrada en BD):

```json
{"ok": false, "mensaje": "Huella no registrada (3)"}
```

### Enrolar huella

`POST /presencia/enrolar`

Ejemplo (form-urlencoded):

```bash
curl -sS -X POST http://127.0.0.1:5000/presencia/enrolar \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "profesor_id=1&huella_id_preferida=2"
```

Respuestas:

- **200** (éxito):

```json
{
  "ok": true,
  "message": "Huella registrada para Ana. ID: 2",
  "error": null,
  "huella_id": 2
}
```

- **200** (fallo controlado por validación de negocio):

```json
{
  "ok": false,
  "message": "Profesor no encontrado",
  "error": "Profesor no encontrado",
  "huella_id": null
}
```

- **500** (error inesperado):

```json
{"ok": false, "message": "<detalle>"}
```

### Seguridad: bloqueo de comandos destructivos

La aplicación Flask **no expone endpoints de borrado destructivo** mediante la API JSON de identificación/escaneo.

- El endpoint `/presencia/borrar-huella-bd` es un flujo de UI: borra `profesores.huella_id` (no borra huellas del sensor) y redirige con `flash`.
- Las operaciones destructivas sobre el dispositivo PiFinger (p.ej. borrar huellas del sensor) se gestionan como utilidades internas del módulo `modules/presencia/huella_service.py` y no se publican como endpoints remotos sin control.

Si necesitas operaciones destructivas en el sensor, deben ejecutarse manualmente (scripts) y no vía peticiones remotas sin autenticación.

## Notas sobre hardware

El lector de huella utiliza comunicación serie en la Raspberry Pi. Para el flujo remoto actual deben copiarse a la Raspberry los archivos compatibles `api_finger.py` y `fingerprint.py`, donde `register_fingerprint(slot_id)` usa el comando `RegisterOneFp=<slot>`.

Si ejecutas la aplicación en la Raspberry Pi y tu sensor es compatible, instala `pyfingerprint` en la Pi y usa el modo local con `PIFINGER_MODE=local` o `PIFINGER_FORCE_LOCAL=1`.

Si el módulo de huella no soporta matching interno, el servidor local debe usar una librería compatible con tu modelo de sensor y los comandos adecuados (`GenImg`, `Img2Tz`, `Search`, `Store`, etc.).
