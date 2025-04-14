# Programmname : fram_test_roh.py
# Datum        : 2025-04-02
# Ersteller    : Wolfram
# Version      : 1.0

from smbus2 import SMBus

FRAM_I2C_ADDR = 0x50

with SMBus(1) as bus:
    print("=== Schreibe Testdaten an Adressen 0x00 bis 0x0F ===")
    for addr in range(0x00, 0x10):
        bus.write_byte_data(FRAM_I2C_ADDR, addr, addr + 1)
        print(f"→ geschrieben: Adresse 0x{addr:02X} ← Wert {addr + 1}")

    print("\n=== Lese zurück von 0x00 bis 0x0F ===")
    for addr in range(0x00, 0x10):
        val = bus.read_byte_data(FRAM_I2C_ADDR, addr)
        print(f"← gelesen   : Adresse 0x{addr:02X} → Wert {val}")
