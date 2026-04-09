# Arquitectura del sistema

Resumen de la arquitectura modular del proyecto:

- Capa web con Flask
- Capa de negocio para guardias y presencia
- Capa de datos con SQLite y DBManager

## Componentes principales

- app.py: punto de entrada web
- modules/guardias: motor y reglas de cálculo
- modules/presencia: lógica de identificación
- modules/db: acceso y modelo de datos
