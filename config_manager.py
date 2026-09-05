import json
import os
from typing import Dict, Any

CONFIG_FILE = "config.json"

def load_config() -> Dict[str, Any]:
    """Lädt die Konfiguration von der Festplatte."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Fehler beim Laden der Config: {e}")
    
    # Standard-Konfiguration, falls keine Datei existiert
    return {
        "source_path": "",
        "target_path": "",
        "fast_mode": True,
        "update_cache": False
    }

def save_config(source_path: str, target_path: str, fast_mode: bool, update_cache: bool) -> None:
    """Speichert die aktuelle UI-Konfiguration auf die Festplatte."""
    config = {
        "source_path": source_path,
        "target_path": target_path,
        "fast_mode": fast_mode,
        "update_cache": update_cache
    }
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"⚠️  Fehler beim Speichern der Config: {e}")
