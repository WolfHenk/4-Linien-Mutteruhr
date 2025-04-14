#!/usr/bin/env python3

import tkinter as tk
import json
import os
from math import sin, cos, radians

JSON_PFAD = "/dev/shm/to_web.json"
UPDATE_INTERVAL = 997  # in Millisekunden

root = tk.Tk()
root.title("Radio-Museum Mutteruhr Anzeige")
root.geometry("600x600")
root.configure(bg='black')

anzeigen = {}
positionen = [(0, 0), (0, 1), (1, 0), (1, 1)]

def istpuls_to_time(istpuls):
    minute = istpuls
    hh = minute // 60
    mm = minute % 60
    return hh, mm

def zeichne_analog(canvas, hh, mm, grau=False):
    canvas.delete("all")
    cx, cy, r = 100, 100, 80
    farbe = 'gray' if grau else 'black'
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill='white')

    for i in range(60):
        winkel = radians(i * 6 - 90)
        x_outer = cx + r * cos(winkel)
        y_outer = cy + r * sin(winkel)
        if i % 5 == 0:
            x_inner = cx + (r - 10) * cos(winkel)
            y_inner = cy + (r - 10) * sin(winkel)
            canvas.create_line(x_inner, y_inner, x_outer, y_outer, width=2, fill=farbe)
            if i % 15 == 0:
                zahl = {0: '12', 15: '3', 30: '6', 45: '9'}[i]
                x_text = cx + (r - 25) * cos(winkel)
                y_text = cy + (r - 25) * sin(winkel)
                canvas.create_text(x_text, y_text, text=zahl, font=("Helvetica", 10, "bold"), fill=farbe)
        else:
            x_inner = cx + (r - 5) * cos(winkel)
            y_inner = cy + (r - 5) * sin(winkel)
            canvas.create_line(x_inner, y_inner, x_outer, y_outer, width=1, fill=farbe)

    winkel_min = radians(mm * 6 - 90)
    winkel_std = radians((hh % 12 + mm / 60) * 30 - 90)

    x_m = cx + r * 0.75 * cos(winkel_min)
    y_m = cy + r * 0.75 * sin(winkel_min)
    x_h = cx + r * 0.5 * cos(winkel_std)
    y_h = cy + r * 0.5 * sin(winkel_std)

    canvas.create_line(cx, cy, x_m, y_m, width=2, fill=farbe)
    canvas.create_line(cx, cy, x_h, y_h, width=4, fill=farbe)

def zeichne_digital(canvas, hh, mm, grau=False):
    canvas.delete("all")
    farbe = 'gray' if grau else 'white'
    canvas.create_rectangle(0, 0, 200, 200, fill='black')
    canvas.create_text(100, 100, text=f"{hh:02}:{mm:02}", font=("Courier", 36), fill=farbe)

def lade_daten():
    if not os.path.exists(JSON_PFAD):
        return {}
    try:
        with open(JSON_PFAD, "r") as f:
            return json.load(f)
    except:
        return {}

def aktualisieren():
    daten = lade_daten()
    for linienindex in range(1, 5):
        linienkey = f"Linie{linienindex}"
        canvas, label, warten_label = anzeigen.get(linienkey, (None, None, None))
        if not canvas or not label or not warten_label:
            continue

        eintrag = daten.get(linienkey)
        if not eintrag or not eintrag.get("aktiv") or eintrag.get("istpuls", 0) <= 0:
            canvas.delete("all")
            label.config(text="")
            warten_label.config(text="")
            continue

        hh, mm = istpuls_to_time(eintrag["istpuls"])
        name = eintrag.get("name", linienkey)
        ist_stopp = eintrag.get("stopp", False)
        ist_wartepuls = eintrag.get("Wartepuls", False)

        if ist_stopp:
            label.config(text=f"{linienkey} ({name})\nANGEHALTEN", fg='gray', bg='black')
        else:
            label.config(text=f"{linienkey} ({name})", fg='white', bg='black')

        if ist_wartepuls:
            warten_label.config(text="WARTEN", fg='gray')
        else:
            warten_label.config(text="")

        if eintrag.get("modus_24h"):
            zeichne_digital(canvas, hh, mm, grau=ist_stopp)
        else:
            zeichne_analog(canvas, hh, mm, grau=ist_stopp)

    root.after(UPDATE_INTERVAL, aktualisieren)

def init_gui():
    for idx in range(4):
        linienkey = f"Linie{idx+1}"
        i, j = positionen[idx]
        frame = tk.Frame(root, bg='black')
        frame.grid(row=i, column=j, padx=20, pady=20)
        label = tk.Label(frame, text="", font=("Helvetica", 12), bg='black', fg='white')
        label.pack()
        canvas = tk.Canvas(frame, width=200, height=200, bg='black', highlightthickness=0)
        canvas.pack()
        warten_label = tk.Label(frame, text="", font=("Helvetica", 10, "italic"), bg='black', fg='gray')
        warten_label.pack()
        anzeigen[linienkey] = (canvas, label, warten_label)

init_gui()
aktualisieren()
root.mainloop()
