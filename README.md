Inbetriebnahme-Anleitung
System: Mutteruhrsteuerung – Version 6.2.1
Ersteller: Wolfram
Stand: 2025-07-28

1. Ziel und Zweck
Diese Anleitung beschreibt die vollständige Erstinbetriebnahme der Mutteruhrsteuerung auf Raspberry Pi inklusive:

Anschluss und Test der Ausgangsrelais oder H-Brücken

Parametrierung der Linien

Kontrolle der Impulsgebung

Systemstart und Funktionstest

Aktivierung des Webinterfaces

Die Anlage steuert bis zu vier historische Nebenuhren über potentialfreie Relaiskontakte oder H-Brücken (Lavetmotor-Ansteuerung). Alle Steuerdaten werden im internen FRAM und einer .conf-Datei abgelegt.

2. Voraussetzungen
Hardware
Raspberry Pi 3/4 mit PiOS

pigpio-Dienst installiert und gestartet (sudo pigpiod)

FRAM (via I2C) vorhanden und korrekt adressiert (Start bei 0x00)

Relaiskarte angeschlossen (je Linie: 2 GPIOs für Positiv/Negativ)

 - Alternativ die beiliegenden Schaltpläne für H-Brücke, dann eine Variable setzen....

Netzwerkverbindung (für Webinterface)

Software
Python 3 installiert

adafruit_fram, pigpio, busio, board installiert (via pip3)

Ordner /opt/mutteruhr mit folgenden Dateien:

main.py (aktuelle Version)

mutteruhr.conf

clocks.py (falls Anzeige gewünscht)

evtl. Webinterface-Komponenten

Datei-Berechtigungen korrekt gesetzt (chmod +x für main.py)

3. Verdrahtung
GPIO-Belegung (Beispielhaft)
Linie	GPIO POS	GPIO NEG\n
1	16	17\n
2	22	23\n
3	24	25\n
4	26	27\n
Achten Sie darauf, dass pro Linie nicht beide Ausgänge gleichzeitig LOW sein dürfen – dies könnte Kurzschlüsse verursachen. Die Software stellt dies sicher.

4. Konfigurationsdatei (mutteruhr.conf)
Bearbeiten Sie die Datei /opt/mutteruhr/mutteruhr.conf. Achten Sie darauf, pro Linie den Abschnitt LinieX mit folgenden Werten zu definieren:

ini
Kopieren
Bearbeiten
[Linie1]
gpio_pos = 16
gpio_neg = 17
impuls_ms = 500
pause_ms = 200
modus_24h = true
stopp = false
aktiv = true
name = Historische Uhr 1
Zusätzliche Sektion:

ini
Kopieren
Bearbeiten
[System]
conf_verbose = 3
WebActive = true
Tipp: Für Testbetrieb stopp = true setzen und später im Webinterface deaktivieren.

5. Inbetriebnahme-Schritte
5.1 Start der Hauptsoftware
Kopieren des kompletten Ordners mutteruhr nach /opt
Bearbeiten
cd /opt/mutteruhr
python3 main.py
Sie sehen die Startup-Meldungen, gefolgt von laufender Ausgabe (je nach verbose):

GPIO-Konfiguration

Laden von FRAM-Daten

Startup-Phase 1–9

Webserverstart (bei Startup 7)

Hauptschleife

5.2 Prüfung der Relaisausgänge
Erhöhen Sie bei Bedarf conf_verbose = 5 in der mutteruhr.conf, um jede Impulsausgabe auf der Konsole zu verfolgen.

Beispielausgabe bei aktiver Linie:

[Linie1] Sende Puls 127
[Linie1] Puls an (GPIO 17)
[Linie1] Puls aus (beide HIGH)

5.3 Kontrolle der Systemzeit
Die Steuerung verwendet die Systemzeit des Raspberry Pi. Prüfen Sie diese mit:
date
Stellen Sie sicher, dass die Zeit über timedatectl oder NTP korrekt synchronisiert ist. Die Systemzeit ist der Referenzpunkt für Sollzeit!
Es empfiehlt sich am i2c-Bus eine RTC anzuschließen.

5.4 Webinterface starten und testen
main.py startet automatisch einen Webserver auf Port 8080.

Rufen Sie im Browser http://\<IP ihres RPi\>:8080 auf

Prüfen Sie: Statusanzeigen, Bearbeiten funktioniert?

Stellen Sie Uhrzeit einer Linie testweise und beobachten Sie Ergebnis

6. Besonderheiten und Verhalten
   
6.1 Pulsausgabe
Nur bei aktiv = true UND stopp = false

Impulse erfolgen, wenn istpuls ≠ sollpuls (mit Toleranz)

Bei zu großem Vorsprung (z. B. durch Sommerzeitumstellung) → „WARTEN“-Modus aktiviert

6.2 Umstellung zwischen 12h- und 24h-Modus
Bei modus_24h = false (12h): max. 720 Pulse/Tag

Bei Umstellung erfolgt automatische Korrektur von istpuls

Zeiteingabe > 12:00 im 12h-Modus → automatisch istpuls -= 720

7. Wartung
FRAM wird regelmäßig aktualisiert nach jedem Setzen eines Ausgangs

Config-Änderungen über Webinterface → automatische .conf-Aktualisierung

Bei manuellem Stop des Programms: SIGTERM abwarten, um Dateizugriffe sauber zu beenden

8. Fehlerbehebung
Fehlerbild	Mögliche Ursache	Lösung
Keine Impulse	Linie stopp = true, aktiv = false	In .conf oder Web prüfen
„WARTEN“ wird angezeigt	istpuls liegt >65 über Sollzeit	Uhrzeit war voreilig eingestellt
Webinterface nicht erreichbar	Port blockiert, Adresse falsch	conf_verbose > 0 setzen und Logs prüfen
Falsche Uhrzeit	Falsche Moduswahl (12h/24h)	Modus und istpuls prüfen
9. Abschließender Funktionstest
Für jede Linie:

Anzeige „läuft“ sichtbar?

istpuls plausibel?

Relais klicken hörbar?

Uhr geht sichtbar im Takt weiter?

Nur wenn alle Punkte erfüllt sind, ist die Inbetriebnahme erfolgreich abgeschlossen.

