# Sistema de Guardias y Presencia

Documentacion tecnica del proyecto para la gestion de guardias escolares y el registro de presencia del profesorado.

## Objetivo

El sistema permite:

- Registrar la presencia del profesorado mediante un metodo de identificacion configurable.
- Gestionar ausencias y calcular automaticamente las guardias.
- Exponer una interfaz web con Flask para consulta y operacion basica.
- Mantener la informacion en una base de datos SQLite.

## Modulos principales

- Flask: punto de entrada web y rutas de la aplicacion.
- Guardias: motor de calculo y reglas de asignacion.
- Presencia: identificacion del profesorado y registro de entradas o salidas.
- Base de datos: acceso a SQLite, modelos y esquema.

## Contenido de esta documentacion

En las siguientes secciones se describe la arquitectura del sistema, la base de datos, el modulo Flask, la logica de guardias, el modulo de presencia, las pruebas unitarias y el despliegue en Raspberry Pi.
