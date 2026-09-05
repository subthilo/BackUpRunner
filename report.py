"""
report.py – CSV-Report-Export für Vergleichsergebnisse
=======================================================

Dieses Modul exportiert die Ergebnisse eines Verzeichnisvergleichs als
CSV-Datei. Der Report enthält alle verglichenen Dateien mit ihrem Status,
Pfaden, Größen und Hashes.

Der CSV-Report dient dazu:
- Den Überblick zu behalten, welche Festplatten/Ordner bereits geprüft wurden
- Die Ergebnisse offline durchzusehen (z.B. in Excel oder Numbers)
- Eine Dokumentation des Backup-Zustands zu haben

Verwendung:
    from report import export_csv
    from comparator import ComparisonResult

    result: ComparisonResult = ...  # aus compare_directories()
    export_csv(result, "/Users/thilo/Desktop/backup_report.csv")

Autor: BackUpRunner
"""

import csv
import os
from datetime import datetime
from comparator import ComparisonResult, FileStatus


def format_size(size_bytes: int) -> str:
    """
    Formatiert eine Dateigröße in Bytes zu einer lesbaren Darstellung.

    Verwendet binäre Einheiten (1 KB = 1024 Bytes), da das der Darstellung
    in macOS Finder und den meisten Dateisystemen entspricht.

    Args:
        size_bytes: Größe in Bytes

    Returns:
        Formatierter String (z.B. "4.2 MB", "1.8 GB", "512 B")

    Beispiele:
        format_size(0)           → "0 B"
        format_size(1023)        → "1023 B"
        format_size(1024)        → "1.0 KB"
        format_size(1048576)     → "1.0 MB"
        format_size(5368709120)  → "5.0 GB"
    """
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} B"
    return f"{size:.1f} {units[unit_index]}"


def export_csv(result: ComparisonResult, output_path: str) -> str:
    """
    Exportiert die Vergleichsergebnisse als CSV-Datei.

    Die CSV-Datei enthält folgende Spalten:
    - Kategorie:        Status der Datei (Identisch, Anderer Pfad, Kein Backup, Duplikat)
    - Quelle_Pfad:      Absoluter Pfad der Quelldatei
    - Quelle_Relativ:   Relativer Pfad der Quelldatei
    - Groesse:          Dateigröße (formatiert, z.B. "4.2 MB")
    - Groesse_Bytes:    Dateigröße in Bytes (für Sortierung/Berechnung)
    - SHA256:           Hash der Datei
    - Ziel_Fundorte:    Alle Fundorte im Ziel, getrennt durch " | "

    Am Ende der CSV wird eine Zusammenfassung als Kommentarzeilen angefügt.

    Args:
        result:      ComparisonResult aus compare_directories()
        output_path: Pfad für die CSV-Ausgabedatei

    Returns:
        Absoluter Pfad der erzeugten CSV-Datei

    Raises:
        OSError: Wenn die Datei nicht geschrieben werden kann
    """
    # Sicherstellen, dass das Zielverzeichnis existiert
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        # ── Header-Zeile ──
        writer.writerow([
            "Kategorie",
            "Quelle_Pfad",
            "Quelle_Relativ",
            "Groesse",
            "Groesse_Bytes",
            "SHA256",
            "Ziel_Fundorte"
        ])

        # ── Identische Dateien (Hash + Pfad stimmen überein) ──
        for item in result.identical:
            writer.writerow([
                "Identisch",
                item.source_file.absolute_path,
                item.source_file.relative_path,
                format_size(item.source_file.size),
                item.source_file.size,
                item.source_file.hash,
                " | ".join(item.target_paths)
            ])

        # ── Dateien mit anderem Pfad (Hash gefunden, Pfad anders) ──
        for item in result.moved:
            writer.writerow([
                "Anderer Pfad",
                item.source_file.absolute_path,
                item.source_file.relative_path,
                format_size(item.source_file.size),
                item.source_file.size,
                item.source_file.hash,
                " | ".join(item.target_paths)
            ])

        # ── Dateien ohne Backup ──
        for item in result.no_backup:
            writer.writerow([
                "Kein Backup",
                item.source_file.absolute_path,
                item.source_file.relative_path,
                format_size(item.source_file.size),
                item.source_file.size,
                item.source_file.hash,
                ""
            ])

        # ── Duplikate im Ziel ──
        # Für Duplikate gibt es keine Quelldatei – es sind reine Ziel-Einträge
        for dup in result.duplicates:
            writer.writerow([
                "Duplikat im Ziel",
                "",  # keine Quelldatei
                "",
                format_size(dup.size),
                dup.size,
                dup.hash,
                " | ".join(dup.paths)
            ])

        # ── Zusammenfassung als Kommentarzeilen ──
        writer.writerow([])  # Leerzeile
        writer.writerow(["# === ZUSAMMENFASSUNG ==="])
        writer.writerow([f"# Quellverzeichnis: {result.source_root}"])
        writer.writerow([f"# Zielverzeichnis: {result.target_root}"])
        writer.writerow([f"# Quelldateien gesamt: {result.source_count}"])
        writer.writerow([f"# Zieldateien gesamt: {result.target_count}"])
        writer.writerow([f"# Identisch (Hash + Pfad): {len(result.identical)}"])
        writer.writerow([f"# Anderer Pfad (Hash gefunden): {len(result.moved)}"])
        writer.writerow([f"# Kein Backup: {len(result.no_backup)}"])
        writer.writerow([f"# Duplikate im Ziel: {len(result.duplicates)} Gruppen"])
        writer.writerow([f"# Erstellt am: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])

    return os.path.abspath(output_path)
