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

| Ruta | Descripción |
|------|-------------|
| `/` | Página de inicio |
| `/presencia` | Registro de presencia del profesorado |
| `/guardias` | Visualización del cálculo de guardias |

## Horarios con guardia

En la tabla `horarios`, los tramos de guardia se representan con la asignatura `Guardia`. Esos tramos cuentan como disponibilidad para cubrir ausencias, pero no como carga lectiva ordinaria.

## Flujo actual de huella

El sistema usa un servidor Flask en la Raspberry Pi para hablar con el lector PiFinger. La aplicacion principal en Windows llama a ese servidor por HTTP.

Regla importante:

```text
huella_id == slot del sensor
```

No hay un identificador global adicional. Si el sensor registra una huella en el slot `0`, SQLite guarda `huella_id = 0`. Si la siguiente huella se registra en el slot `1`, SQLite guarda `huella_id = 1`.

Flujo de registro:

1. Windows calcula el siguiente slot libre segun los `huella_id` ya guardados en `ies.db`.
2. Windows llama a la Raspberry con `/register/<nombre>?slot=N`.
3. La Raspberry registra la huella con `RegisterOneFp=N`.
4. La Raspberry devuelve `slot: N`.
5. Windows guarda ese valor en `profesores.huella_id`.

Flujo de escaneo:

1. Windows llama a `/scan`.
2. La Raspberry devuelve `PASS_N`.
3. Windows busca directamente `profesor.huella_id == N`.
4. Si el profesor estaba fuera, se registra `entrada`; si estaba presente, se registra `salida`.

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

## Notas sobre hardware

El lector de huella utiliza comunicacion serie en la Raspberry Pi. Para el flujo remoto actual deben copiarse a la Raspberry los archivos compatibles `api_finger.py` y `fingerprint.py`, donde `register_fingerprint(slot_id)` usa el comando `RegisterOneFp=<slot>`.

Si ejecutas la aplicación en la Raspberry Pi y tu sensor es compatible, instala `pyfingerprint` en la Pi y usa el modo local con `PIFINGER_MODE=local` o `PIFINGER_FORCE_LOCAL=1`.

Si el módulo de huella no soporta matching interno, el servidor local debe usar una librería compatible con tu modelo de sensor y los comandos adecuados (`GenImg`, `Img2Tz`, `Search`, `Store`, etc.).
