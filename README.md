# 🛡️ Proyecto Guardias

Aplicación Flask para gestión de guardias. API REST con rutas funcionales.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.3-green)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## 🚀 Rápido inicio

```bash
# Clona el repo
git clone https://github.com/CliffHenning/Proyecto_Guardias.git
cd Proyecto_Guardias

# Crea entorno virtual
python -m venv .venv

# Activa (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Instala dependencias
python -m pip install -r requirements.txt

# Ejecuta la app
python app.py

# Módulo de Presencia

Este módulo implementa el control de presencia del profesorado utilizando tres métodos de identificación hardware diferentes.

## Métodos de Identificación

### 1. RFID (Por defecto)
- **Hardware**: RFID HAT para Raspberry Pi (SKU 20003) basado en MFRC522
- **Comunicación**: SPI
- **Librería**: `mfrc522`
- **Funcionamiento**: Lee UID de tarjetas RFID/NFC y lo mapea al profesor_id

### 2. Huella Dactilar
- **Hardware**: PiFinger (SKU 21253)
- **Comunicación**: UART a 9600 bps
- **Librería**: `pyserial`
- **Funcionamiento**: Envía comandos de identificación y recibe ID de huella

### 3. Reconocimiento Facial
- **Hardware**: Raspberry Pi Camera Module 3
- **Librerías**: `picamera2`, `face_recognition`
- **Funcionamiento**: Captura imagen, extrae embeddings faciales y compara con referencias

## Configuración

El método se selecciona mediante la variable de entorno `METODO_PRESENCIA`:
- `METODO_PRESENCIA=rfid` (por defecto)
- `METODO_PRESENCIA=huella`
- `METODO_PRESENCIA=facial`

## Instalación de Dependencias

### En Raspberry Pi:
```bash
pip install mfrc522 pyserial face-recognition picamera2
```

### En desarrollo (Windows):
Las librerías hardware no son necesarias. El sistema permite entrada manual para testing.

## Funcionamiento

1. **Identificación**: El profesor se identifica mediante el método configurado
2. **Registro**: Se registra entrada/salida automáticamente alternando entre los dos estados
3. **Visualización**: La interfaz web muestra el estado actual de todos los profesores

## Desarrollo

En modo desarrollo (Windows), los servicios permiten entrada manual:
- RFID: Ingresar UID manualmente
- Huella: Ingresar ID de huella manualmente
- Facial: Ingresar ID facial manualmente

## Base de Datos

Los registros se almacenan en la tabla `presencia` con:
- `profesor_id`: ID del profesor
- `tipo`: 'entrada' o 'salida'
- `timestamp`: Fecha y hora automática
