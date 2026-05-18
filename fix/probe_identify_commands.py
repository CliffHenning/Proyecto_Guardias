import argparse
import json
import re
import signal
import time

from fingerprint import FingerprintSensor, IDENTIFY_CANDIDATE_COMMANDS


DEFAULT_PORT = "/dev/ttyAMA0"
DEFAULT_BAUD = 9600

DESTRUCTIVE_WORDS = (
    "REGISTER",
    "CLEAR",
    "REMOVE",
    "DELETE",
    "ERASE",
    "SETPWD",
    "CLEARPWD",
    "BAUDRATE",
    "LOCK",
)


def parse_huella_id(text):
    if not text:
        return None

    patterns = (
        r"\bPASS[_\s:|#-]*(\d+)\b",
        r"\bID[_\s:=#-]*(\d+)\b",
        r"\bFP[_\s:=#-]*(\d+)\b",
        r"\bFINGER(?:PRINT)?[_\s:=#-]*(\d+)\b",
        r"\bSLOT[_\s:=#-]*(\d+)\b",
        r"#\s*(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def is_safe_command(command):
    command_upper = command.upper()
    return not any(word in command_upper for word in DESTRUCTIVE_WORDS)


def read_for(fp, seconds):
    deadline = time.monotonic() + seconds
    chunks = []
    while time.monotonic() < deadline:
        rec = read_rx_with_timeout(fp, min(1.0, max(0.1, deadline - time.monotonic())))
        if rec:
            chunks.append(rec)
            if "Matched!" in rec or "PASS" in rec.upper() or parse_huella_id(rec) is not None:
                break
        time.sleep(0.1)
    return chunks


def _alarm_handler(signum, frame):
    raise TimeoutError("Timeout leyendo del puerto serie")


def read_rx_with_timeout(fp, seconds):
    if hasattr(signal, "SIGALRM"):
        previous_handler = signal.signal(signal.SIGALRM, _alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        try:
            return fp.read_rx()
        except Exception as exc:
            if "Timeout leyendo del puerto serie" not in str(exc):
                raise
            return ""
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)

    return fp.read_rx()


def run_command(command, port, baud, read_seconds):
    if not is_safe_command(command):
        return {
            "command": command,
            "safe": False,
            "error": "Comando bloqueado por seguridad",
            "raw": [],
            "huella_id": None,
        }

    fp = FingerprintSensor()
    fp.connect_sensor(port=port, baud_rate=baud, use_thread=False)
    try:
        fp.send_raw_command(command)
        raw = read_for(fp, read_seconds)
    except KeyboardInterrupt:
        return {
            "command": command,
            "safe": True,
            "interrupted": True,
            "matched": False,
            "huella_id": None,
            "raw": [],
        }
    finally:
        fp.disconnect_sensor()

    text = "\n".join(raw)
    return {
        "command": command,
        "safe": True,
        "matched": "MATCHED!" in text.upper(),
        "huella_id": parse_huella_id(text),
        "no_response": not bool(raw),
        "raw": raw,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Prueba comandos no destructivos PiFinger para buscar ID/slot."
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--read-seconds", type=float, default=8.0)
    parser.add_argument(
        "--command",
        action="append",
        help="Comando extra a probar, por ejemplo '<C>IdentifyFingerprint</C>'.",
    )
    parser.add_argument(
        "--only-command",
        action="append",
        help="Prueba solo este comando. Se puede repetir.",
    )
    args = parser.parse_args()

    if args.only_command:
        commands = args.only_command
    else:
        commands = [command.decode("utf-8") for command in IDENTIFY_CANDIDATE_COMMANDS]

    if args.command and not args.only_command:
        commands.extend(args.command)

    seen = set()
    results = []
    for command in commands:
        if command in seen:
            continue
        seen.add(command)

        print(f"\n=== PROBANDO {command} ===", flush=True)
        print("Coloca el dedo en el sensor ahora y espera la respuesta.", flush=True)
        result = run_command(command, args.port, args.baud, args.read_seconds)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        if result.get("interrupted"):
            print("Prueba interrumpida por teclado. Fin del probe.", flush=True)
            break

    winners = [
        result for result in results
        if result.get("huella_id") is not None
    ]
    print("\n=== RESUMEN ===", flush=True)
    if winners:
        for result in winners:
            print(
                f"OK: {result['command']} devolvio huella_id={result['huella_id']}",
                flush=True,
            )
    else:
        print("Ningun comando probado devolvio ID/slot numerico.", flush=True)


if __name__ == "__main__":
    main()
