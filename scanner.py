"""
scanner.py – Verzeichnis-Scanner mit Hash-Berechnung
=====================================================

Dieses Modul scannt ein Verzeichnis rekursiv und berechnet für jede Datei
einen SHA-256-Hash. Die Ergebnisse werden als Liste von FileInfo-Objekten
und optional als Hash-Index (dict[hash] → [pfade]) zurückgegeben.

Verwendung:
    from scanner import scan_directory, build_hash_index

    # Verzeichnis scannen
    files, total_size = scan_directory("/pfad/zum/ordner", progress_callback)

    # Hash-Index für schnelles Lookup aufbauen
    index = build_hash_index(files)

Autor: BackUpRunner
"""

import os
import hashlib
from dataclasses import dataclass, field
from typing import Callable, Optional


# Chunk-Größe für das Lesen großer Dateien (8 KB).
# Dateien werden in Stücken dieser Größe gelesen, um den Speicherverbrauch
# bei sehr großen Dateien (z.B. Videos, Disk-Images) gering zu halten.
CHUNK_SIZE = 8192


@dataclass
class FileInfo:
    """
    Speichert alle relevanten Informationen über eine gescannte Datei.

    Attributes:
        absolute_path:  Vollständiger Pfad zur Datei (z.B. /Volumes/NAS/Backup/foto.jpg)
        relative_path:  Pfad relativ zum gescannten Wurzelverzeichnis (z.B. Backup/foto.jpg)
        size:           Dateigröße in Bytes
        modified_time:  Letzte Änderungszeit als Unix-Timestamp
        hash:           SHA-256 Hashwert der Datei (hex-String, 64 Zeichen)
    """
    absolute_path: str
    relative_path: str
    size: int
    modified_time: float
    hash: str = ""


def compute_hash(filepath: str) -> str:
    """
    Berechnet den SHA-256-Hash einer Datei.

    Die Datei wird in Chunks gelesen (CHUNK_SIZE = 8 KB), damit auch
    sehr große Dateien verarbeitet werden können, ohne den gesamten
    Inhalt in den Arbeitsspeicher zu laden.

    Args:
        filepath: Absoluter Pfad zur Datei

    Returns:
        SHA-256 Hashwert als Hex-String (64 Zeichen)

    Raises:
        OSError: Wenn die Datei nicht gelesen werden kann
        PermissionError: Wenn keine Leserechte vorhanden sind
    """
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def count_files(directory: str) -> int:
    """
    Zählt die Anzahl der Dateien in einem Verzeichnis (rekursiv).

    Wird vor dem eigentlichen Scan aufgerufen, um die Gesamtanzahl
    für die Fortschrittsanzeige zu ermitteln.

    Args:
        directory: Pfad zum Verzeichnis

    Returns:
        Anzahl der Dateien im Verzeichnis (rekursiv)
    """
    count = 0
    for _, _, files in os.walk(directory):
        count += len(files)
    return count


def scan_directory(
    directory: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> tuple[list[FileInfo], int]:
    """
    Scannt ein Verzeichnis rekursiv und berechnet SHA-256-Hashes.

    Durchläuft alle Dateien im angegebenen Verzeichnis und dessen
    Unterverzeichnissen. Für jede Datei werden Pfad, Größe, Änderungszeit
    und SHA-256-Hash erfasst.

    Symbolische Links werden übersprungen, um Endlosschleifen zu vermeiden.
    Dateien, die nicht gelesen werden können (z.B. Berechtigungsprobleme),
    werden mit einer Warnung übersprungen.

    Args:
        directory:          Pfad zum zu scannenden Verzeichnis
        progress_callback:  Optionale Callback-Funktion, die bei jeder
                            verarbeiteten Datei aufgerufen wird.
                            Parameter: (aktuelle_datei_nr, gesamt_dateien, aktueller_pfad)

    Returns:
        Tuple aus:
        - Liste von FileInfo-Objekten für jede erfolgreich gescannte Datei
        - Gesamtgröße aller gescannten Dateien in Bytes

    Beispiel:
        def on_progress(current, total, path):
            print(f"[{current}/{total}] {path}")

        files, total = scan_directory("/Volumes/USB/Projekte", on_progress)
        print(f"{len(files)} Dateien gescannt, {total / 1e9:.1f} GB")
    """
    # Verzeichnis normalisieren (trailing slashes entfernen etc.)
    directory = os.path.normpath(directory)

    # Zuerst Gesamtanzahl ermitteln für Fortschrittsanzeige
    total_files = count_files(directory)

    files: list[FileInfo] = []
    total_size = 0
    current_count = 0

    # os.walk durchläuft das Verzeichnis rekursiv:
    # root = aktuelles Verzeichnis
    # dirs = Liste der Unterverzeichnisse (wird nicht gebraucht)
    # filenames = Liste der Dateien im aktuellen Verzeichnis
    for root, dirs, filenames in os.walk(directory, followlinks=False):
        for filename in filenames:
            absolute_path = os.path.join(root, filename)

            # Symbolische Links überspringen – könnten Zyklen verursachen
            if os.path.islink(absolute_path):
                current_count += 1
                continue

            # Relativen Pfad berechnen (z.B. "Fotos/2024/urlaub.jpg")
            relative_path = os.path.relpath(absolute_path, directory)

            try:
                # Datei-Metadaten lesen
                stat = os.stat(absolute_path)
                size = stat.st_size
                modified_time = stat.st_mtime

                # SHA-256 Hash berechnen
                file_hash = compute_hash(absolute_path)

                # FileInfo erstellen und zur Liste hinzufügen
                file_info = FileInfo(
                    absolute_path=absolute_path,
                    relative_path=relative_path,
                    size=size,
                    modified_time=modified_time,
                    hash=file_hash
                )
                files.append(file_info)
                total_size += size

            except (OSError, PermissionError) as e:
                # Datei konnte nicht gelesen werden – überspringen und warnen
                print(f"⚠️  Übersprungen (Fehler): {absolute_path} – {e}")

            current_count += 1

            # Fortschritts-Callback aufrufen, falls vorhanden
            if progress_callback:
                progress_callback(current_count, total_files, absolute_path)

    return files, total_size


def build_hash_index(files: list[FileInfo]) -> dict[str, list[str]]:
    """
    Erstellt einen Hash-Index aus einer Liste von FileInfo-Objekten.

    Der Index ermöglicht schnelles Nachschlagen: "Gibt es irgendwo eine
    Datei mit diesem Hash?" – unabhängig vom Dateinamen oder Pfad.

    Wenn ein Hash mehrfach vorkommt (= Duplikate), enthält die Liste
    alle Pfade zu diesen identischen Dateien.

    Args:
        files: Liste von FileInfo-Objekten (typischerweise aus scan_directory())

    Returns:
        Dictionary: SHA-256 Hash → Liste aller absoluten Pfade mit diesem Hash

    Beispiel:
        index = build_hash_index(target_files)

        # Prüfen ob eine Datei im Backup existiert
        if source_file.hash in index:
            print(f"Gefunden unter: {index[source_file.hash]}")

        # Duplikate finden (Hash mit mehr als einem Pfad)
        duplicates = {h: paths for h, paths in index.items() if len(paths) > 1}
    """
    index: dict[str, list[str]] = {}
    for file_info in files:
        if file_info.hash not in index:
            index[file_info.hash] = []
        index[file_info.hash].append(file_info.absolute_path)
    return index
