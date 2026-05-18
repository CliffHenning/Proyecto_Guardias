from flask import Flask, jsonify, request
import json
import re
import subprocess

app = Flask(__name__)
API_VERSION = "pifinger-api-2026-05-18-match-sin-identidad"
DESTRUCTIVE_COMMAND_WORDS = {
    "REGISTER",
    "CLEAR",
    "REMOVE",
    "DELETE",
    "ERASE",
    "SETPWD",
    "CLEARPWD",
    "BAUDRATE",
    "LOCK",
}


@app.route("/health")
def health():
    return jsonify({"ok": True, "version": API_VERSION})


@app.route("/version")
def version():
    return jsonify({"ok": True, "version": API_VERSION})


def _command_from_request():
    command = request.args.get("command", "CompareFingerprint").strip()
    if not command:
        command = "CompareFingerprint"

    if command.startswith("<C>") and command.endswith("</C>"):
        raw_command = command
    else:
        raw_command = f"<C>{command}</C>"

    command_upper = raw_command.upper()
    if any(word in command_upper for word in DESTRUCTIVE_COMMAND_WORDS):
        return None, f"Comando bloqueado por seguridad: {raw_command}"

    return raw_command, None


def _parse_identify_json(salida):
    for line in salida:
        if not line.startswith("IDENTIFY_JSON="):
            continue
        try:
            return json.loads(line.split("=", 1)[1])
        except json.JSONDecodeError:
            return None
    return None


def _parse_huella_id(salida):
    for line in salida:
        m = re.search(r"(?:MATCH_ID=|PASS[_\s:|]*|#)(\d+)", line, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


@app.route("/register/<nombre>")
def register(nombre):
    try:
        slot = request.args.get("slot", type=int)
        if slot is None:
            return jsonify({
                "ok": False,
                "error": "Debe indicar slot: /register/<nombre>?slot=N",
                "version": API_VERSION,
            }), 400

        if slot < 0 or slot > 127:
            return jsonify({
                "ok": False,
                "error": f"slot fuera de rango: {slot}",
                "version": API_VERSION,
            }), 400

        proc = subprocess.Popen(
            ["python3", "register_fingerprint.py", str(slot), "45"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        salida = []

        while True:
            line = proc.stdout.readline()

            if not line:
                break

            line = line.strip()
            print("[REGISTER]", line)
            salida.append(line)

            if (
                line == "REGISTER_OK"
                or line.startswith("REGISTER_ID=")
                or "Success" in line
                or "Registered" in line
                or "<R>FINISHED</R>" in line
                or "FINISHED" in line
            ):
                proc.terminate()
                return jsonify({
                    "ok": True,
                    "nombre": nombre,
                    "slot": slot,
                    "huella_id": slot,
                    "version": API_VERSION,
                    "raw": salida
                })

            if (
                line == "REGISTER_FAIL"
                or line == "REGISTER_TIMEOUT"
                or "<R>FAIL</R>" in line
                or "<R>NG</R>" in line
            ):
                proc.terminate()
                return jsonify({
                    "ok": False,
                    "slot": slot,
                    "huella_id": None,
                    "error": "REGISTER_FAIL",
                    "message": f"No se pudo registrar en el slot {slot}. Puede estar ocupado.",
                    "version": API_VERSION,
                    "raw": salida
                }), 409

        return jsonify({
            "ok": False,
            "slot": slot,
            "huella_id": None,
            "version": API_VERSION,
            "raw": salida
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "version": API_VERSION,
        })


@app.route("/scan")
def scan():
    try:
        proc = subprocess.Popen(
            ["python3", "compare_fp.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        salida = []

        while True:
            line = proc.stdout.readline()

            if not line:
                break

            line = line.strip()
            print("[SCAN]", line)
            salida.append(line)

            if (
                line.startswith("MATCH_ID=")
                or line == "MATCH_WITHOUT_ID"
                or line == "MATCH_FAIL"
                or "Mismatch!" in line
                or "<R>FAIL</R>" in line
            ):
                break

        huella_id = _parse_huella_id(salida)

        matched = any("Matched!" in line or line.startswith("MATCH_ID=") for line in salida)
        if matched and huella_id is None:
            return jsonify({
                "ok": False,
                "matched": True,
                "error": "MATCH_SIN_IDENTIDAD",
                "message": "El sensor confirma coincidencia, pero no devolvio slot/ID",
                "huella_id": None,
                "version": API_VERSION,
                "raw": salida
            }), 409

        return jsonify({
            "ok": huella_id is not None,
            "matched": huella_id is not None,
            "message": "Profesor reconocido" if huella_id is not None else "No se pudo identificar la huella",
            "huella_id": huella_id,
            "version": API_VERSION,
            "raw": salida
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "version": API_VERSION,
        })


@app.route("/scan_experimental")
def scan_experimental():
    command, error = _command_from_request()
    if error:
        return jsonify({
            "ok": False,
            "error": error,
            "version": API_VERSION,
        }), 400

    try:
        proc = subprocess.Popen(
            ["python3", "identify_fp.py", "--command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        salida = []
        while True:
            line = proc.stdout.readline()

            if not line:
                break

            line = line.strip()
            print("[SCAN_EXPERIMENTAL]", line)
            salida.append(line)

            if line.startswith("IDENTIFY_JSON="):
                break

        identify_result = _parse_identify_json(salida) or {}
        huella_id = identify_result.get("huella_id")
        matched = bool(identify_result.get("matched"))

        if huella_id is None:
            huella_id = _parse_huella_id(salida)

        if matched and huella_id is None:
            return jsonify({
                "ok": False,
                "matched": True,
                "error": "MATCH_SIN_IDENTIDAD",
                "message": "El comando confirma coincidencia, pero no devolvio slot/ID",
                "command": command,
                "huella_id": None,
                "version": API_VERSION,
                "raw": salida,
            }), 409

        return jsonify({
            "ok": huella_id is not None,
            "matched": huella_id is not None or matched,
            "command": command,
            "huella_id": huella_id,
            "version": API_VERSION,
            "raw": salida,
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "version": API_VERSION,
        })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
