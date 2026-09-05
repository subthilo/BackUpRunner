import sqlite3
import os
from scanner import FileInfo

DB_FILE = "nas_cache.db"

def _get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS target_cache (
            absolute_path TEXT PRIMARY KEY,
            size INTEGER,
            modified_time REAL,
            hash TEXT
        )
    ''')
    # Ein Index auf absolute_path macht LIKE-Abfragen wesentlich schneller
    conn.execute('CREATE INDEX IF NOT EXISTS idx_path ON target_cache(absolute_path)')
    return conn

def has_target_cache() -> bool:
    """Prüft, ob die Datenbank existiert und Einträge hat."""
    if not os.path.exists(DB_FILE):
        return False
    try:
        with _get_conn() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM target_cache")
            return cursor.fetchone()[0] > 0
    except Exception:
        return False

def load_target_cache(target_root: str) -> tuple[list[FileInfo], int]:
    """
    Lädt alle Dateien aus der Datenbank, die im angegebenen target_root liegen.
    Die relativen Pfade werden passend zum target_root dynamisch on-the-fly berechnet.
    """
    if not has_target_cache():
        return [], 0
        
    try:
        # Pfad-Prefix normalisieren (mit Slash am Ende, außer es ist root)
        prefix = target_root if target_root.endswith(os.sep) else target_root + os.sep
        query_pattern = f"{prefix}%"
        
        with _get_conn() as conn:
            cursor = conn.execute(
                "SELECT absolute_path, size, modified_time, hash FROM target_cache WHERE absolute_path LIKE ? OR absolute_path = ?",
                (query_pattern, target_root)
            )
            rows = cursor.fetchall()
            
        files = []
        total_size = 0
        for row in rows:
            abs_path = row[0]
            # relativen Pfad passend zum gewählten Zielordner dynamisch berechnen
            rel_path = os.path.relpath(abs_path, target_root)
            
            files.append(FileInfo(
                absolute_path=abs_path,
                relative_path=rel_path,
                size=row[1],
                modified_time=row[2],
                hash=row[3]
            ))
            total_size += row[1]
            
        return files, total_size
    except Exception as e:
        print(f"⚠️  Fehler beim Laden des Caches: {e}")
        return [], 0

def save_target_cache(target_root: str, files: list[FileInfo]) -> None:
    """
    Speichert einen neuen Scan in der Datenbank ab.
    Dabei werden nur die alten Einträge für GENAU DIESEN Unterordner gelöscht.
    Der Rest des NAS bleibt im Gedächtnis!
    """
    prefix = target_root if target_root.endswith(os.sep) else target_root + os.sep
    query_pattern = f"{prefix}%"
    
    try:
        with _get_conn() as conn:
            # 1. Alte Einträge für diesen Ordner löschen
            conn.execute(
                "DELETE FROM target_cache WHERE absolute_path LIKE ? OR absolute_path = ?",
                (query_pattern, target_root)
            )
            
            # 2. Neue (frisch gescannte) Einträge einfügen
            data = [(f.absolute_path, f.size, f.modified_time, f.hash) for f in files]
            conn.executemany(
                "INSERT INTO target_cache (absolute_path, size, modified_time, hash) VALUES (?, ?, ?, ?)",
                data
            )
    except Exception as e:
        print(f"⚠️  Fehler beim Speichern des Caches: {e}")

def add_to_target_cache(file_info: FileInfo) -> None:
    """
    Fügt eine einzelne kopierte Datei der Datenbank hinzu.
    """
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO target_cache (absolute_path, size, modified_time, hash) VALUES (?, ?, ?, ?)",
                (file_info.absolute_path, file_info.size, file_info.modified_time, file_info.hash)
            )
    except Exception as e:
        print(f"⚠️  Fehler beim Update des Caches: {e}")
