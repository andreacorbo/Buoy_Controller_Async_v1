# boot.py
# MIT license; Copyright (c) 2020 Andrea Corbo

import os
import pyb

pyb.freq(84000000)  # Sets main clock to reduce power consumption.

pyb.usb_mode("VCP+MSC")  # Sets usb device to act only as virtual com port, needed
                     # to map pyboard to static dev on linux systems.
try:
    os.mount(pyb.SDCard(), "/sd")  # Mounts SD card.
except:
    print("UNABLE TO MOUNT SD")
