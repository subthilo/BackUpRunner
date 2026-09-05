import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import subprocess
import os
import sys

# Globale Variable für den Kivy-Prozess
kivy_process = None

# Pfade ermitteln
base_dir = os.path.dirname(os.path.abspath(__file__))
main_py_path = os.path.join(base_dir, "main.py")
venv_python = os.path.join(base_dir, ".venv", "bin", "python")
python_bin = venv_python if os.path.exists(venv_python) else sys.executable

def create_image():
    """Erstellt ein simples Icon für die Menüleiste (Blauer Punkt auf dunklem Grund)"""
    # Da pystray auf macOS manchmal zickig mit Emojis ist, zeichnen wir ein sauberes Icon
    image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0)) # Transparent
    dc = ImageDraw.Draw(image)
    dc.ellipse((8, 8, 56, 56), fill=(137, 180, 250)) # Akzent-Blau
    return image

def start_app(icon, item):
    """Startet die eigentliche Kivy-App"""
    global kivy_process
    if kivy_process and kivy_process.poll() is None:
        # App läuft bereits
        return
    try:
        kivy_process = subprocess.Popen(
            [python_bin, main_py_path],
            cwd=base_dir
        )
    except Exception as e:
        print(f"Fehler beim Starten der App: {e}")

def quit_app(icon, item):
    """Beendet den Launcher und ggf. die laufende App"""
    global kivy_process
    if kivy_process and kivy_process.poll() is None:
        kivy_process.terminate()
    icon.stop()

# Menü aufbauen
menu = pystray.Menu(
    item('BackUpRunner starten', start_app),
    item('Beenden', quit_app)
)

if __name__ == "__main__":
    print("Starte Menüleisten-Launcher...")
    icon = pystray.Icon("BackUpRunner", create_image(), "BackUpRunner", menu)
    icon.run()
