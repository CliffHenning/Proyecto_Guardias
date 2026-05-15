# Sistema de Guardias y Presencia

Aplicación web en Python para gestionar el control de presencia del profesorado y calcular las guardias necesarias cuando se detectan ausencias.

La solución está organizada en módulos independientes para mantener separadas la interfaz web, la lógica de negocio y el acceso a datos. La interfaz está construida con Flask, la persistencia se apoya en SQLite y la documentación se publica con MkDocs.

## Qué hace el sistema

- Registra entradas y salidas del profesorado.
- Detecta ausencias que afectan al horario lectivo.
- Calcula qué aulas requieren cobertura.
- Ordena al profesorado disponible según criterios de prioridad.
- Permite confirmar manualmente qué profesor cubre cada guardia.

## Estructura de la documentación

- Arquitectura: visión general de capas y módulos.
- Base de datos: esquema persistente, tablas y resultado de guardias.
- Flask: rutas principales y vistas de la aplicación.
- Guardias: flujo de cálculo, ranking y registro manual.
- Presencia: identificación del profesorado y alternancia de entrada o salida.
- Fix: cambios aplicados para registrar huellas en slots reales del sensor.
- Pruebas: ejecución de la suite automática con pytest.
- Despliegue: notas base para ejecutar el proyecto en Raspberry Pi.

## Estructura principal del proyecto

```text
app.py
config.py
modules/
  db/
  guardias/
  presencia/
templates/
tests/
docs/
```

## Documentación local

Para previsualizar la documentación en local:

```bash
mkdocs serve
```

Para generar el sitio estático:

```bash
mkdocs build
```

El resto del detalle técnico está distribuido en las páginas específicas del menú lateral.
