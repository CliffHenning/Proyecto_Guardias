import argparse
import json
import re
import signal
import time

from fingerprint import FingerprintSensor


DEFAULT_PORT = "/dev/ttyAMA0"
DEFAULT_BAUD = 9600
DEFAULT_COMMAND = "<C>CompareFingerprint</C>"


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


def main():
    parser = argparse.ArgumentParser(
        description="Ejecuta un comando de identificacion PiFinger y devuelve JSON."
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--command", default=DEFAULT_COMMAND)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    fp = FingerprintSensor()
    fp.connect_sensor(port=args.port, baud_rate=args.baud, use_thread=False)
    raw = []
    try:
        fp.send_raw_command(args.command)
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            rec = read_rx_with_timeout(fp, min(1.0, max(0.1, deadline - time.monotonic())))
            if rec:
                print(rec, flush=True)
                raw.append(rec)
                text = "\n".join(raw)
                if parse_huella_id(text) is not None or "Matched!" in text:
                    break
            time.sleep(0.1)
    finally:
        fp.disconnect_sensor()

    text = "\n".join(raw)
    huella_id = parse_huella_id(text)
    print("IDENTIFY_JSON=" + json.dumps({
        "ok": huella_id is not None,
        "matched": "MATCHED!" in text.upper() or huella_id is not None,
        "huella_id": huella_id,
        "command": args.command,
        "raw": raw,
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
