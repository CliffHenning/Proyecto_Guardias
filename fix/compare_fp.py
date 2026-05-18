from oled_091 import SSD1306
from os import path
from time import monotonic, sleep
import re

DIR_PATH = path.abspath(path.dirname(__file__))
DefaultFont = path.join(DIR_PATH, "Fonts/GothamLight.ttf")

display = SSD1306()

#  Import FingerprintSensor class from fingerprint module
from fingerprint import FingerprintSensor

#  Set the serial comport for the connected sensor
COM_PORT = "/dev/ttyAMA0"  # 

#  Create class object
fp = FingerprintSensor()
display = SSD1306()
#  Initialise the sensor serial with the COM port and fixed baud rate of
#  115200, set "use_thread" argument as false
fp.connect_sensor(port=COM_PORT, baud_rate=9600, use_thread=False)

#  Use unlock_with_fingerprint function of FingerprintSensor to send
#  fingerprint unlock command to the sensor
fp.compare_fingerprint()

display.DirImage(path.join(DIR_PATH, "Images/SB.png"))
display.DrawRect()
display.ShowImage()
sleep(1)
display.PrintText("Place your Finger", FontSize=14)
display.ShowImage()

#  Wait for the sensor to compare and keep reading briefly after Matched!.
#  The vendor GUI expects the sensor to send:
#    Matched!
#    <R>PASS_N</R>
#  so do not stop at the first Matched! line.
matched = False
matched_at = None
pass_id = None
post_match_seconds = 2.0

while True:
    rec = fp.read_rx()
    if rec:
        print(rec)

        pass_match = re.search(r"PASS[_\s:|]*(\d+)", rec, re.IGNORECASE)
        if pass_match:
            pass_id = int(pass_match.group(1))
            print(f"MATCH_ID={pass_id}")
            display.PrintText(rec, cords=(2, 2), FontSize=14)
            display.ShowImage()
            break

        if "Matched!" in rec:
            matched = True
            matched_at = monotonic()
            print("MATCH_OK")
            display.PrintText(rec, cords=(2, 2), FontSize=14)
            display.ShowImage()
            continue

        if "Mismatch!" in rec or "<R>FAIL</R>" in rec:
            print("MATCH_FAIL")
            display.PrintText(rec, cords=(2, 2), FontSize=14)
            display.ShowImage()
            break

        display.PrintText(rec, cords=(2, 2), FontSize=14)
        display.ShowImage()

    if matched and matched_at is not None:
        if monotonic() - matched_at >= post_match_seconds:
            print("MATCH_WITHOUT_ID")
            break
        else:
            sleep(0.1)

#  Disconnect the serial fingerprint sensor
fp.disconnect_sensor()
