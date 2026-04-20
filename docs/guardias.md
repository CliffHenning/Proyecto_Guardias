# Motor de cálculo de guardias

El módulo de guardias calcula cobertura de ausencias según reglas de prioridad.

## Flujo general

1. Detectar profesores ausentes
2. Ver qué clases quedan descubiertas
3. Buscar profesores disponibles con `Guardia` en esa misma hora
4. Aplicar ranking por criterios de prioridad
5. Insertar el resultado calculado en la tabla `guardias`
6. Mostrar las aulas a cubrir y permitir la confirmación manual del profesor que realizará la guardia

## Criterios del ranking

El ranking de profesorado para guardias se ordena de mayor a menor prioridad con estos criterios jerárquicos:

1. Menor número de guardias acumuladas
2. Menor número de guardias en la semana actual
3. Menor carga lectiva

## Datos de aulas sin profesor

Cuando se detecta una ausencia con horario asociado, el sistema genera una guardia con los datos necesarios para identificar el aula sin profesor:

1. Aula afectada
2. Asignatura impartida en esa hora
3. Profesor ausente
4. Hora que requiere cobertura

La aplicación conserva internamente la hora como índice numérico para simplificar la lógica y la base de datos, pero en la interfaz la muestra con el tramo real del instituto. De lunes a viernes se usan estos once tramos:

1. 1: 8:45-9:45
2. 2: 9:35-10:25
3. 3: 10:25-11:15
4. 4: 11:45-12:35
5. 5: 12:35-13:25
6. 6: 13:25-14:15
7. 7: 15:40-16:30
8. 8: 16:30-17:20
9. 9: 17:20-18:10
10. 10: 18:10-19:00
11. 11: 19:20-20:10

La asociación entre el número de hora y su tramo real se centraliza en una función de utilidad, de forma que la base de datos puede seguir trabajando con `1..11` y la interfaz mostrar siempre el texto correcto.

Para facilitar la depuración, si una ausencia no tiene horario detallado cargado para ese día y hora, el sistema sigue generando una guardia pendiente con valores de apoyo:

1. Aula por determinar
2. Sin asignatura

## Registro de guardia realizada

Desde la vista de guardias se muestra cada aula calculada junto con un desplegable de profesores disponibles para esa hora, ordenados por prioridad.

Antes del registro manual, el motor ya propone un profesor para cada ausencia cruzando:

1. Las ausencias activas de esa hora
2. Los profesores que tienen `Guardia` en esa misma hora
3. El ranking de prioridad para evitar reutilizar al mismo profesor en dos aulas simultáneas

Ese resultado se persiste en `guardias` con `cubierta = 0`, `id_profesor_ausente` e `id_profesor_cubre`.

Al pulsar el boton de registro:

1. Se toma el profesor seleccionado manualmente en la interfaz
2. Se almacena la guardia en la tabla `guardias` como cubierta, incluyendo el aula y la asignatura mostradas en la vista
3. Se incrementan los contadores `guardias_acumuladas` y `guardias_semana` del profesor elegido
4. La vista se recarga mostrando el estado de la guardia como registrada

Si un profesor tenía ausencias activas del día y posteriormente registra una entrada, el sistema elimina esas ausencias activas y hace que desaparezcan las guardias pendientes asociadas.
