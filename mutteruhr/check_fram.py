#!/usr/bin/env python3
# Programmname: check_fram.py
# Version: 1.0.1
# Datum: 2025-04-05
# Ersteller: Wolfram

import board
import busio
import adafruit_fram
import time

# FRAM-Setup
i2c = busio.I2C(board.SCL, board.SDA)
fram = adafruit_fram.FRAM_I2C(i2c, address=0x50)

# Adresse für Istpulse je Linie (Little Endian)
linien = {
    0x00: "Linie 1",
    0x02: "Linie 2",
    0x04: "Linie 3",
    0x06: "Linie 4"
}

print("Inhalt der FRAM-Speicherstellen für Istpuls (Adafruit FRAM):")
print("Adresse  Wert    (Bytes)        Linie")
print()

for addr, name in linien.items():
    lo = fram[addr][0]
    hi = fram[addr + 1][0]
    wert = int(lo) | (int(hi) << 8)
    print(f"0x{addr:02X}     {wert:<7} ({lo:3}, {hi:3})     {name}")

# Flags lesen
flags1 = fram[0x09][0]
flags2 = fram[0x0A][0]

print("\nLaufzeitflags:")
for i in range(4):
    aktiv = (flags1 >> i) & 1
    stopp = (flags1 >> (i + 4)) & 1
    print(f"Linie {i+1}: aktiv = {aktiv}, stopp = {stopp}")

web = (flags2 >> 0) & 1
verbose = ((flags2 >> 1) & 1) + ((flags2 >> 2) & 1) * 2 + ((flags2 >> 3) & 1) * 4
print(f"WebActive: {web}, verbose = {verbose}")