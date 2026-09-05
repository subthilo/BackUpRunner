# Architektur – BackUpRunner

Dieses Dokument beschreibt die technische Architektur und die Designentscheidungen von BackUpRunner.

## Überblick

```
┌────────────────────────────────────────────────────┐
│                    main.py                         │
│              (Kivy App + Screens)                  │
│                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ Select   │→ │ Scan     │→ │ Result           │ │
│  │ Screen   │  │ Screen   │  │ Screen           │ │
│  └──────────┘  └────┬─────┘  └────────┬─────────┘ │
│                     │                 │            │
└─────────────────────┼─────────────────┼────────────┘
                      │                 │
          ┌───────────▼────────┐  ┌─────▼──────┐
          │     scanner.py     │  │  report.py  │
          │  (Scan + Hashing)  │  │ (CSV-Export)│
          └───────────┬────────┘  └────────────┘
                      │
          ┌───────────▼────────┐
          │   comparator.py    │
          │  (Hash-Vergleich)  │
          └────────────────────┘
```

## Module im Detail

### scanner.py

**Aufgabe**: Verzeichnisse rekursiv scannen und SHA-256-Hashes berechnen.

**Kernkomponenten**:

| Komponente | Beschreibung |
|---|---|
| `FileInfo` (dataclass) | Speichert Pfad, Größe, Änderungszeit und Hash einer Datei |
| `compute_hash()` | Berechnet SHA-256 in 8-KB-Chunks (memory-schonend) |
| `count_files()` | Zählt Dateien für die Fortschrittsanzeige |
| `scan_directory()` | Hauptfunktion: scannt rekursiv und hasht jede Datei |
| `build_hash_index()` | Erstellt `dict[hash] → [pfade]` für schnelles Lookup |

**Designentscheidungen**:

- **8 KB Chunk-Größe**: Kompromiss zwischen Geschwindigkeit und Speicherverbrauch. Bei 1-TB-Dateien wird nie mehr als 8 KB gleichzeitig im Speicher gehalten.
- **Symlinks werden übersprungen**: Verhindert Endlosschleifen bei zirkulären Links.
- **Fehlertoleranz**: Dateien, die nicht gelesen werden können (Berechtigungen, defekte Sektoren), werden übersprungen statt den gesamten Scan abzubrechen.
- **Progress-Callback**: Erlaubt der UI, den Fortschritt anzuzeigen, ohne dass Scanner und UI gekoppelt sind.

### comparator.py

**Aufgabe**: Quelldateien gegen den Hash-Index des Zielverzeichnisses vergleichen.

**Kernkomponenten**:

| Komponente | Beschreibung |
|---|---|
| `FileStatus` (Enum) | `IDENTICAL`, `MOVED`, `NO_BACKUP` |
| `ComparedFile` (dataclass) | Ergebnis für eine einzelne Quelldatei |
| `DuplicateGroup` (dataclass) | Gruppe von Dateien im Ziel mit gleichem Hash |
| `ComparisonResult` (dataclass) | Gesamtergebnis mit allen Kategorien |
| `compare_directories()` | Hauptfunktion: führt den Vergleich durch |

**Vergleichs-Algorithmus**:

```
Für jede Quelldatei:
  1. Ist der SHA-256-Hash im Ziel-Index vorhanden?
     NEIN → Status: NO_BACKUP (kein Backup)
     JA   → Weiter zu 2.

  2. Stimmt der relative Pfad mit einem Zielpfad überein,
     der den gleichen Hash hat?
     JA   → Status: IDENTICAL (perfektes Backup)
     NEIN → Status: MOVED (Backup an anderer Stelle)

Zusätzlich:
  Alle Hashes im Ziel-Index, die > 1 Pfad haben → Duplikate
```

**Warum pfad-unabhängig?**

Das Backup-Chaos entsteht oft dadurch, dass Dateien umbenannt oder in andere Ordner verschoben werden. Ein reiner Pfad-Vergleich würde diese Dateien als "nicht gesichert" melden, obwohl der Inhalt identisch vorhanden ist. Der Hash-Vergleich löst dieses Problem.

**Relative-Pfad-Prüfung**:

Zusätzlich zum Hash prüfen wir, ob der relative Pfad übereinstimmt. Das ist wichtig um zu unterscheiden:
- "Die Datei ist gesichert UND liegt am gleichen Ort" (IDENTICAL)
- "Die Datei ist gesichert, liegt aber woanders" (MOVED)

### report.py

**Aufgabe**: Vergleichsergebnisse als CSV-Datei exportieren.

**CSV-Spalten**:

| Spalte | Beschreibung |
|---|---|
| `Kategorie` | Identisch, Anderer Pfad, Kein Backup, Duplikat im Ziel |
| `Quelle_Pfad` | Absoluter Pfad der Quelldatei |
| `Quelle_Relativ` | Relativer Pfad (für bessere Lesbarkeit) |
| `Groesse` | Formatierte Größe (z.B. "4.2 MB") |
| `Groesse_Bytes` | Größe in Bytes (für Sortierung in Excel) |
| `SHA256` | Hash der Datei |
| `Ziel_Fundorte` | Fundorte im Ziel, getrennt durch ` | ` |

Am Ende der CSV steht eine Zusammenfassung mit Statistiken und Metadaten.

### main.py

**Aufgabe**: Kivy-App mit drei Screens und Threading.

**Threading-Modell**:

```
Main-Thread (Kivy UI)          Hintergrund-Thread (Scan)
━━━━━━━━━━━━━━━━━━━            ━━━━━━━━━━━━━━━━━━━━━━━━
     │                              │
     │  start_scan() ──────────────►│
     │                              │ scan_directory(source)
     │  ◄── Clock.schedule_once ────│ (Fortschritt)
     │  UI aktualisieren            │
     │                              │ scan_directory(target)
     │  ◄── Clock.schedule_once ────│ (Fortschritt)
     │  UI aktualisieren            │
     │                              │ compare_directories()
     │  ◄── Clock.schedule_once ────│
     │  Ergebnisse anzeigen         │
     ▼                              ▼
```

Kivy erlaubt UI-Änderungen nur aus dem Main-Thread. Daher wird `Clock.schedule_once()` verwendet, um Updates aus dem Hintergrund-Thread an den Main-Thread zu übergeben.

### backuprunner.kv

**Aufgabe**: UI-Layout in Kivy Language.

**Farbschema (Catppuccin Mocha)**:

| Element | Farbe | Hex |
|---|---|---|
| Hintergrund | Dunkelblau-Grau | `#1e1e2e` |
| Text | Hell-Lavendel | `#cdd6f4` |
| Gedämpfter Text | Grau | `#9399b2` |
| Akzent (Buttons) | Blau | `#89b4fa` |
| Erfolg | Grün | `#a6e3a1` |
| Warnung | Gelb | `#f9e2af` |
| Fehler | Rot | `#f38ba8` |
| Info/Moved | Lila | `#cba6f7` |

## Datenfluss

```
Benutzer wählt:
  Quelle: /Volumes/USB/Projekte
  Ziel:   /Volumes/NAS/Backups

         ┌──────────────────────┐
         │   scan_directory()   │
         │   (Quelle scannen)   │
         └──────────┬───────────┘
                    ▼
         source_files: [FileInfo, FileInfo, ...]

         ┌──────────────────────┐
         │   scan_directory()   │
         │   (Ziel scannen)     │
         └──────────┬───────────┘
                    ▼
         target_files: [FileInfo, FileInfo, ...]

         ┌──────────────────────┐
         │  build_hash_index()  │
         └──────────┬───────────┘
                    ▼
         target_index: {
           "a1b2c3...": ["/Volumes/NAS/Backups/Fotos/bild.jpg"],
           "d4e5f6...": ["/Volumes/NAS/Backups/alt/doc.pdf",
                         "/Volumes/NAS/Backups/neu/doc.pdf"],  ← Duplikat!
         }

         ┌────────────────────────┐
         │  compare_directories() │
         └──────────┬─────────────┘
                    ▼
         ComparisonResult:
           identical:  [ComparedFile, ...]  ← Hash + Pfad gleich
           moved:      [ComparedFile, ...]  ← Hash gleich, Pfad anders
           no_backup:  [ComparedFile, ...]  ← Hash nicht gefunden
           duplicates: [DuplicateGroup, ...]← Gleicher Hash, >1 Pfad im Ziel

         ┌──────────────────────┐
         │    export_csv()      │
         └──────────┬───────────┘
                    ▼
         backup_report_20260905_103000.csv
```

## Performance-Überlegungen

### Bottleneck: I/O beim Hashen

Das Berechnen von SHA-256 erfordert, jede Datei vollständig zu lesen. Bei Netzwerklaufwerken ist das der größte Flaschenhals.

| Datenmenge | Geschätzte Dauer (lokal) | Geschätzte Dauer (NAS/Netzwerk) |
|---|---|---|
| 10 GB | ~1 Minute | ~5 Minuten |
| 100 GB | ~10 Minuten | ~30-60 Minuten |
| 1 TB | ~1-2 Stunden | ~3-6 Stunden |

### Mögliche Optimierungen (Phase 2)

- **Hash-Index cachen**: Den Ziel-Index als JSON speichern, damit das NAS nicht bei jedem Vergleich neu gescannt werden muss.
- **Vorab-Filter**: Erst nach Dateiname + Größe filtern, dann nur bei Verdacht hashen.
- **Parallelisierung**: Mehrere Dateien gleichzeitig hashen (Multi-Threading).
