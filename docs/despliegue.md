# Despliegue en Raspberry Pi

Guia base de despliegue en Raspberry Pi.

## Recomendaciones

- Usar Python 3.9+.
- Instalar dependencias del proyecto.
- Configurar el puerto serie del lector de huella.
- Configurar un servicio para arranque automatico si se usa en produccion.

## Servidor de huellas en Raspberry

El despliegue actual usa una API Flask separada en la Raspberry Pi para hablar con el sensor PiFinger.

Archivos que deben estar en la Raspberry:

- `api_finger.py`
- `fingerprint.py`

El servidor debe exponer:

- `GET /health`
- `GET /register/<nombre>?slot=N`
- `GET /scan`

La aplicacion principal en Windows debe apuntar a la Raspberry con:

```powershell
$env:PIFINGER_URL = "http://<ip-raspberry>:5001"
```

El registro debe usar el comando del sensor `RegisterOneFp=N`, no el registro generico, para evitar que todas las huellas se guarden en el slot `0`.

## Prueba rapida

1. Arranca la API en la Raspberry.
2. Comprueba `/health`.
3. Registra una primera huella y confirma que devuelve `slot: 0`.
4. Registra una segunda huella y confirma que devuelve `slot: 1`.
5. Escanea cada dedo y confirma que se reciben `PASS_0` y `PASS_1`.
