
import ui
import random

class MyButtonClass(ui.View):
    def __init__(self, x, y, width, height, action, color):
        self.color = color
        self.x = x
        self.y = y
        self.height = height
        self.width = width

    def draw(self):
        path = ui.Path.rect(0, 0, self.width, self.height)
        ui.set_color(self.color)
        path.fill()

    def touch_began(self, touch):
        self.color = "green"
        self.set_needs_display()

    def touch_moved(self, touch):
        self.color = "white"
        self.set_needs_display()

    def touch_ended(self, touch):
        self.color = "blue"
        self.set_needs_display()
                
class EliteKeypad(ui.View):
    def __init__(self, frame=(0, 0, 300, 300), action=None,
                 autoclose=False):
        self.frame = frame
        self.action = action
        self.autoclose = autoclose
        self.border_color = 'black'
        self.border_width = 2
        self.corner_radius = 10
            
        # Define grid layout
        # (Title, Weight, color) - Weight 1 for a standard square-ish grid
        self.layout_data = [
            [('Launch', 1, 'cyan'), ('Trade', 1, 'cyan'), ('Equip', 1, 'cyan'),
             ('Status', 1, 'cyan'), ('Local Chart', 1, 'cyan'), ('Galaxy Chart', 1, 'cyan'),
             ('Data', 1, 'cyan')],
            [('Menu', 1, '#fb9bff'), ('Pause', 1, '#fb9bff'), ('Compass Planet', 1, '#fb9bff'),(' ', 2, '#fb9bff'),
             ('Find', 1, 'cyan'), (' ', 1, 'cyan')],
            [('Jump', 1, 'lightgreen'), ('Hyper Space', 1, 'lightgreen'), ('Escape', 1, 'lightgreen'),
             ('ECM', 1, 'lightgreen'), ('Bomb', 1, 'lightgreen'), ('Target', 1, 'lightgreen'),
             ('Missile', 1, 'lightgreen')],
            [('Docking', 1, 'lightgreen'), ('New Galaxy', 1, 'lightgreen'), ('To Sun', 1, '#fb9bff'),
             ('To Planet', 1, '#fb9bff'), ('To Station', 1, '#fb9bff'), ('Up', 1, 'yellow'),
             (' ', 1, 'lightgreen')],
            [('Look Fwd', 1, 'cyan'),('Look Aft', 1, 'cyan'),('Look Port', 1, 'cyan'), ('Look Stbd', 1, 'cyan'), 
              ('Left', 1, 'yellow'), ('Select', 1, '#ff8080'),
             ('Right', 1, 'yellow')],
            [ ('Fire Laser', 2, 'orange'),  ('OK', 1, '#ff8080'), ('Cancel', 1, '#ff8080'),
              (' ', 1, 'cyan'), ('Down', 1, 'yellow'), (' ', 1, 'cyan')]
        ]
        
        self.btns = {}
        for row in self.layout_data:
            for char, weight, color in row:
                # We only create buttons for non-empty slots or functional buttons
                # btn = MyButtonClass(0,0, 20,20, "red")
                btn = self.multiline_button(char)
                btn.name = char
                btn.background_color = color if char != ' ' else 'transparent'
                btn.tint_color = 'black'
                btn.border_width = 0.5 if char != ' ' else 0
                # btn.corner_radius = 10
                btn.weight = weight
                
                btn.action = self.action or self.button_tapped
                
                # Disable the "spacer" buttons
                if char == ' ':
                    btn.enabled = False
                
                self.add_subview(btn)
                self.btns[char] = btn
                
        self.background_color = '#d1d4d9'
        self.layout()
    
    def multiline_button(self, text):
        # 1. Create the base button
        btn = ui.Button()
        btn.background_color = '##ffffff' if text != ' ' else 'transparent'
        btn.corner_radius = 10
        
        # 2. Create a Label for the text
        label = ui.Label()
        label.text = text
        label.name = 'label'
        label.frame = btn.frame
        label.font = ('Avenir Next', 10)
        label.text_color = 'black'
        label.alignment = ui.ALIGN_CENTER
        label.number_of_lines = 0  # 0 allows unlimited lines
        
        # 3. Add label to button and make it fill the space
        label.flex = 'WH'
        btn.add_subview(label)
        
        return btn

    def key_change(self, key_name, name=None, color=None, enabled=None):
        # change appearance of key
        try:
           for button in self.subviews:
              if button.name == key_name:
                break
           else:
               raise AttributeError(f'Button {key_name} not found')
               return
           if name is not None:
               button.name = name
               button['label'].text = name
           if color is not None:
               button.background_color = color
           if enabled is not None:
               button.enabled = enabled
               button['label'].text_color = 'black' if enabled else 'lightgrey'
        except AttributeError as e:
            AttributeError(f'Button attribute not valid {e}')
            
    def toggle(self, gs, attribute_str, keynames=None, enable=None, colors=None):
        # toggle a parameter and optionally the keypad name, enable or color
        try:
            attribute = getattr(gs,  attribute_str)
            attribute = not attribute
            setattr(gs,  attribute_str, attribute)
        except AttributeError:
            attribute = random.randint(0, 1)
        
        key_color = key_enable = new_keyname = None
        
        if keynames is not None:
           # a pair of keynames relating to false or true attribute state
           if attribute:
               existing_keyname, new_keyname = keynames
           else:
               new_keyname, existing_keyname = keynames
        
        if enable is not None:
            key_enable = enable
                     
        if colors is not None:
           # a pair of colors relating to false or true attribute state
           if attribute:
               key_color = colors[attribute]
                             
        self.key_change(key_name=existing_keyname,
                                            name=new_keyname,
                                            color=key_color,
                                            enabled=key_enable)
                                                     
    def layout(self):
        pad = 5
        rows = len(self.layout_data)
        row_h = (self.height - (pad * (rows + 1))) / rows
        
        for r_idx, row in enumerate(self.layout_data):
            total_weight = sum(item[1] for item in row)
            unit_w = (self.width - (pad * (len(row) + 1))) / total_weight
            
            current_x = pad
            y = r_idx * (row_h + pad) + pad
            
            for char, weight, color in row:
                btn = self.btns[char]
                w = unit_w * weight
                btn.frame = (current_x, y, w, row_h)
                # btn['label'].frame = btn.frame
                btn['label'].font = ('Arial Rounded MT Bold', max(10, row_h * 0.125))
                
                current_x += w + pad

    def button_tapped(self, sender):
        letter = sender.name
        self.input_word += letter.lower()
                                                   
    def close_keypad(self):
        if self.superview:
            self.superview.remove_subview(self)

                        
def my_repeat_action(sender):
    print("Repeating!")

                                              
if __name__ == '__main__':
    # Setup a dummy text field to demonstrate the link
    def get_text(sender):
       print(sender.name)
       tf.text = sender.name
    main_view = ui.View(frame=(0, 0, 600, 600))
    tf = ui.TextField(frame=(10, 50, 380, 40))
    tf.placeholder = 'Cursor output appears here'
    main_view.add_subview(tf)
    
    # Initialize the Keypad
    keypad = EliteKeypad(
        frame=(100, 150, 500, 375),
        action=get_text)
    existing_btn = keypad['U']
    # 3. "Upgrade" it
    # ButtonRepeater(existing_btn, my_repeat_action)
    main_view.add_subview(keypad)
    keypad.key_change('Up', enabled=True)
    #keypad.key_change(key_name='Docking', name='Cancel Docking')                                        
    keypad.toggle(None, '', ['Docking', 'Cancel Docking'])
    main_view.present('sheet')
    # --- How to apply it to your existing code ---
    
 

        




