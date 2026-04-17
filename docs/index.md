# Sistema de Gestión de Guardias y Presencia

Aplicación web desarrollada con Flask para gestionar el control de presencia del profesorado y visualizar las guardias que deben cubrirse cuando se detectan ausencias.

Esta portada resume el estado real del proyecto y enlaza con el resto de la documentación técnica. Los detalles extensos de implementación se mantienen en las páginas específicas de `docs/`.

## Qué hace el proyecto

- Registra presencia del profesorado mediante métodos configurables.
- Muestra el estado actual del profesorado en la interfaz web.
- Detecta ausencias del día a partir de horarios y fichajes.
- Genera guardias pendientes para las aulas que se quedan sin profesor.
- Ordena a los candidatos a cubrir guardia según criterios de prioridad.
- Permite registrar desde la web qué profesor ha cubierto una guardia.

## Estado actual del repositorio

- La aplicación principal está en `app.py`.
- La base de datos SQLite usada por defecto es `ies.db`.
- El método de presencia se controla con la variable de entorno `METODO_PRESENCIA`.
- En el estado actual están integrados los flujos de RFID y huella.
- El reconocimiento facial no está implementado en este repositorio.

## Arranque rápido

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-presence.txt
python -m modules.db.init_db
python app.py
```

La aplicación queda disponible en `http://127.0.0.1:5000`.

## Estructura de la documentación

- `arquitectura.md`: visión general de la arquitectura y separación por capas.
- `base_datos.md`: tablas, persistencia y papel de `db_manager.py`.
- `flask.md`: rutas, vistas y responsabilidad de la capa web.
- `guardias.md`: motor de guardias, ranking y registro de coberturas.
- `presencia.md`: identificación y registro de entrada y salida.
- `pruebas.md`: organización y ejecución de la suite de tests.
- `despliegue.md`: instalación y despliegue en Raspberry Pi.

## Recorrido recomendado

Si quieres entender el proyecto de forma ordenada:

1. Empieza por arquitectura.
2. Continúa por base de datos, presencia y guardias.
3. Revisa Flask para ver cómo se expone todo en la interfaz.
4. Termina con pruebas y despliegue.

## Notas de mantenimiento

- Esta página debe funcionar como portada, no como copia del enunciado original.
- Si cambia el comportamiento real del código, hay que actualizar primero esta portada y después la página temática afectada.