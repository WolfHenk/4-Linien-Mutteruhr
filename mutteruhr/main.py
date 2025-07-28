# Programmname: Mutteruhrsteuerung
# Version     : 6.2.1
# Ersteller   : Wolfram
# Datum       : 28.07.2025
print("\n Version     : 6.2.1 \n")

##BEGINN INIT
import os
import json
import time
import configparser
import pigpio
import busio
import board
import adafruit_fram
from datetime import datetime
import threading
from flask import jsonify

#Set use_H_bridge to true if you use my KiCad-board!
#set it to False to user relayboards.
use_H_bridge = True

CONFIG_PATH = '/opt/mutteruhr/mutteruhr.conf'
file_to_web = "/dev/shm/to_web.json"
#file_to_clock = "/dev/shm/to_clock.json"
letzter_ram_timestamp = 0
Startup = 0
config = configparser.ConfigParser()
config.read(CONFIG_PATH)
conf_verbose = config['System'].getint('conf_verbose', fallback=0)
verbose = conf_verbose
pi = pigpio.pi()
i2c = busio.I2C(board.SCL, board.SDA)
fram = adafruit_fram.FRAM_I2C(i2c)
fram_adressen = [0x00, 0x02, 0x04, 0x06]
linien = {}
zustand = {}

for i in range(1, 5):
    key = f"Linie{i}"
    sek = config[key]
    linien[key] = {
        "gpio_pos": sek.getint("gpio_pos"),
        "gpio_neg": sek.getint("gpio_neg"),
        "impuls_ms": sek.getint("impuls_ms"),
        "pause_ms": sek.getint("pause_ms"),
        "modus_24h": sek.getboolean("modus_24h"),
        "stopp": sek.getboolean("stopp"),
        "aktiv": sek.getboolean("aktiv"),
        "name": sek.get("name", fallback=key),
        "istpuls": 1,
        "Wartepuls": False,
        "halt": False,
    }

    pi.set_mode(linien[key]["gpio_pos"], pigpio.OUTPUT)
    pi.set_mode(linien[key]["gpio_neg"], pigpio.OUTPUT)
    if use_H_bridge == True:
        pi.write(linien[key]["gpio_pos"], 0)
        pi.write(linien[key]["gpio_neg"], 0)
    else:
        pi.write(linien[key]["gpio_pos"], 1)
        pi.write(linien[key]["gpio_neg"], 1)

    addr = fram_adressen[i - 1]
    lo = fram[addr][0] if isinstance(fram[addr], (bytes, bytearray)) else fram[addr]
    hi = fram[addr + 1][0] if isinstance(fram[addr + 1], (bytes, bytearray)) else fram[addr + 1]
    ist = (hi << 8) | lo
    maxpuls = 1440 if linien[key]["modus_24h"] else 720
    if ist == 0 or ist > maxpuls:
        ist = 1
        linien[key]["stopp"] = True
        config[key]["stopp"] = "true"
    linien[key]["istpuls"] = ist

    zustand[key] = {
        "phase": "bereit",
        "next_time": time.monotonic()
    }

with open(CONFIG_PATH, 'w') as cfgfile:
    config.write(cfgfile)

if verbose > 0:
    print("\nAktive GPIO-Belegung:")
    print("Linie    GPIO_POS   GPIO_NEG  ")
    print("------------------------------")
    for key, val in linien.items():
        print("{:<8}{:<11}{}".format(key, val['gpio_pos'], val['gpio_neg']))
    print(f"\nVerbose-Level aktiv: {verbose}")
    print("\nInitialisierung abgeschlossen. Starte Routinendefinition...")
##ENDE INITIALISIERUNG

##BEGINN ROUTINEN
def soll_impuls(ist, soll, maxpuls, toleranz=65):
    if ist == soll:
        return False
    if ist < soll:
        return True
    if ist > soll and (ist - soll > toleranz):
        if verbose > 4:
            print(f"[{key}] vor Echtzeit: Warte")
        return True
    return False

def LeseFram():
    global linien, fram_adressen, fram, verbose, web_active

    for i, key in enumerate(linien.keys()):
        addr = fram_adressen[i]
        lo = fram[addr][0] if isinstance(fram[addr], (bytes, bytearray)) else fram[addr]
        hi = fram[addr + 1][0] if isinstance(fram[addr + 1], (bytes, bytearray)) else fram[addr + 1]
        linien[key]["istpuls"] = (hi << 8) | lo

    flags1 = fram[0x09][0] if isinstance(fram[0x09], (bytes, bytearray)) else fram[0x09]
    for i, key in enumerate(linien.keys()):
        linien[key]["aktiv"] = bool(flags1 & (1 << i))
        linien[key]["stopp"] = bool(flags1 & (1 << (i + 4)))

    flags2 = fram[0x0A][0] if isinstance(fram[0x0A], (bytes, bytearray)) else fram[0x0A]
    web_active = bool(flags2 & 0b00000001)
    # verbose aus FRAM wird nicht gesetzt – Konfig ist führend

    if verbose > 3:
        print("[FRAM] Lese Istpulse und Flags:")
        for key in linien:
            print(f"  {key}: istpuls = {linien[key]['istpuls']}, aktiv = {linien[key]['aktiv']}, stopp = {linien[key]['stopp']}")
            print(f"  WebActive = {web_active}, verbose = {verbose}")

def SchreibeFram():
    global linien, fram_adressen, fram, verbose, config

    flags1 = 0
    flags2 = 0

    for i, key in enumerate(linien.keys()):
        linie = linien[key]
        istpuls = linie["istpuls"]
        addr = fram_adressen[i]
        fram[addr] = istpuls & 0xFF
        fram[addr + 1] = (istpuls >> 8) & 0xFF
        if linie["aktiv"]:
            flags1 |= (1 << i)
        if linie["stopp"] or linie["halt"]:
            flags1 |= (1 << (i + 4))

    if config["System"].getboolean("WebActive", fallback=True):
        flags2 |= 1

    v = verbose & 0b111
    flags2 |= (v << 1)

    fram[0x09] = bytes([flags1])
    fram[0x0A] = bytes([flags2])

    if verbose >= 3:
        print(f"[FRAM] Schreibe Flags1 (0x09): {flags1:08b}")
        print(f"[FRAM] Schreibe Flags2 (0x0A): {flags2:08b}")
    

def SchreibeRam():
    global linien, verbose, file_to_web

    daten = {}

    for key, linie in linien.items():
        daten[key] = {
            "name": linie["name"],
            "istpuls": linie["istpuls"],
            "impuls_ms": linie["impuls_ms"],
            "pause_ms": linie["pause_ms"],
            "stopp": linie["stopp"],
            "aktiv": linie["aktiv"],
            "modus_24h": linie["modus_24h"],
            "Wartepuls": linie["Wartepuls"],
        }

    try:
        with open(file_to_web, "w") as f:
            json.dump(daten, f)
        if verbose > 5:
            print("[RAM] Schreibe to_web.json mit folgenden Daten:")
            for k, v in daten.items():
                print(f"  {k}: {v}")
    except Exception as e:
        if verbose > 0:
            print(f"[RAM] Fehler beim Schreiben von to_web.json: {e}")


""" def LeseRam():
    global letzter_ram_timestamp, file_to_clock, linien, config, verbose

    if not os.path.exists(file_to_clock):
        if verbose > 4:
            print("[LeseRam] RAM-Datei nicht gefunden.")
        return

    try:
        with open(file_to_clock, "r") as f:
            daten = json.load(f)
    except Exception as e:
        if verbose > 0:
            print(f"[LeseRam] Fehler beim Lesen der RAM-Datei: {e}")
        return

    if "timestamp" not in daten or not isinstance(daten["timestamp"], int):
        if verbose > 4:
            print("[LeseRam] Kein gültiger Timestamp vorhanden – Datei wird ignoriert.")
        return

    if daten["timestamp"] <= letzter_ram_timestamp:
        if verbose > 5:
            print("[LeseRam] Timestamp nicht neuer – kein Einlesen erforderlich.")
        return

    letzter_ram_timestamp = daten["timestamp"]

    if verbose > 4:
        print(f"[LeseRam] Einlesen gültiger Daten von timestamp: {daten['timestamp']}")

    geändert = False

    for key in linien.keys():
        if key not in daten:
            continue
        ram = daten[key]
        linie = linien[key]
        sektion = config[key]

        # Istpuls → FRAM und intern
        if "istpuls" in ram and isinstance(ram["istpuls"], int):
            if ram["istpuls"] != linie["istpuls"]:
                if verbose > 4:
                    print(f"[LeseRam] {key}: istpuls {linie['istpuls']} → {ram['istpuls']}")
                linie["istpuls"] = ram["istpuls"]
                geändert = True  # Wird im Hauptcode dann per SchreibeFram übernommen

        # Impulsdauer
        if "impuls_ms" in ram and isinstance(ram["impuls_ms"], int):
            if ram["impuls_ms"] != linie["impuls_ms"]:
                if verbose > 4:
                    print(f"[LeseRam] {key}: impuls_ms {linie['impuls_ms']} → {ram['impuls_ms']}")
                linie["impuls_ms"] = ram["impuls_ms"]
                sektion["impuls_ms"] = str(ram["impuls_ms"])

        # Pausendauer
        if "pause_ms" in ram and isinstance(ram["pause_ms"], int):
            if ram["pause_ms"] != linie["pause_ms"]:
                if verbose > 4:
                    print(f"[LeseRam] {key}: pause_ms {linie['pause_ms']} → {ram['pause_ms']}")
                linie["pause_ms"] = ram["pause_ms"]
                sektion["pause_ms"] = str(ram["pause_ms"])

        # Stopp-Flag
        if "stopp" in ram and isinstance(ram["stopp"], bool):
            if ram["stopp"] != linie["stopp"]:
                if verbose > 4:
                    print(f"[LeseRam] {key}: stopp {linie['stopp']} → {ram['stopp']}")
                linie["stopp"] = ram["stopp"]
                sektion["stopp"] = str(ram["stopp"]).lower()

    # Konfig zurückschreiben
    with open(CONFIG_PATH, 'w') as cfgfile:
        config.write(cfgfile) """
# ----------------------------
# Routine: WebServer()
# ----------------------------
def WebServer():
    from flask import Flask, render_template, request, redirect, url_for

    app = Flask(__name__)

    def puls_to_time(puls, is_24h):
        if not is_24h and puls >= 720:
            puls -= 720
        hh = puls // 60
        mm = puls % 60
        return f"{hh:02}:{mm:02}"

    def time_to_puls(hh, mm, is_24h):
        istpuls = hh * 60 + mm
        if not is_24h and hh > 12:
            istpuls -= 720
        return istpuls

    @app.route("/")
    def index():
        return render_template("index.html", linien=linien)

    @app.route("/edit/<linie_id>")
    def edit_line(linie_id):
        linie = linien[linie_id]
        linie["halt"] = True
        istzeit = puls_to_time(linie["istpuls"], linie["modus_24h"])
        return render_template("aenderung.html", linie=linie, linie_id=linie_id, istzeit=istzeit)

    @app.route("/update_line", methods=["POST"])
    def update_line():
        linie_id = request.form["linie_id"]
        linie = linien[linie_id]

        linie["name"] = request.form["name"]
        linie["impuls_ms"] = int(request.form["impuls_ms"])
        linie["pause_ms"] = int(request.form["pause_ms"])
        linie["modus_24h"] = "modus_24h" in request.form
        linie["stopp"] = "stopp" in request.form

        neue_zeit = request.form["istzeit"]
        hh, mm = map(int, neue_zeit.split(":"))

        # Begrenzen auf gültige Werte
        hh = max(0, min(hh, 23))
        mm = max(0, min(mm, 59))

        neuer_istpuls = time_to_puls(hh, mm, linie["modus_24h"])

        # Impuls- und Pausenzeit begrenzen
        impuls = int(request.form["impuls_ms"])
        pause = int(request.form["pause_ms"])

        impuls = max(10, min(impuls, 3000))
        pause = max(10, min(pause, 1500))

        linie["impuls_ms"] = impuls
        linie["pause_ms"] = pause


        if linie["istpuls"] != neuer_istpuls:
            linie["istpuls"] = neuer_istpuls
            addr = fram_adressen[list(linien.keys()).index(linie_id)]
            fram[addr] = linie["istpuls"] & 0xFF
            fram[addr + 1] = (linie["istpuls"] >> 8) & 0xFF

        linie["halt"] = False

        sektion = config[linie_id]
        sektion["name"] = linie["name"]
        sektion["impuls_ms"] = str(linie["impuls_ms"])
        sektion["pause_ms"] = str(linie["pause_ms"])
        sektion["modus_24h"] = str(linie["modus_24h"])
        sektion["stopp"] = str(linie["stopp"])
        with open(CONFIG_PATH, 'w') as cfgfile:
            config.write(cfgfile)

        return redirect(url_for("index"))

    @app.route("/status_json")
    def status_json():
        from datetime import datetime
        now = datetime.now()
        soll24 = now.hour * 60 + now.minute
        sollzeit24 = f"{soll24 // 60:02}:{soll24 % 60:02}"

        linienstatus = {
            key: {
                "istpuls": linie["istpuls"],
                "Wartepuls": linie["Wartepuls"],
                "modus_24h": linie["modus_24h"]
            } for key, linie in linien.items()
        }

        return jsonify({
            "linien": linienstatus,
            "sollzeit24": sollzeit24
        })



    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)


##ENDE ROUTINEN
last_second = -1
Startup = 1
if verbose > 0:
    print("\nStartup-Phase...")
##STARTUP-PHASEN
while Startup < 10:
    match Startup:
        case 1:
            if verbose > 0:
                print("Startup case 1 aktiv: lösche RAM-Dateien")
            # lösche RAM-Dateien falls vorhanden. In diesem Stadium sind es Leichen.
            if os.path.exists(file_to_web):
                os.remove(file_to_web)
            #if os.path.exists(file_to_clock):
            #    os.remove(file_to_clock)
            #lösche ram files
            Startup = 2

        case 2:
            if verbose > 0:
                print("Startup case 2 aktiv: Reserveschritt")
            # RESERVESCHRITT
            Startup = 3

        case 3:
            if verbose > 0:
                print("Startup case 3 aktiv: Erzeuge RAM-Datei file to web")
            # Erzeuge RAM-Datei falls nicht vorhanden
            if not os.path.exists(file_to_web):
                with open(file_to_web, "w") as f:
                    json.dump({}, f)
            Startup = 4

        case 4:
            if verbose > 0:
            #    print("Startup case 4 aktiv: Erzeuge RAM-Datei file to clock")
                print("Startup case 4 aktiv: Reserveschritt")
            # Erzeuge zweite RAM-Datei
            #if not os.path.exists(file_to_clock):
            #    with open(file_to_clock, "w") as f:
            #        json.dump({"timestamp": 0}, f)
            Startup = 5

        case 5:
            if verbose > 0:
                print("Startup case 5 aktiv: RESERVESCHRITT")
            # RESERVESCHRITT
            Startup = 6

        case 6:
            if verbose > 0:
                print("Startup case 6 aktiv: Schreibe RAM Initial")
            SchreibeRam()
            Startup = 7

        case 7:
            # vorgesehen für Webserver Start
            if verbose > 0:
                print("Startup case 7 aktiv: Starte Webserver")
            threading.Thread(target=WebServer, daemon=True).start()
            Startup = 8

        case 8:
            if verbose > 0:
                print("Startup case 8 aktiv: RESERVESCHRITT")
            # vorgesehen zur Überprüfung ob Webserver da ist...
            Startup = 9

        case 9:
            if verbose > 0:
                print("Startup case 9 aktiv: RESERVESCHRITT")
            Startup = 10  # Regelbetrieb aktivieren
if verbose > 0:
    print("\nStartup abgeschlossen. Starte Regelbetrieb, Hauptschleife...\n")
##ENDE STARTUP-PHASEN

##BEGINN HAUPTSCHLEIFE
while Startup == 10:
    now = datetime.now()
    minute = now.hour * 60 + now.minute
    soll24 = minute
    soll12 = soll24 if soll24 <= 720 else soll24 - 720

    current_time = time.monotonic()

    for i, key in enumerate(linien.keys()):
        linie = linien[key]
        z = zustand[key]

        if not linie["aktiv"]:
            if verbose >= 4:
                print(f"[{key}] nicht aktiv")
            continue
        if linie["stopp"] or linie["halt"]:
            if verbose >= 4:
                print(f"[{key}] STOP oder HALT durch Bearbeiten")
            continue

        if current_time < z["next_time"]:
            continue

        maxpuls = 1440 if linie["modus_24h"] else 720
        soll = soll24 if linie["modus_24h"] else soll12
        ist = linie["istpuls"]

        linie["Wartepuls"] = False
        if ist > soll and (ist - soll >= 2 and ist - soll < 65):
            linie["Wartepuls"] = True
            if verbose > 3:
                print(f"[{key}] Wartepuls: ist = {ist}, soll = {soll}, Δ = {ist - soll}")
        if z["phase"] == "bereit":
            if not soll_impuls(ist, soll, maxpuls):
                if verbose >= 4:
                    print(f"[{key}] Warte auf neue Minute")
                z["next_time"] = current_time + 1
                continue

            if ist % 2 == 0:
                if use_H_bridge==True:
                    pi.write(linie["gpio_pos"], 1)
                else:    
                    pi.write(linie["gpio_pos"], 0)
                if verbose >= 5:
                    print(f"[{key}] Puls an (GPIO {linie['gpio_pos']})")
            else:
                if use_H_bridge==True:
                    pi.write(linie["gpio_neg"], 1)
                else:    
                    pi.write(linie["gpio_neg"], 0)
                if verbose >= 5:
                    print(f"[{key}] Puls an (GPIO {linie['gpio_neg']})")

            if verbose >= 2:
                print(f"[{key}] Sende Puls {ist}")

            addr = fram_adressen[i]
            fram[addr] = linie["istpuls"] & 0xFF
            fram[addr + 1] = (linie["istpuls"] >> 8) & 0xFF
            z["phase"] = "puls"
            z["next_time"] = current_time + linie["impuls_ms"] / 1000

        elif z["phase"] == "puls":
            if use_H_bridge==True:    
                pi.write(linie["gpio_pos"], 0)
                pi.write(linie["gpio_neg"], 0)
            else:
                pi.write(linie["gpio_pos"], 1)
                pi.write(linie["gpio_neg"], 1)
            if verbose >= 5:
        
                print(f"[{key}] Puls aus (beide HIGH)")

            linie["istpuls"] += 1
            if linie["istpuls"] > maxpuls:
                linie["istpuls"] = 1

            addr = fram_adressen[i]
            fram[addr] = linie["istpuls"] & 0xFF
            fram[addr + 1] = (linie["istpuls"] >> 8) & 0xFF

            z["phase"] = "pause"
            z["next_time"] = current_time + linie["pause_ms"] / 1000

        elif z["phase"] == "pause":
            z["phase"] = "bereit"
            z["next_time"] = current_time

    if now.second != last_second:
        last_second = now.second
        config.read(CONFIG_PATH)

        conf_verbose = config["System"].getint("conf_verbose", fallback=0)
        if conf_verbose != verbose:
            verbose = conf_verbose

        LeseFram()
        
        update_needed = False
        for i in range(1, 5):
            key = f"Linie{i}"
            sek = config[key]
            l = linien[key]

            # Konfigurationswerte übernehmen
            l["impuls_ms"] = sek.getint("impuls_ms")
            l["pause_ms"] = sek.getint("pause_ms")
            l["modus_24h"] = sek.getboolean("modus_24h")
            l["stopp"] = sek.getboolean("stopp")
            l["aktiv"] = sek.getboolean("aktiv")

            if (
                l["impuls_ms"] != sek.getint("impuls_ms") or
                l["pause_ms"] != sek.getint("pause_ms") or
                l["modus_24h"] != sek.getboolean("modus_24h") or
                l["stopp"] != sek.getboolean("stopp") or
                l["aktiv"] != sek.getboolean("aktiv")
            ):
                update_needed = True
                break

        if update_needed:
            if verbose > 2:
                print("[CFG] Änderung erkannt – schreibe in FRAM...")
            SchreibeFram()
        SchreibeRam()
#        LeseRam()
    time.sleep(0.01)
##ENDE HAUPTSCHLEIFE
