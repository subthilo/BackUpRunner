import os
from kivy.app import App
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.clock import Clock

class TestApp(App):
    def build(self):
        self.fc = FileChooserListView(path='/', dirselect=True)
        self.fc.bind(path=self.on_path, selection=self.on_sel)
        
        layout = BoxLayout(orientation='vertical')
        layout.add_widget(self.fc)
        btn = Button(text='Print', size_hint_y=0.2)
        btn.bind(on_release=lambda x: print(f"PATH: {self.fc.path}\nSEL: {self.fc.selection}"))
        layout.add_widget(btn)
        
        # Simulate clicks
        def sim(*args):
            # simulate selection
            self.fc.selection = ['/System']
            print(f"After manual sel: PATH: {self.fc.path}, SEL: {self.fc.selection}")
            # simulate navigation
            self.fc.path = '/Users'
            print(f"After nav to /Users: PATH: {self.fc.path}, SEL: {self.fc.selection}")
            App.get_running_app().stop()
            
        Clock.schedule_once(sim, 1)
        return layout

    def on_path(self, inst, val):
        pass
    def on_sel(self, inst, val):
        pass

TestApp().run()
