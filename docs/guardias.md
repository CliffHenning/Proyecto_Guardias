# Motor de cálculo de guardias

El módulo de guardias calcula cobertura de ausencias según reglas de prioridad.

## Flujo general

1. Detectar profesores disponibles
2. Aplicar ranking por criterios de prioridad
3. Asignar guardias por hora y disponibilidad

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

## Registro de guardia realizada

Desde la vista de guardias se puede registrar una guardia ya asignada.

Al pulsar el boton de registro:

1. Se almacena la guardia en la tabla `guardias` como cubierta
2. Se incrementan los contadores `guardias_acumuladas` y `guardias_semana` del profesor asignado
3. La vista se recarga mostrando los nuevos valores del ranking y el estado de la guardia como registrada
