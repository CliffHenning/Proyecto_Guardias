# Base de Datos (SQLite)

El sistema utiliza SQLite como base de datos local.

## Elementos clave

- Archivo de base de datos: ies.db
- Esquema SQL: modules/db/schema.sql
- Inicialización: modules/db/init_db.py
- Acceso: modules/db/db_manager.py

## Horarios de guardia

- Los tramos de guardia se almacenan también en la tabla `horarios`.
- Se identifican con `tipo = 'guardia'`; para compatibilidad, el sistema también reconoce `asignatura = 'Guardia'`.
- Un tramo de guardia habilita al profesor para cubrir ausencias en esa misma hora.
- Los tramos `Guardia` no cuentan como carga lectiva.

## Resultado de guardias

- La tabla `guardias` guarda el resultado calculado por fecha y hora.
- Cada fila conserva `id_profesor_ausente` e `id_profesor_cubre`.
- Las filas con `cubierta = 0` son propuestas calculadas por el motor.
- Las filas con `cubierta = 1` representan guardias confirmadas manualmente.
