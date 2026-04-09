# Sistema de Gestión de Guardias

Aplicación web Flask para la gestión automática de guardias escolares con identificación por RFID.

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

## Variable de entorno

El método de identificación del profesorado se controla mediante la variable de entorno `METODO_PRESENCIA`:

```bash
# Modo RFID (por defecto, requiere hardware en Raspberry Pi)
$env:METODO_PRESENCIA = "rfid"
```

Si no se define, el sistema usa `rfid` como valor predeterminado.

## Ejecutar los tests

```bash
# Todos los tests
python -m pytest tests/ -v

# Con informe HTML
python -m pytest tests/ --html=report.html --self-contained-html
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
│   └── presencia/          # Identificación del profesorado (RFID)
├── templates/              # Plantillas HTML
├── static/                 # Archivos estáticos
├── docs/                   # Fuente de la documentación MkDocs
└── tests/                  # Suite de tests pytest
```

## Notas sobre hardware

El módulo RFID (`mfrc522`) solo funciona en Raspberry Pi. En entornos de desarrollo Windows el sistema opera igualmente; los tests cubren todas las rutas sin necesidad de hardware físico.
