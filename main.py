"""
main.py – Hauptdatei der BackUpRunner-App
==========================================

BackUpRunner ist ein Kivy-basiertes Desktop-Tool zur Backup-Analyse.
Es vergleicht ein Quellverzeichnis gegen ein Zielverzeichnis (z.B. NAS)
und zeigt, welche Dateien bereits gesichert sind, welche fehlen und
welche Duplikate im Backup existieren.

Phase 1: Nur Analyse – kein Kopieren, kein Löschen.

Screens:
    1. SelectScreen  – Quell- und Zielverzeichnis wählen
    2. ScanScreen    – Fortschrittsanzeige während des Scannens
    3. ResultScreen  – Ergebnisse mit vier Kategorien + CSV-Export

Starten:
    python main.py

Autor: BackUpRunner
"""

import os
import threading
from datetime import datetime

import kivy
kivy.require('2.3.1')

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.clock import Clock
from kivy.properties import ObjectProperty, StringProperty
from kivy.core.window import Window

from scanner import scan_directory, build_hash_index
from comparator import compare_directories, ComparisonResult
from report import export_csv, format_size
from operations import copy_file, move_to_trash
import config_manager
import cache_manager


# ============================================================================
# Screen 1: Verzeichnisauswahl
# ============================================================================


def open_directory_chooser(title, callback):
    """Öffnet einen Dateibrowser zur Verzeichnisauswahl."""
    content = BoxLayout(orientation='vertical', spacing=10, padding=10)
    from kivy.uix.textinput import TextInput
    path_input = TextInput(
        text='/', hint_text='Pfad eingeben, z.B. /Volumes/MeinNAS', multiline=False,
        size_hint_y=None, height='40dp', font_size='14sp',
        background_color=(0.176, 0.176, 0.255, 1), foreground_color=(0.804, 0.839, 0.957, 1),
        cursor_color=(0.537, 0.706, 0.980, 1), padding=[10, 10, 10, 10]
    )
    content.add_widget(path_input)
    nav_layout = BoxLayout(size_hint_y=None, height='36dp', spacing=5)
    nav_volumes = CustomButton(text='📁 /Volumes', height='36dp', font_size='13sp')
    nav_home = CustomButton(text='🏠 Home', height='36dp', font_size='13sp')
    nav_root = CustomButton(text='💻 /', height='36dp', font_size='13sp')
    nav_layout.add_widget(nav_volumes)
    nav_layout.add_widget(nav_home)
    nav_layout.add_widget(nav_root)
    content.add_widget(nav_layout)
    filechooser = FileChooserListView(path='/', dirselect=True)
    def on_path_change(instance, value):
        path_input.text = value
        # WICHTIG: Kivy leert die Auswahl nicht automatisch beim Wechseln in einen Ordner!
        # Wenn der User vorher einen übergeordneten Ordner angeklickt hatte und dann rein-
        # navigiert, würde sonst der übergeordnete Ordner ausgewählt bleiben.
        filechooser.selection = []
    filechooser.bind(path=on_path_change)
    def on_path_input(instance):
        entered = instance.text.strip()
        import os
        if os.path.isdir(entered):
            filechooser.path = entered
    path_input.bind(on_text_validate=on_path_input)
    def go_volumes(instance): filechooser.path = '/Volumes'
    def go_home(instance): filechooser.path = os.path.expanduser('~')
    def go_root(instance): filechooser.path = '/'
    nav_volumes.bind(on_release=go_volumes)
    nav_home.bind(on_release=go_home)
    nav_root.bind(on_release=go_root)
    content.add_widget(filechooser)
    button_layout = BoxLayout(size_hint_y=None, height='48dp', spacing=10)
    cancel_btn = CustomButton(text='Abbrechen')
    cancel_btn.background_color = (0.953, 0.545, 0.659, 1)
    select_btn = CustomButton(text='Auswählen')
    button_layout.add_widget(cancel_btn)
    button_layout.add_widget(select_btn)
    content.add_widget(button_layout)
    popup = Popup(title=title, content=content, size_hint=(0.9, 0.9))
    cancel_btn.bind(on_release=popup.dismiss)
    def on_select(instance):
        selected = filechooser.selection[0] if filechooser.selection else filechooser.path
        callback(selected)
        popup.dismiss()
    select_btn.bind(on_release=on_select)
    
    # Drag & Drop für den Chooser aktivieren
    from kivy.core.window import Window
    def on_drop_in_chooser(window, filename, x, y):
        try:
            file_path = filename.decode('utf-8')
            import os
            if os.path.isdir(file_path):
                filechooser.path = file_path
                path_input.text = file_path
        except Exception:
            pass

    def bind_dnd(instance):
        Window.bind(on_drop_file=on_drop_in_chooser)
        
    def unbind_dnd(instance):
        Window.unbind(on_drop_file=on_drop_in_chooser)
        
    popup.bind(on_open=bind_dnd)
    popup.bind(on_dismiss=unbind_dnd)
    
    popup.open()

class SelectScreen(Screen):
    """
    Erster Screen der App – hier wählt der Benutzer Quell- und Zielverzeichnis.

    Das Quellverzeichnis ist der zu prüfende Ordner (z.B. auf einer USB-Platte).
    Das Zielverzeichnis ist das Backup-Root (z.B. NAS), in dem gesucht wird.

    Der Benutzer kann die Pfade manuell eingeben oder über einen Dateibrowser
    auswählen. Nach dem Start wird zu Screen 2 (ScanScreen) gewechselt.
    """

    # Referenzen auf UI-Elemente (werden in backuprunner.kv gesetzt)
    source_input = ObjectProperty(None)
    target_input = ObjectProperty(None)
    start_button = ObjectProperty(None)
    status_label = ObjectProperty(None)

    def on_kv_post(self, base_widget):
        """Wird aufgerufen, nachdem die KV-Datei geladen wurde."""
        # Konfiguration beim Start laden und UI vorbefüllen
        config = config_manager.load_config()
        if config:
            self.source_input.text = config.get('source', '')
            self.target_input.text = config.get('target', '')
            self.ids.fast_mode_checkbox.active = config.get('fast_mode', False)
            self.ids.update_cache_checkbox.active = config.get('update_cache', False)

    def on_enter(self, *args):
        """Wenn der Screen sichtbar wird, Drag&Drop binden."""
        Window.bind(on_drop_file=self._on_drop_file)

    def on_leave(self, *args):
        """Wenn der Screen verlassen wird, Drag&Drop wieder entfernen."""
        Window.unbind(on_drop_file=self._on_drop_file)

    def _on_drop_file(self, window, filename, x, y):
        """Behandelt Drag & Drop von Verzeichnissen in die App."""
        try:
            # Dateipfad decodieren (Kivy gibt bytes zurück)
            file_path = filename.decode('utf-8')
            
            # Prüfen, ob es ein Verzeichnis ist
            if not os.path.isdir(file_path):
                self.status_label.text = '⚠️ Bitte einen Ordner hineinziehen, keine einzelne Datei!'
                return
                
            # Wir machen es dem Nutzer einfach: Wenn er die obere Hälfte des Bildschirms trifft,
            # wird es Quelle, in der unteren Hälfte Ziel.
            # Alternativ können wir direkt prüfen, welches Textfeld getroffen wurde:
            if self.source_input.collide_point(*self.source_input.to_widget(x, y)):
                self.source_input.text = file_path
                self.status_label.text = '✅ Quellverzeichnis gesetzt'
            elif self.target_input.collide_point(*self.target_input.to_widget(x, y)):
                self.target_input.text = file_path
                self.status_label.text = '✅ Zielverzeichnis gesetzt'
            else:
                # Falls irgendwo anders hin gezogen wurde, nehmen wir das Feld, das leer ist
                if not self.source_input.text.strip():
                    self.source_input.text = file_path
                    self.status_label.text = '✅ Quellverzeichnis gesetzt (Auto-Zuweisung)'
                elif not self.target_input.text.strip():
                    self.target_input.text = file_path
                    self.status_label.text = '✅ Zielverzeichnis gesetzt (Auto-Zuweisung)'
                else:
                    self.status_label.text = 'ℹ️ Bitte ziehe den Ordner direkt auf das Quell- oder Zielfeld!'
        except Exception as e:
            self.status_label.text = f'⚠️ Fehler beim Drag & Drop: {e}'

    def choose_source(self):
        """Öffnet einen Dateibrowser zur Auswahl des Quellverzeichnisses."""
        open_directory_chooser(
            title='Quellverzeichnis wählen',
            callback=self._set_source
        )

    def choose_target(self):
        """Öffnet einen Dateibrowser zur Auswahl des Zielverzeichnisses."""
        open_directory_chooser(
            title='Zielverzeichnis wählen',
            callback=self._set_target
        )

    def _set_source(self, path):
        """Callback: Setzt den gewählten Pfad als Quellverzeichnis."""
        self.source_input.text = path

    def _set_target(self, path):
        """Callback: Setzt den gewählten Pfad als Zielverzeichnis."""
        self.target_input.text = path

    def start_scan(self):
        """
        Startet den Scan-Vorgang nach Validierung der Eingaben.

        Prüft, ob beide Verzeichnisse angegeben sind und existieren.
        Wenn alles in Ordnung ist, wird zu Screen 2 gewechselt und
        der Scan-Thread gestartet.
        """
        source = self.source_input.text.strip()
        target = self.target_input.text.strip()

        # ── Eingabe-Validierung ──
        if not source or not target:
            self.status_label.text = '⚠️ Bitte Quelle und Ziel angeben!'
            return

        if not os.path.exists(source):
            self.status_label.text = f'⚠️ Quelle existiert nicht: {source}'
            return

        if not os.path.isdir(target):
            self.status_label.text = f'⚠️ Zielverzeichnis existiert nicht: {target}'
            return

        if os.path.normpath(source) == os.path.normpath(target):
            self.status_label.text = '⚠️ Quell- und Zielverzeichnis sind identisch!'
            return

        self.status_label.text = ''

        # Pfade an die App übergeben und Scan starten
        app = App.get_running_app()
        app.source_path = source
        app.target_path = target
        app.fast_mode = self.ids.fast_mode_checkbox.active
        app.update_cache = self.ids.update_cache_checkbox.active

        # Einstellungen dauerhaft speichern
        config_manager.save_config(source, target, app.fast_mode, app.update_cache)

        # Zum Scan-Screen wechseln
        self.manager.transition = SlideTransition(direction='left')
        self.manager.current = 'scan'

        # Scan starten (im ScanScreen)
        scan_screen = self.manager.get_screen('scan')
        scan_screen.start_scan(source, target, app.fast_mode, app.update_cache)


# Hilfklasse für Buttons (wird auch in Python-Code verwendet)
class CustomButton(Button):
    """
    Vordefinierter Button-Style passend zum Dark Theme.
    Wird sowohl in der .kv-Datei als auch im Python-Code verwendet.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0.537, 0.706, 0.980, 1)  # Blau
        self.color = (0.118, 0.118, 0.180, 1)  # Dunkler Text
        self.font_size = '16sp'
        self.size_hint_y = None
        self.height = '48dp'
        self.bold = True


# ============================================================================
# Screen 2: Scan-Fortschritt
# ============================================================================

class ScanScreen(Screen):
    """
    Zweiter Screen – zeigt den Fortschritt während des Scannens.

    Der Scan läuft in einem Hintergrund-Thread, damit die UI nicht einfriert.
    Der Fortschritt wird über Kivy's Clock.schedule_once() an den Main-Thread
    zurückgegeben, da Kivy-UI-Elemente nur aus dem Main-Thread heraus
    aktualisiert werden dürfen.

    Phasen:
        1. "Scanne Quellverzeichnis..." – Quelldateien werden gescannt + gehasht
        2. "Scanne Zielverzeichnis..." – Zieldateien werden gescannt + gehasht
        3. "Vergleiche..."            – Hash-Index + Vergleich
    """

    # Referenzen auf UI-Elemente
    phase_label = ObjectProperty(None)
    progress_bar = ObjectProperty(None)
    progress_label = ObjectProperty(None)
    current_file_label = ObjectProperty(None)
    cancel_button = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._scan_thread = None
        self._cancelled = False

    def start_scan(self, source_path, target_path, fast_mode=False, update_cache=False):
        """
        Startet den Scan-Vorgang in einem Hintergrund-Thread.

        Args:
            source_path: Pfad zum Quellverzeichnis
            target_path: Pfad zum Zielverzeichnis
            fast_mode: Wenn True, wird nur Größe & Datum statt Hash verglichen
            update_cache: Wenn True, wird das NAS komplett neu gescannt
        """
        self._cancelled = False
        self._scan_thread = threading.Thread(
            target=self._run_scan,
            args=(source_path, target_path, fast_mode, update_cache),
            daemon=True  # Thread wird beendet, wenn die App beendet wird
        )
        self._scan_thread.start()

    def cancel_scan(self):
        """
        Bricht den laufenden Scan ab und kehrt zum Auswahl-Screen zurück.
        """
        self._cancelled = True
        # Kurz warten, dann zurück zum Auswahl-Screen
        Clock.schedule_once(lambda dt: self._go_back(), 0.5)

    def _go_back(self):
        """Wechselt zurück zum Auswahl-Screen."""
        self.manager.transition = SlideTransition(direction='right')
        self.manager.current = 'select'

    def _update_ui(self, phase, current, total, filepath=""):
        """
        Aktualisiert die UI-Elemente (wird über Clock.schedule_once aufgerufen).

        Diese Methode wird indirekt aus dem Hintergrund-Thread aufgerufen.
        Clock.schedule_once stellt sicher, dass die Aktualisierung im
        Main-Thread stattfindet (Kivy-Anforderung).

        Args:
            phase:      Beschreibung der aktuellen Phase
            current:    Aktuelle Dateinummer
            total:      Gesamtanzahl Dateien
            filepath:   Pfad der aktuell verarbeiteten Datei
        """
        def update(dt):
            self.phase_label.text = phase
            if total > 0:
                self.progress_label.text = f'{current:,} / {total:,} Dateien'
                self.progress_bar.value = (current / total) * 100
            else:
                self.progress_label.text = f'{current:,} Dateien gescannt...'
                self.progress_bar.value = 0
            # Nur den Dateinamen anzeigen, nicht den ganzen Pfad
            if filepath:
                self.current_file_label.text = filepath
        Clock.schedule_once(update)

    def _run_scan(self, source_path, target_path, fast_mode, update_cache):
        """
        Haupt-Scan-Logik – läuft im Hintergrund-Thread.

        Ablauf:
        1. Quellverzeichnis scannen (alle Dateien + Hashes)
        2. Zielverzeichnis scannen (oder aus Cache laden)
        3. Hash-Index aufbauen
        4. Vergleich durchführen
        5. Ergebnis an den ResultScreen übergeben

        Args:
            source_path: Pfad zum Quellverzeichnis
            target_path: Pfad zum Zielverzeichnis
            fast_mode: Boolean, ob schneller Vergleich aktiv ist
            update_cache: Boolean, ob der NAS-Cache ignoriert/erneuert werden soll
        """
        try:
            # ── Phase 1: Quellverzeichnis scannen ──
            self._update_ui('📂 Zähle Dateien im Quellverzeichnis...', 0, 0, 'Bitte warten...')

            def source_progress(current, total, filepath):
                if self._cancelled:
                    return
                self._update_ui(
                    '📂 Scanne Quellverzeichnis...',
                    current, total, filepath
                )

            source_files, source_size = scan_directory(
                source_path, source_progress, fast_mode=fast_mode
            )

            if self._cancelled:
                return

            # ── Phase 2: Zielverzeichnis scannen (oder aus Cache laden) ──
            if not update_cache and cache_manager.has_target_cache():
                self._update_ui('💾 Lade NAS-Index aus dem Cache...', 0, 0, 'Verarbeite Datenbank (0 Sekunden Wartezeit)...')
                target_files, target_size = cache_manager.load_target_cache(target_path)
            else:
                self._update_ui('💾 Scanne Zielverzeichnis (NAS)...', 0, 0, 'Dies kann sehr lange dauern!')

                def target_progress(current, total, filepath):
                    if self._cancelled:
                        return
                    self._update_ui(
                        '💾 Scanne Zielverzeichnis...',
                        current, total, filepath
                    )

                target_files, target_size = scan_directory(
                    target_path, target_progress, fast_mode=fast_mode
                )
                
                if self._cancelled:
                    return
                
                # Cache sofort speichern, damit er beim nächsten Mal bereitsteht
                self._update_ui('💾 Speichere NAS-Index in Cache...', 0, 0, 'Bitte warten...')
                cache_manager.save_target_cache(target_path, target_files)

            if self._cancelled:
                return

            # ── Phase 3: Vergleich durchführen ──
            self._update_ui('🔄 Vergleiche Dateien...', 0, 0)

            # Hash-Index aus den Zieldateien aufbauen
            target_index = build_hash_index(target_files)

            # Vergleich durchführen
            result = compare_directories(
                source_files, target_files, target_index,
                source_path, target_path
            )

            # ── Ergebnis an den ResultScreen übergeben ──
            def show_results(dt):
                app = App.get_running_app()
                app.comparison_result = result
                result_screen = self.manager.get_screen('result')
                result_screen.display_results(result)
                self.manager.transition = SlideTransition(direction='left')
                self.manager.current = 'result'

            Clock.schedule_once(show_results)

        except Exception as e:
            # Fehler in der UI anzeigen
            def show_error(dt):
                self.phase_label.text = f'❌ Fehler: {str(e)}'
                self.progress_label.text = 'Scan abgebrochen'
                self.current_file_label.text = ''
            Clock.schedule_once(show_error)


# ============================================================================
# Screen 3: Analyse-Ergebnisse
# ============================================================================


# ============================================================================
# UI-Komponenten
# ============================================================================

class FileRow(BoxLayout):
    filename = StringProperty()
    detail = StringProperty()
    size_text = StringProperty()

class ResultScreen(Screen):
    """
    Dritter Screen – zeigt die Ergebnisse der Analyse.

    Die Ergebnisse werden in vier Tabs dargestellt:
    - ⚠️ Kein Backup:   Dateien, die nicht im Ziel gefunden wurden
    - ✅ Identisch:      Dateien mit gleichem Hash UND gleichem Pfad
    - 🔀 Anderer Pfad:   Dateien mit gleichem Hash, aber an anderer Stelle
    - 📋 Duplikate:      Dateien, die mehrfach im Ziel existieren

    Außerdem kann ein CSV-Report exportiert werden.
    """

    # Referenzen auf UI-Elemente
    summary_label = ObjectProperty(None)
    tab_panel = ObjectProperty(None)
    identical_list = ObjectProperty(None)
    moved_list = ObjectProperty(None)
    no_backup_list = ObjectProperty(None)
    duplicates_list = ObjectProperty(None)

    def display_results(self, result: ComparisonResult):
        """
        Füllt die UI mit den Vergleichsergebnissen.

        Erstellt für jede Kategorie die entsprechenden Listeneinträge
        und zeigt die Zusammenfassung im Header an.

        Args:
            result: ComparisonResult aus compare_directories()
        """
        # ── Zusammenfassung ──
        self.summary_label.text = (
            f'✅ {len(result.identical)} identisch  |  '
            f'🔀 {len(result.moved)} anderer Pfad  |  '
            f'⚠️ {len(result.no_backup)} kein Backup  |  '
            f'📋 {len(result.duplicates)} Duplikat-Gruppen'
        )

        # ── Listen leeren (falls vorherige Ergebnisse vorhanden) ──
        self.identical_list.clear_widgets()
        self.moved_list.clear_widgets()
        self.no_backup_list.clear_widgets()
        self.duplicates_list.clear_widgets()

        # ── Tab "Kein Backup" füllen ──
        if result.no_backup:
            for item in result.no_backup:
                row = self._create_file_row(
                    filename=item.source_file.relative_path,
                    detail=f'Pfad: {item.source_file.absolute_path}',
                    size=item.source_file.size
                )
                btn = CustomButton(text='➕ Kopieren', width='100dp', size_hint_x=None, height='40dp')
                # Wir binden die Aktion mit default arguments, um scoping issues in Schleifen zu vermeiden
                btn.bind(on_release=lambda instance, i=item, r=row: self.copy_single_file(i, r))
                row.ids.action_container.add_widget(btn)

                # Löschen Button hinzufügen
                trash_btn = CustomButton(text='🗑️', width='50dp', size_hint_x=None, height='40dp')
                trash_btn.background_color = (0.953, 0.545, 0.659, 1) # Rot
                trash_btn.bind(on_release=lambda instance, p=item.source_file.absolute_path, r=row, b=trash_btn: self.trash_single_file(p, r, b))
                row.ids.action_container.add_widget(trash_btn)
                
                self.no_backup_list.add_widget(row)
        else:
            self.no_backup_list.add_widget(
                self._create_empty_label('🎉 Alle Dateien sind gesichert!')
            )

        # ── Tab "Identisch" füllen ──
        if result.identical:
            for item in result.identical:
                target_info = item.target_paths[0] if item.target_paths else ''
                row = self._create_file_row(
                    filename=item.source_file.relative_path,
                    detail=f'Ziel: {target_info}',
                    size=item.source_file.size
                )
                
                btn = CustomButton(text='🗑️ Löschen', width='100dp', size_hint_x=None, height='40dp')
                btn.background_color = (0.953, 0.545, 0.659, 1) # Rot
                btn.bind(on_release=lambda instance, p=item.source_file.absolute_path, r=row, b=btn: self.trash_single_file(p, r, b))
                row.ids.action_container.add_widget(btn)
                
                self.identical_list.add_widget(row)
        else:
            self.identical_list.add_widget(
                self._create_empty_label('Keine identischen Dateien gefunden')
            )

        # ── Tab "Anderer Pfad" füllen ──
        if result.moved:
            for item in result.moved:
                targets = '\n'.join(item.target_paths)
                row = self._create_file_row(
                    filename=item.source_file.relative_path,
                    detail=f'Gefunden unter: {" | ".join(item.target_paths)}',
                    size=item.source_file.size
                )
                self.moved_list.add_widget(row)
        else:
            self.moved_list.add_widget(
                self._create_empty_label('Keine verschobenen Dateien gefunden')
            )

        # ── Tab "Duplikate" füllen ──
        if result.duplicates:
            for dup in result.duplicates:
                row = self._create_file_row(
                    filename=f'{len(dup.paths)} Kopien',
                    detail=f'Pfade: {" | ".join(dup.paths)}',
                    size=dup.size
                )
                # Für jedes Duplikat (außer das erste) einen Löschen Button
                for path in dup.paths[1:]:
                    btn = CustomButton(text='🗑️ Löschen', width='100dp', size_hint_x=None, height='40dp')
                    btn.background_color = (0.953, 0.545, 0.659, 1) # Rot
                    btn.bind(on_release=lambda instance, p=path, r=row, b=btn: self.trash_single_file(p, r, b))
                    row.ids.action_container.add_widget(btn)
                self.duplicates_list.add_widget(row)
        else:
            self.duplicates_list.add_widget(
                self._create_empty_label('Keine Duplikate im Ziel gefunden')
            )

    def _create_file_row(self, filename: str, detail: str, size: int):
        from kivy.factory import Factory
        row = Factory.FileRow()
        row.filename = filename
        row.detail = detail
        row.size_text = format_size(size)
        return row

    def _create_empty_label(self, text: str) -> Label:
        """
        Erstellt ein Label für leere Listen.

        Args:
            text: Anzuzeigender Text

        Returns:
            Label-Widget
        """
        return Label(
            text=text,
            font_size='16sp',
            color=(0.584, 0.616, 0.737, 1),
            size_hint_y=None,
            height='60dp'
        )


    def copy_single_file(self, item, row):
        def on_target_selected(target_dir):
            try:
                target_path = copy_file(
                    item.source_file.absolute_path, 
                    target_dir, 
                    item.source_file.relative_path, 
                    expected_hash=item.source_file.hash
                )
                
                # Cache aktualisieren
                app = App.get_running_app()
                new_size = os.path.getsize(target_path)
                new_mtime = os.path.getmtime(target_path)
                if getattr(app, 'fast_mode', False):
                    new_hash = f"FAST_{new_size}_{int(new_mtime)}"
                else:
                    from scanner import compute_hash
                    new_hash = compute_hash(target_path)
                    
                from scanner import FileInfo
                new_info = FileInfo(
                    absolute_path=target_path,
                    relative_path=item.source_file.relative_path,
                    size=new_size,
                    modified_time=new_mtime,
                    hash=new_hash
                )
                cache_manager.add_to_target_cache(new_info)
                
                row.ids.action_container.clear_widgets()
                lbl = Label(text='✅ Kopiert', color=(0.651, 0.890, 0.631, 1), size_hint_x=None, width='80dp')
                trash_btn = CustomButton(text='🗑️ Quelle in Papierkorb', size_hint_x=None, width='180dp', height='40dp')
                trash_btn.background_color = (0.953, 0.545, 0.659, 1) # Rot
                trash_btn.bind(on_release=lambda instance, p=item.source_file.absolute_path, r=row, b=trash_btn: self.trash_single_file(p, r, b))
                row.ids.action_container.add_widget(lbl)
                row.ids.action_container.add_widget(trash_btn)
            except Exception as e:
                Popup(title='❌ Fehler beim Kopieren', content=Label(text=str(e), text_size=(400, None)), size_hint=(0.7, 0.3)).open()
                
        open_directory_chooser("Wohin soll die Datei kopiert werden?", on_target_selected)

    def trash_single_file(self, path, row, btn):
        if move_to_trash(path):
            row.ids.action_container.clear_widgets()
            lbl = Label(text='✅ Im Papierkorb', color=(0.651, 0.890, 0.631, 1), size_hint_x=None, width='120dp')
            row.ids.action_container.add_widget(lbl)
        else:
            Popup(title='❌ Fehler', content=Label(text=f'Konnte {path} nicht löschen.'), size_hint=(0.7, 0.3)).open()

    def trash_all_identical(self):
        app = App.get_running_app()
        result = app.comparison_result
        if not result or not result.identical:
            return
            
        def on_confirm(instance):
            popup.dismiss()
            success_count = 0
            freed_space = 0
            
            for item in result.identical:
                if move_to_trash(item.source_file.absolute_path):
                    success_count += 1
                    freed_space += item.source_file.size
            
            self.identical_list.clear_widgets()
            self.identical_list.add_widget(
                self._create_empty_label(f'✅ {success_count} Dateien in Papierkorb verschoben')
            )
            
            Popup(
                title='Erfolgreich gelöscht',
                content=Label(
                    text=f'{success_count} Dateien wurden in den Papierkorb verschoben.\nFreigegebener Speicherplatz: {format_size(freed_space)}', 
                    text_size=(380, None),
                    halign='center'
                ),
                size_hint=(0.8, 0.4)
            ).open()

        content = BoxLayout(orientation='vertical', spacing='10dp', padding='10dp')
        content.add_widget(Label(
            text=f'Sollen {len(result.identical)} identische Dateien auf der Quelle (Mac) in den Papierkorb verschoben werden?',
            text_size=(380, None),
            halign='center'
        ))
        
        btn_layout = BoxLayout(size_hint_y=None, height='40dp', spacing='10dp')
        cancel_btn = CustomButton(text='Abbrechen', background_color=(0.584, 0.616, 0.737, 1))
        confirm_btn = CustomButton(text='In Papierkorb', background_color=(0.953, 0.545, 0.659, 1))
        
        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(confirm_btn)
        content.add_widget(btn_layout)
        
        popup = Popup(title='Löschen bestätigen', content=content, size_hint=(0.9, 0.4), auto_dismiss=False)
        cancel_btn.bind(on_release=popup.dismiss)
        confirm_btn.bind(on_release=on_confirm)
        popup.open()

    def trash_all_missing(self):
        app = App.get_running_app()
        result = app.comparison_result
        if not result or not result.no_backup:
            return
            
        def on_confirm(instance):
            popup.dismiss()
            success_count = 0
            freed_space = 0
            
            for item in result.no_backup:
                if move_to_trash(item.source_file.absolute_path):
                    success_count += 1
                    freed_space += item.source_file.size
            
            self.no_backup_list.clear_widgets()
            self.no_backup_list.add_widget(
                self._create_empty_label(f'✅ {success_count} Dateien in Papierkorb verschoben')
            )
            
            Popup(
                title='Erfolgreich gelöscht',
                content=Label(
                    text=f'{success_count} ungesicherte Dateien wurden in den Papierkorb verschoben.\nFreigegebener Speicherplatz: {format_size(freed_space)}', 
                    text_size=(380, None),
                    halign='center'
                ),
                size_hint=(0.8, 0.4)
            ).open()

        content = BoxLayout(orientation='vertical', spacing='10dp', padding='10dp')
        content.add_widget(Label(
            text=f'Sollen {len(result.no_backup)} Dateien OHNE Backup auf der Quelle (Mac) in den Papierkorb verschoben werden?',
            text_size=(380, None),
            halign='center'
        ))
        
        btn_layout = BoxLayout(size_hint_y=None, height='40dp', spacing='10dp')
        cancel_btn = CustomButton(text='Abbrechen', background_color=(0.584, 0.616, 0.737, 1))
        confirm_btn = CustomButton(text='In Papierkorb', background_color=(0.953, 0.545, 0.659, 1))
        
        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(confirm_btn)
        content.add_widget(btn_layout)
        
        popup = Popup(title='Löschen bestätigen', content=content, size_hint=(0.9, 0.4), auto_dismiss=False)
        cancel_btn.bind(on_release=popup.dismiss)
        confirm_btn.bind(on_release=on_confirm)
        popup.open()

    def copy_all_missing(self):
        app = App.get_running_app()
        result = app.comparison_result
        if not result or not result.no_backup:
            return
            
        def on_target_selected(target_dir):
            success_items = []
            is_fast_mode = getattr(app, 'fast_mode', False)
            total_items = len(result.no_backup)
            
            from kivy.uix.progressbar import ProgressBar
            import threading
            
            content = BoxLayout(orientation='vertical', spacing='10dp', padding='10dp')
            progress_label = Label(text='Starte Kopiervorgang...', text_size=(380, None), halign='center')
            progress_bar = ProgressBar(max=total_items, value=0)
            cancel_btn = CustomButton(text='Abbrechen', background_color=(0.953, 0.545, 0.659, 1))
            
            content.add_widget(progress_label)
            content.add_widget(progress_bar)
            content.add_widget(cancel_btn)
            
            popup = Popup(title='Kopiere Dateien...', content=content, size_hint=(0.8, 0.4), auto_dismiss=False)
            
            stop_event = threading.Event()
            
            def cancel_copy(instance):
                stop_event.set()
                progress_label.text = 'Abbruch wird vorbereitet...'
                cancel_btn.disabled = True

            cancel_btn.bind(on_release=cancel_copy)
            
            def update_ui(current, total, file_name):
                progress_bar.value = current
                progress_label.text = f'Kopiere Datei {current} von {total}...\n{file_name}'
            
            def finish_copy(dt):
                popup.dismiss()
                ask_content = BoxLayout(orientation='vertical', spacing=10, padding=10)
                ask_content.add_widget(Label(
                    text=f'✅ {len(success_items)} Dateien kopiert.\n\nSollen die Original-Dateien auf\ndeinem Mac in den Papierkorb verschoben werden?',
                    halign='center'
                ))
                btn_layout = BoxLayout(size_hint_y=None, height='40dp', spacing=10)
                btn_keep = CustomButton(text='Behalten')
                btn_trash = CustomButton(text='🗑️ In Papierkorb', background_color=(0.953, 0.545, 0.659, 1))
                btn_layout.add_widget(btn_keep)
                btn_layout.add_widget(btn_trash)
                ask_content.add_widget(btn_layout)
                
                ask_popup = Popup(title='Kopieren beendet', content=ask_content, size_hint=(0.8, 0.4))
                
                def do_trash(inst):
                    for item in success_items:
                        move_to_trash(item.source_file.absolute_path)
                    ask_popup.dismiss()
                    
                btn_keep.bind(on_release=ask_popup.dismiss)
                btn_trash.bind(on_release=do_trash)
                ask_popup.open()
                
            def copy_thread_func():
                from scanner import compute_hash, FileInfo
                
                for i, item in enumerate(result.no_backup):
                    if stop_event.is_set():
                        break
                        
                    # Aktualisiere die UI über Clock (auf Main-Thread)
                    Clock.schedule_once(lambda dt, cur=i+1, tot=total_items, fn=item.source_file.relative_path: update_ui(cur, tot, fn), 0)
                    
                    try:
                        target_path = copy_file(
                            item.source_file.absolute_path, 
                            target_dir, 
                            item.source_file.relative_path, 
                            expected_hash=item.source_file.hash
                        )
                        success_items.append(item)
                        
                        # Cache updaten
                        new_size = os.path.getsize(target_path)
                        new_mtime = os.path.getmtime(target_path)
                        if is_fast_mode:
                            new_hash = f"FAST_{new_size}_{int(new_mtime)}"
                        else:
                            new_hash = compute_hash(target_path)
                            
                        cache_manager.add_to_target_cache(FileInfo(
                            absolute_path=target_path,
                            relative_path=item.source_file.relative_path,
                            size=new_size,
                            modified_time=new_mtime,
                            hash=new_hash
                        ))
                    except Exception as e:
                        print(f"Fehler bei {item.source_file.absolute_path}: {e}")
                
                Clock.schedule_once(finish_copy, 0)
            
            popup.open()
            threading.Thread(target=copy_thread_func, daemon=True).start()
            
        open_directory_chooser("Zielordner für alle fehlenden Dateien wählen", on_target_selected)

    def trash_entire_source(self):
        app = App.get_running_app()
        if not getattr(app, 'source_dir', None):
            return
            
        def on_confirm(instance):
            popup.dismiss()
            if move_to_trash(app.source_dir):
                self.new_comparison()
                Popup(
                    title='Erfolgreich gelöscht',
                    content=Label(
                        text='Der gesamte Quellordner wurde in den Papierkorb verschoben.', 
                        text_size=(380, None),
                        halign='center'
                    ),
                    size_hint=(0.8, 0.4)
                ).open()
            else:
                Popup(
                    title='❌ Fehler', 
                    content=Label(
                        text='Konnte den Ordner nicht in den Papierkorb verschieben.\n(Evtl. wird der Papierkorb auf dem Laufwerk nicht unterstützt.)', 
                        text_size=(380, None),
                        halign='center'
                    ), 
                    size_hint=(0.8, 0.4)
                ).open()

        content = BoxLayout(orientation='vertical', spacing='10dp', padding='10dp')
        content.add_widget(Label(
            text=f'[b]Möchtest du den gesamten Quellordner löschen?[/b]\n\n{app.source_dir}\n\nEr wird in den Papierkorb verschoben. Danach kehrt die App zum Startbildschirm zurück.',
            markup=True,
            text_size=(380, None),
            halign='center'
        ))
        
        btn_layout = BoxLayout(size_hint_y=None, height='40dp', spacing='10dp')
        cancel_btn = CustomButton(text='Abbrechen', background_color=(0.584, 0.616, 0.737, 1))
        confirm_btn = CustomButton(text='In Papierkorb', background_color=(0.953, 0.545, 0.659, 1))
        
        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(confirm_btn)
        content.add_widget(btn_layout)
        
        popup = Popup(title='⚠️ ACHTUNG: Gesamten Ordner löschen', content=content, size_hint=(0.9, 0.5), auto_dismiss=False)
        cancel_btn.bind(on_release=popup.dismiss)
        confirm_btn.bind(on_release=on_confirm)
        popup.open()

    def export_report(self):
        """
        Exportiert die Ergebnisse als CSV-Datei.

        Die Datei wird auf dem Desktop gespeichert mit einem Zeitstempel
        im Dateinamen, damit mehrere Reports nicht überschrieben werden.
        """
        app = App.get_running_app()
        result = app.comparison_result

        if not result:
            return

        # CSV-Datei auf dem Desktop speichern
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        desktop = os.path.expanduser('~/Desktop')
        output_path = os.path.join(desktop, f'backup_report_{timestamp}.csv')

        try:
            saved_path = export_csv(result, output_path)

            # Erfolgs-Popup anzeigen
            popup = Popup(
                title='✅ Report exportiert',
                content=Label(
                    text=f'CSV gespeichert unter:\n{saved_path}',
                    text_size=(400, None),
                    halign='center'
                ),
                size_hint=(0.7, 0.3)
            )
            popup.open()
        except Exception as e:
            # Fehler-Popup anzeigen
            popup = Popup(
                title='❌ Fehler beim Export',
                content=Label(
                    text=f'Fehler: {str(e)}',
                    text_size=(400, None),
                    halign='center'
                ),
                size_hint=(0.7, 0.3)
            )
            popup.open()

    def new_comparison(self):
        """Wechselt zurück zum Auswahl-Screen für einen neuen Vergleich."""
        self.manager.transition = SlideTransition(direction='right')
        self.manager.current = 'select'


# ============================================================================
# App-Klasse
# ============================================================================

class BackUpRunnerApp(App):
    """
    Hauptklasse der BackUpRunner-App.

    Verwaltet den ScreenManager und speichert globale Daten wie
    die gewählten Pfade und das Vergleichsergebnis.

    Attributes:
        source_path:        Pfad zum Quellverzeichnis
        target_path:        Pfad zum Zielverzeichnis
        comparison_result:  Ergebnis des letzten Vergleichs
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.source_path = ""
        self.target_path = ""
        self.comparison_result = None

    def build(self):
        """
        Erstellt die App-Oberfläche.

        Initialisiert den ScreenManager mit den drei Screens
        und setzt den Fenstertitel.

        Returns:
            ScreenManager mit allen Screens
        """
        self.title = 'BackUpRunner – Backup-Analyse'

        # ScreenManager erstellt und Screens hinzufügen
        sm = ScreenManager()
        sm.add_widget(SelectScreen(name='select'))
        sm.add_widget(ScanScreen(name='scan'))
        sm.add_widget(ResultScreen(name='result'))

        # Konfiguration laden und SelectScreen vorausfüllen
        config = config_manager.load_config()
        select_screen = sm.get_screen('select')
        select_screen.ids.source_input.text = config.get("source_path", "")
        select_screen.ids.target_input.text = config.get("target_path", "")
        select_screen.ids.fast_mode_checkbox.active = config.get("fast_mode", True)
        select_screen.ids.update_cache_checkbox.active = config.get("update_cache", False)

        return sm


# ============================================================================
# App starten
# ============================================================================

if __name__ == '__main__':
    BackUpRunnerApp().run()
