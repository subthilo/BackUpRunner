import re

with open('main.py', 'r') as f:
    content = f.read()

# 1. Add imports
content = content.replace(
    'from report import export_csv, format_size\n',
    'from report import export_csv, format_size\nfrom operations import copy_file, move_to_trash\n'
)

# 2. Add FileRow class
file_row_class = """
# ============================================================================
# UI-Komponenten
# ============================================================================

class FileRow(BoxLayout):
    filename = StringProperty()
    detail = StringProperty()
    size_text = StringProperty()
"""
content = content.replace(
    'class ResultScreen(Screen):',
    file_row_class + '\nclass ResultScreen(Screen):'
)

# 3. Extract open_directory_chooser
chooser_code = """
def open_directory_chooser(title, callback):
    \"\"\"Öffnet einen Dateibrowser zur Verzeichnisauswahl.\"\"\"
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
    filechooser = FileChooserListView(path='/', dirselect=True, filters=['!.*'])
    def on_path_change(instance, value):
        path_input.text = value
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
    popup.open()
"""
content = content.replace(
    'class SelectScreen(Screen):',
    chooser_code + '\nclass SelectScreen(Screen):'
)

# 4. Replace SelectScreen's usage
content = re.sub(
    r'def choose_source\(self\):\n\s+self\._open_directory_chooser\(.*?\)',
    'def choose_source(self):\n        open_directory_chooser("Quellverzeichnis wählen", self._set_source)',
    content, flags=re.DOTALL
)
content = re.sub(
    r'def choose_target\(self\):\n\s+self\._open_directory_chooser\(.*?\)',
    'def choose_target(self):\n        open_directory_chooser("Zielverzeichnis wählen", self._set_target)',
    content, flags=re.DOTALL
)

# Remove the old _open_directory_chooser
content = re.sub(
    r'def _open_directory_chooser\(self, title, callback\):.*?def start_scan',
    'def start_scan',
    content, flags=re.DOTALL
)

with open('main.py', 'w') as f:
    f.write(content)
