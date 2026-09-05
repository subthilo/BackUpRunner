import json
import os
from scanner import FileInfo

CACHE_FILE = "target_cache.json"

def has_target_cache() -> bool:
    """Prüft, ob ein Cache existiert."""
    return os.path.exists(CACHE_FILE)

def load_target_cache() -> tuple[list[FileInfo], int]:
    """
    Lädt den NAS-Index aus dem lokalen Cache.
    Gibt ein Tuple (files, total_size) zurück, genau wie scan_directory().
    """
    if not has_target_cache():
        return [], 0
        
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        files = []
        total_size = 0
        for item in data:
            files.append(FileInfo(
                absolute_path=item["absolute_path"],
                relative_path=item["relative_path"],
                size=item["size"],
                modified_time=item["modified_time"],
                hash=item["hash"]
            ))
            total_size += item["size"]
            
        return files, total_size
    except Exception as e:
        print(f"⚠️  Fehler beim Laden des Caches: {e}")
        return [], 0

def save_target_cache(files: list[FileInfo]) -> None:
    """
    Speichert den frisch gescannten NAS-Index auf der Festplatte ab.
    """
    data = []
    for f in files:
        data.append({
            "absolute_path": f.absolute_path,
            "relative_path": f.relative_path,
            "size": f.size,
            "modified_time": f.modified_time,
            "hash": f.hash
        })
        
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"⚠️  Fehler beim Speichern des Caches: {e}")

def add_to_target_cache(file_info: FileInfo) -> None:
    """
    Fügt eine einzelne kopierte Datei dem existierenden Cache hinzu.
    Überschreibt existierende Einträge mit dem gleichen relativen Pfad.
    """
    if not has_target_cache():
        return
        
    files, _ = load_target_cache()
    
    # Vorhandene Datei mit gleichem Pfad entfernen (Überschreiben)
    files = [f for f in files if f.relative_path != file_info.relative_path]
    
    files.append(file_info)
    save_target_cache(files)
