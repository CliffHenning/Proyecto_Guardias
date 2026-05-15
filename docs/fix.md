# Fix

Esta seccion documenta los cambios aplicados para que el flujo de huella funcione con slots reales del sensor PiFinger.

## Problema detectado

El registro de huella funcionaba, pero todas las altas acababan usando el slot `0`.

Eso provocaba este efecto:

- primer profesor registrado: `huella_id = 0`;
- segundo profesor registrado: tambien pasaba a `huella_id = 0`;
- el segundo registro desplazaba al anterior en SQLite para evitar duplicados;
- al escanear `PASS_0`, el sistema identificaba al ultimo profesor asociado al slot `0`.

El problema no estaba en SQLite. La base de datos guardaba correctamente lo que recibia. El origen estaba en la Raspberry: el driver usaba el comando generico de registro y el sensor elegia siempre el slot por defecto.

## Cambio en Windows

En `modules/presencia/huella_service.py` se ajusto el alta remota:

- se calcula el primer slot libre a partir de `profesores.huella_id`;
- se llama a la Raspberry con `/register/<nombre>?slot=N`;
- se parsea `slot`, `slot_id`, `huella_id`, `id`, `fingerprint_id` o respuestas tipo `#N`;
- se guarda el slot recibido como `huella_id`;
- no se hace un escaneo adicional para corregir el registro.

## Cambio en api_finger.py

La API Flask de la Raspberry exige un slot explicito:

```text
/register/<nombre>?slot=N
```

El endpoint valida el rango y llama al driver con ese slot:

```python
registrar_huella_en_slot(slot_preferido)
```

Tambien devuelve errores claros si el driver no soporta registro por slot.

## Cambio en fingerprint.py

El driver ya tenia disponible el comando:

```python
REGISTER_FINGERPRINT_AT_STRING = "<C>RegisterOneFp={}</C>"
```

Pero `register_fingerprint()` usaba el comando generico:

```python
REGISTER_FINGERPRINT_STRING = b"<C>RegisterFingerprint</C>"
```

Ese comando generico acababa registrando en el slot por defecto.

La funcion se modifico para aceptar un slot opcional:

```python
def register_fingerprint(self, slot_id=None, slot=None):
    if slot_id is None:
        slot_id = slot
    if slot_id is None:
        return self.send_cmd(REGISTER_FINGERPRINT_STRING)
    return self.register_fingerprint_at(slot_id)
```

Y `register_fingerprint_at()` valida el rango antes de enviar:

```python
<C>RegisterOneFp=N</C>
```

## Resultado esperado

- Sergio se registra primero: `huella_id = 0`.
- Carlos se registra despues: `huella_id = 1`.
- Lucia se registra despues: `huella_id = 2`.
- Escanear Sergio devuelve `PASS_0`.
- Escanear Carlos devuelve `PASS_1`.
- Escanear Lucia devuelve `PASS_2`.

El sistema completo queda sincronizado:

```text
Raspberry slot == SQLite huella_id == PASS_N
```
