# Base de Datos (SQLite)

El sistema utiliza SQLite como base de datos local.

## Elementos clave

- Archivo de base de datos: `ies.db`.
- Esquema SQL: `modules/db/schema.sql`.
- Inicializacion: `modules/db/init_db.py`.
- Acceso: `modules/db/db_manager.py`.

## Huellas

- La columna `profesores.huella_id` guarda el slot real del sensor PiFinger.
- La regla del sistema es `huella_id == slot del sensor`.
- Si la Raspberry devuelve `PASS_1`, se busca un profesor con `huella_id = 1`.
- Al asignar un `huella_id`, el gestor limpia ese mismo valor de otros profesores para evitar duplicados.

## Horarios de guardia

- Los tramos de guardia se almacenan tambien en la tabla `horarios`.
- Se identifican con `tipo = 'guardia'`; para compatibilidad, el sistema tambien reconoce `asignatura = 'Guardia'`.
- Un tramo de guardia habilita al profesor para cubrir ausencias en esa misma hora.
- Los tramos `Guardia` no cuentan como carga lectiva.

## Resultado de guardias

- La tabla `guardias` guarda el resultado calculado por fecha y hora.
- Cada fila conserva `id_profesor_ausente` e `id_profesor_cubre`.
- Las filas con `cubierta = 0` son propuestas calculadas por el motor.
- Las filas con `cubierta = 1` representan guardias confirmadas manualmente.
