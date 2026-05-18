#  Import FingerprintSensor class from fingerprint module
import sys
from time import monotonic, sleep
from fingerprint import FingerprintSensor

#  Set the serial comport for the connected sensor
COM_PORT = "/dev/ttyAMA0"  # /dev/ttyS0"
BAUD_RATE = 9600

slot = None
if len(sys.argv) > 1:
    slot = int(sys.argv[1])

timeout_seconds = 45.0
if len(sys.argv) > 2:
    timeout_seconds = float(sys.argv[2])

#  Create class object
fp = FingerprintSensor()
#  Initialise the sensor serial with the COM port and fixed baud rate.
fp.connect_sensor(port=COM_PORT, baud_rate=BAUD_RATE, use_thread=False)

#  Use register_fingerprint function of FingerprintSensor to send
#  fingerprint registration command to the sensor
if slot is None:
    fp.register_fingerprint()
else:
    fp.register_fingerprint(slot_id=slot)

#  Read the sensor output, as the sensor will guide through 3 step
#  registration process
deadline = monotonic() + timeout_seconds
while monotonic() < deadline:
    #  Read the sensor output, if it's not null print the received data and
    #  follow the steps printed on the console
    rec = fp.read_rx()
    if rec:
        print(rec)
        rec_upper = rec.upper()
        if "<R>FINISHED</R>" in rec_upper or "FINISHED" in rec_upper:
            if slot is not None:
                print(f"REGISTER_ID={slot}")
            print("REGISTER_OK")
            break
        if "<R>NG</R>" in rec_upper or "<R>FAIL</R>" in rec_upper or "FAIL" in rec_upper:
            print("REGISTER_FAIL")
            break
    else:
        sleep(0.1)
else:
    print("REGISTER_TIMEOUT")

#  Disconnect the serial fingerprint sensor
fp.disconnect_sensor()
