# BackUpRunner 🔍

**Backup-Analyse-Tool** – Finde heraus, welche deiner Dateien bereits gesichert sind und welche nicht.

## Das Problem

Du hast Daten auf vielen verschiedenen Festplatten verteilt. Durch frühere Backup-Versuche ist Chaos entstanden: Manche Dateien sind mehrfach vorhanden, manche fehlen im Backup, und manche liegen an unerwarteten Orten. Du brauchst Klarheit.

## Die Lösung

BackUpRunner vergleicht einen **Quellordner** (z.B. ein Projekt auf einer USB-Platte) gegen ein **Zielverzeichnis** (z.B. dein NAS-Backup). Der Vergleich ist **hash-basiert und pfad-unabhängig**: Egal wo im Backup eine Datei liegt – wenn der Inhalt (SHA-256) identisch ist, wird sie als gesichert erkannt.

## Features (Phase 1 – Analyse)

- 🔍 **Hash-basierter Vergleich**: Erkennt identische Dateien unabhängig vom Dateipfad
- 📊 **Vier Kategorien**:
  - ✅ **Identisch** – Hash + Pfad stimmen überein (perfektes Backup)
  - 🔀 **Anderer Pfad** – Hash gefunden, aber an anderer Stelle im Ziel
  - ⚠️ **Kein Backup** – Datei existiert nirgends im Ziel
  - 📋 **Duplikate** – Dateien, die mehrfach im Ziel existieren
- 💾 **CSV-Report**: Alle Ergebnisse als CSV exportieren
- 🖥️ **Desktop-App**: Kivy-basierte Oberfläche mit Dark Theme
- 🌐 **Netzwerklaufwerke**: Funktioniert mit lokalen und Netzwerk-Laufwerken (NAS via SMB/AFP)

## Installation

### Voraussetzungen

- Python 3.9+
- macOS (getestet), Linux (sollte funktionieren), Windows (nicht getestet)

### Setup

```bash
# Repository klonen
git clone <repo-url>
cd BackUpRunner

# Virtuelles Environment erstellen
python3 -m venv .venv
source .venv/bin/activate

# Abhängigkeiten installieren
pip install -r requirements.txt
```

## Verwendung

```bash
# Virtuelles Environment aktivieren (falls noch nicht aktiv)
source .venv/bin/activate

# App starten
python main.py
```

### Workflow

1. **Quellverzeichnis wählen**: Der Ordner, den du prüfen willst (z.B. `/Volumes/USB-Platte/Projekte`)
2. **Zielverzeichnis wählen**: Dein Backup-Root (z.B. `/Volumes/NAS/Backups`)
3. **"Analyse starten" klicken**: Die App scannt beide Verzeichnisse und berechnet SHA-256-Hashes
4. **Ergebnisse ansehen**: Vier Tabs zeigen dir, was gesichert ist und was fehlt
5. **CSV exportieren**: Speichert den Report auf deinem Desktop

### Tipps

- **Erster Scan dauert**: Besonders das Zielverzeichnis (NAS) kann bei großen Datenmengen dauern, da jede Datei gelesen und gehasht werden muss.
- **Netzwerklaufwerke**: Stelle sicher, dass das NAS eingebunden ist (im Finder sichtbar unter `/Volumes/`).
- **Große Datenmengen**: Der Fortschrittsbalken zeigt dir, wie weit der Scan ist.

## Projektstruktur

```
BackUpRunner/
├── main.py             # App-Einstiegspunkt, Screen-Management
├── backuprunner.kv     # UI-Layout (Kivy Language)
├── scanner.py          # Verzeichnis scannen + Hash-Berechnung
├── comparator.py       # Hash-Vergleich + Kategorisierung
├── report.py           # CSV-Report-Export
├── requirements.txt    # Python-Abhängigkeiten
├── README.md           # Diese Datei
├── ARCHITECTURE.md     # Technische Dokumentation
└── .venv/              # Virtuelles Environment (nicht im Git)
```

## Phase 2 (geplant)

Wenn die Analyse-Ergebnisse überzeugen, kommen folgende Features:
- 📁 Dateien ins Backup kopieren (Zielordner wählbar)
- 🗑️ Quelldateien in den Papierkorb verschieben (via `send2trash`)
- 💾 Hash-Index cachen (NAS nicht bei jedem Vergleich neu scannen)

## Lizenz

Privates Projekt.
