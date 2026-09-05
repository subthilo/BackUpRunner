from kivy.app import App
from kivy.uix.filechooser import FileChooserListView
class TestApp(App):
    def build(self):
        fc = FileChooserListView(path='/', dirselect=True)
        def on_sel(inst, sel):
            print("SELECTED:", sel)
        fc.bind(selection=on_sel)
        return fc
TestApp().run()
