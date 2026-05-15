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

- Windows calcula el primer slot libre en SQLite.
- El alta se solicita a la Raspberry con `/register/<nombre>?slot=N`.
- La Raspberry registra la huella con `RegisterOneFp=N`.
- La respuesta debe incluir `slot: N`.
- Ese valor se guarda en `profesores.huella_id`.

No se usa un `fp_id` global separado.

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
