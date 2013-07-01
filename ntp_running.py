#!/usr/bin/env python

from crtc import Crtc
from config import config
import subprocess
import re

"""
First a check to see if ntpd is running. If it is not running we set the date manually and restart the service.
"""

ntpd_status = subprocess.call(["pgrep", "ntpd"])
if (ntpd_status != 0):
    ref_server = config["hipat_reference"]
    subprocess.call(["ntpdate", "-u", ref_server])
    subprocess.call(["/etc/rc.d/ntpd", "restart"])
    
"""
Then we make sure that the output we receive from the Crtc is valid. This is indicated by a bit in the text string we receive, it is either:
A: Valid
V: Not valid
If the data is unvalid we set the date and time of the Crtc.
"""

ser = Crtc()
regex = "054,(A|V),0000"
for x in range(10):
    try:
        serial_message = str(ser)
        match = re.search(regex, serial_message).group(1)
        if match:
            answer = match
            break
    except:
        answer = "V"
        continue
if answer == "V":
    ser.date_time(0)