import os
import shutil
from send2trash import send2trash
from typing import Optional
from scanner import compute_hash

def copy_file(source_path: str, target_dir: str, relative_path: str, expected_hash: Optional[str] = None) -> str:
    """
    Kopiert eine Datei sicher in das Zielverzeichnis.

    Wenn die Datei aus einem Verzeichnis-Scan stammt, wird die Ordnerstruktur
    anhand des `relative_path` im Ziel reproduziert. War die Quelle eine
    einzelne Datei, ist der `relative_path` nur der Dateiname, und sie wird
    flach ins Ziel kopiert.

    Args:
        source_path: Absoluter Pfad der Quelldatei
        target_dir:  Absoluter Pfad des Ziel-Hauptordners (wohin kopiert werden soll)
        relative_path: Der relative Pfad der Datei (zur Beibehaltung der Struktur)

    Returns:
        Absoluter Pfad der neuen Zieldatei

    Raises:
        OSError, PermissionError, etc., falls das Kopieren fehlschlägt
    """
    # Konstruiere den vollen Zielpfad inkl. Unterordner
    target_path = os.path.join(target_dir, relative_path)
    
    # Stelle sicher, dass die nötigen Unterordner existieren
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    
    # Kopiere die Datei (kopiert auch Metadaten wie Zeitstempel)
    shutil.copy2(source_path, target_path)
    
    # Hash-Verifikation
    if expected_hash:
        if expected_hash.startswith("FAST_"):
            try:
                expected_size = int(expected_hash.split("_")[1])
                target_size = os.path.getsize(target_path)
                if expected_size != target_size:
                    try:
                        os.remove(target_path)
                    except OSError:
                        pass
                    raise IOError("Kopieren fehlgeschlagen: Dateigröße stimmt nach Kopieren nicht überein.")
            except (IndexError, ValueError):
                pass
        else:
            copied_hash = compute_hash(target_path)
            if copied_hash != expected_hash:
                # Beschädigte Datei löschen
                try:
                    os.remove(target_path)
                except OSError:
                    pass
                raise IOError("Kopieren fehlgeschlagen: Datei-Integritätsprüfung (Hash) fehlerhaft.")
            
    return target_path

def move_to_trash(filepath: str) -> bool:
    """
    Verschiebt eine Datei sicher in den Papierkorb des Betriebssystems.

    Verwendet send2trash, um zu verhindern, dass Dateien unwiderruflich
    gelöscht werden.

    Args:
        filepath: Absoluter Pfad der zu löschenden Datei

    Returns:
        True, wenn erfolgreich verschoben, False falls ein Fehler auftrat
    """
    try:
        if os.path.exists(filepath):
            send2trash(filepath)
            return True
        return False
    except Exception as e:
        print(f"⚠️  Fehler beim Verschieben in den Papierkorb ({filepath}): {e}")
        return False
