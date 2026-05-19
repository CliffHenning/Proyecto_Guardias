# Modulo de Presencia

Gestiona la identificacion por huella y el registro de presencia del profesorado.

## Identificacion

- Metodo principal: huella dactilar mediante servidor Flask en Raspberry Pi.
- La aplicacion principal consulta la Raspberry por HTTP.
- El identificador usado por todo el sistema es el slot del sensor.

```text
huella_id == slot del sensor
```

Cuando el sensor devuelve `PASS_0`, la aplicacion busca directamente un profesor con `huella_id = 0`.

## Registro de huella

- Windows (app principal) calcula el primer slot libre en SQLite.
- El alta se solicita a la Raspberry mediante endpoints configurables en `modules/presencia/huella_service.py`.
- Por defecto el cliente intenta varias rutas de “register” (enrolado), por ejemplo: `/register_fingerprint`, `/enroll`, `/enrolar`, `/register`, etc.
- La Raspberry registra la huella en el **slot real** del sensor equivalente a `RegisterOneFp=<slot>`.
- La respuesta debe permitir obtener el slot (por ejemplo `PASS_<n>`, `slot`, `slot_id` o un texto que contenga el número).
- Ese valor se guarda en `profesores.huella_id`.

No se usa un `fp_id` global separado.

## Endpoints JSON (app principal)

La identificación automática y el registro de presencia se realizan mediante:

- `POST /presencia/confirmar-presencia-huella`

Y el enrolado mediante:

- `POST /presencia/enrolar`

Códigos HTTP y mensajes esperados:

- **200**: OK (`ok: true`) o fallo controlado (`ok: false`)
- **400**: sin huella detectada
- **404**: huella detectada pero no registrada en BD
- **500**: excepción no controlada

## Registro de presencia

La funcion `registrar_presencia` alterna entre `entrada` y `salida`.

El escaneo de huella usa esa misma alternancia:

- si el ultimo estado era `entrada`, el nuevo registro es `salida`;
- si no habia entrada activa, el nuevo registro es `entrada`.

## Depuracion

Durante el escaneo se registran logs con:

- ruta y metodo usados contra la Raspberry;
- respuesta cruda del sensor;
- datos parseados;
- conjunto de `huella_id` validos leidos desde SQLite;
- slot detectado por el parser.
