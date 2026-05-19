# Módulo Flask

La aplicación web está implementada con Flask.

## Rutas principales

- `/`: página de inicio (GET)
- `/presencia`: vista de presencia (GET)
- `/presencia/confirmar-presencia-huella`: endpoint JSON para identificar huella y registrar presencia automáticamente (POST)
- `/presencia/enrolar`: endpoint JSON para enrolar huellas (POST)
- `/guardias`: vista de guardias (GET)
- `/guardias/registrar`: registro manual de guardia desde la UI (POST)
