import re

with open('main.py', 'r') as f:
    content = f.read()

# 1. Simplify _create_file_row to just instantiate FileRow
new_create_file_row = """
    def _create_file_row(self, filename: str, detail: str, size: int):
        from kivy.factory import Factory
        row = Factory.FileRow()
        row.filename = filename
        row.detail = detail
        row.size_text = format_size(size)
        return row
"""
content = re.sub(
    r'    def _create_file_row\(self, filename: str, detail: str, size: int\) -> BoxLayout:.*?return row',
    new_create_file_row.strip('\n'),
    content, flags=re.DOTALL
)

# 2. Update display_results to add buttons
display_results_updates = """
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
                self.no_backup_list.add_widget(row)
        else:
            self.no_backup_list.add_widget(
                self._create_empty_label('🎉 Alle Dateien sind gesichert!')
            )

        # ── Tab "Identisch" füllen ──
"""
content = re.sub(
    r'        # ── Tab "Kein Backup" füllen ──.*?# ── Tab "Identisch" füllen ──',
    display_results_updates.strip('\n') + '\n\n        # ── Tab "Identisch" füllen ──',
    content, flags=re.DOTALL
)

duplicates_updates = """
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
"""
content = re.sub(
    r'        # ── Tab "Duplikate" füllen ──.*?def _create_file_row',
    duplicates_updates.strip('\n') + '\n\n    def _create_file_row',
    content, flags=re.DOTALL
)

# 3. Add action methods
action_methods = """
    def copy_single_file(self, item, row):
        def on_target_selected(target_dir):
            try:
                copy_file(item.source_file.absolute_path, target_dir, item.source_file.relative_path)
                row.ids.action_container.clear_widgets()
                lbl = Label(text='✅ Kopiert', color=(0.651, 0.890, 0.631, 1), size_hint_x=None, width='100dp')
                row.ids.action_container.add_widget(lbl)
            except Exception as e:
                Popup(title='❌ Fehler beim Kopieren', content=Label(text=str(e), text_size=(400, None)), size_hint=(0.7, 0.3)).open()
                
        open_directory_chooser("Wohin soll die Datei kopiert werden?", on_target_selected)

    def trash_single_file(self, path, row, btn):
        if move_to_trash(path):
            row.ids.action_container.remove_widget(btn)
            if len(row.ids.action_container.children) == 0:
                lbl = Label(text='✅ Aufgeräumt', color=(0.651, 0.890, 0.631, 1), size_hint_x=None, width='100dp')
                row.ids.action_container.add_widget(lbl)
        else:
            Popup(title='❌ Fehler', content=Label(text=f'Konnte {path} nicht löschen.'), size_hint=(0.7, 0.3)).open()

    def copy_all_missing(self):
        app = App.get_running_app()
        result = app.comparison_result
        if not result or not result.no_backup:
            return
            
        def on_target_selected(target_dir):
            success = 0
            for item in result.no_backup:
                try:
                    copy_file(item.source_file.absolute_path, target_dir, item.source_file.relative_path)
                    success += 1
                except Exception as e:
                    print(f"Fehler bei {item.source_file.absolute_path}: {e}")
            Popup(title='✅ Kopieren beendet', content=Label(text=f'{success} von {len(result.no_backup)} Dateien kopiert.'), size_hint=(0.7, 0.3)).open()
            
        open_directory_chooser("Zielordner für alle fehlenden Dateien wählen", on_target_selected)

"""

# Insert action methods before export_report
content = content.replace('    def export_report(self):', action_methods + '    def export_report(self):')

with open('main.py', 'w') as f:
    f.write(content)
