# ============================================
# Programmname : reset_fram.py
# Datum        : 2025-04-02
# Version      : 2.2.5
# Ersteller    : Wolfram
# Zweck        : Rücksetzen aller wichtigen Speicherstellen (0x00–0x10) im FRAM
# ============================================

import board
import busio
import adafruit_fram

i2c = busio.I2C(board.SCL, board.SDA)
fram = adafruit_fram.FRAM_I2C(i2c)

print("Setze FRAM-Bytes von 0x00 bis 0x10 auf 0...")
for addr in range(0x00, 0x11):
    fram[addr] = 0
    print(f"Adresse 0x{addr:02X} ← 0")
print("Fertig.")