 # This is the entry point for Pythonista Elite
# it is based heavily on Elite The New Kind  by Christian Pinder
# This C project has been converted to Python by Gemini and Claude AI
# Elements of project Elite FlatLand are present by # Author: Darron Vanaria
# especially in constants and game_engine
# The gui code is mine

# Chris Thomas April 2026
import math
import queue
import traceback
import ui
from time import time
from imp import reload
import logging
from scene import Scene, run, ShapeNode, LabelNode
from scene import Node, SpriteNode, Texture
from image_helpers import set_colorkey, pil_to_ui
import constants as cs
# from constants import logger
from hud_elite import HudPanel
from alg_main import MainLoop
from wireframe_3d import Camera, Vector3, Renderer
from joystick import Joystick
from change_screensize import get_screen_size
from elite_keypad import EliteKeypad
# turn off logging for this module.
# it seems to be on by default
target_logger = logging.getLogger('PIL.PngImagePlugin')
target_logger.setLevel('ERROR')

logger = logging.getLogger(__name__)
EXPLOSION_SPEED = 0.4


class EliteScene(Scene):
           
    def _did_change_size(self):
       """ recalculate all sizes when screen changes 
       not perfect yet"""
       
       W, H = get_screen_size()
       print('triggered new layout', W, H)
       reload(cs)
       self.keypad.frame = cs.KEYBOARD_RECT
       
       self.msg.position=(cs.GAME_W, cs.GAME_H - cs.KEYBOARD_RECT.min_y + 50)                         
       fontsize = (cs.W - cs.FLIGHT_RECT.max_x) // 18
       self.msg_right.position=(cs.HUD_RIGHT.x + 10, cs.HUD_H + 20)                                   
       self.obj_status.position=(cs.GAME_W, cs.GAME_H)       
       self.obj_status.font=('Copperplate', fontsize)                                    
       self.msg_left.position=(cs.HUD_LEFT.x + 10, cs.HUD_H)
       self.renderer.viewport = cs.FLIGHT_RECT  # x, y, w, h       
       for obj in (self.background, self.hud, self.joystick,
                   self.joystick_thrust, self.fire_button):        
           obj.remove_from_parent()
       
       self.background = self.create_background()              
       self.hud = HudPanel()       
       self.create_controls()
              
       for obj in (self.background, self.hud, self.joystick,
                   self.joystick_thrust, self.fire_button):        
           self.add_child(obj)       
                                 
    def setup(self):
        W, H = get_screen_size()
        self.paused = True
        self.enable_sound = cs.SOUND
        self.input_queue = queue.Queue()
        self.active_touches = {}
        self.keypad = EliteKeypad(frame=cs.KEYBOARD_RECT,
                                  action=self.button_tapped)
       
        self.create_controls()
        # status and debug messages
        self.msg = LabelNode('', position=(cs.GAME_W, cs.GAME_H - cs.KEYBOARD_RECT.min_y + 50),
                             color=cs.WHITE, anchor_point=(0, 0),
                             parent=self)
        fontsize = (cs.W - cs.FLIGHT_RECT.max_x) // 18
        self.msg_right = LabelNode('', position=(cs.HUD_RIGHT.x + 10, cs.HUD_H + 20),
                                   color=cs.WHITE, font=('Copperplate', 18),
                                   anchor_point=(0, 1), parent=self)
        self.obj_status = LabelNode('', position=(cs.GAME_W, cs.GAME_H),
                                    anchor_point=(0, 1), font=('Copperplate', fontsize),
                                    color=cs.WHITE, parent=self)
        # self.cloud = IsometricCloud(loc=Point(cs.KEYBOARD_X+cs.KEYBOARD_W/2, cs.GAME_H-200))
        self.msg_left = LabelNode('', position=(cs.HUD_LEFT.x + 10, cs.HUD_H),
                                  color=cs.WHITE, font=('Copperplate', 18),
                                  anchor_point=(0, 1), parent=self)
        self.kbd = Keyboard(self)

        self.hud = HudPanel()
        self.add_child(self.hud)

        self.background = self.create_background()
        self.background.z_position = -1
        self.add_child(self.background)
        try:
            # for testing
            self.add_child(self.joystick)
            self.add_child(self.joystick_thrust)
            self.add_child(self.fire_button)
            self.view.add_subview(self.keypad)
        except AttributeError:
            pass
            
        self.moved = False

        self.renderer = Renderer(depth_sort=True, backface_cull=cs.WIREFRAME_REMOVAL)
        self.renderer.viewport = cs.FLIGHT_RECT  # x, y, w, h
        
        self.camera = Camera(
            position=Vector3(0, 0, 0),  # -1000),
            fov=math.radians(45),
            yaw=0,
            pitch=0,
            z_near=5.0,
            z_far=300000)
            
        self.mainloop = MainLoop(self)

        self.laser_sight.alpha = 0
        self.laser_lines.alpha = 0
        self.hud.safe_node.alpha = 0
        self.hud.ecm_node.alpha = 0
        # initially make these keys disabled
        for keyname in ['Jump', 'Escape', 'Cancel Escape', 'ECM', 'Bomb',
                        'Missile', 'Target Off', 'Target', 'Look Port',
                        'Look Stbd', 'Look Fwd', 'Look Aft', 'Docking', 'Compass Planet',
                        'Fire laser', 'Hyper Space', 'Cancel Docking', 'New Galaxy']:
            self.keypad.key_change(keyname, enabled=False)
        
        self.emit_counter = 0
        self.emit_rate = 5  # Emit every 5 frames
        self.is_joystick_active = False
        self._explosion_t = 0.0
        self.paused = False
        if not hasattr(self, 'test'):
            self.mainloop.game_loop()
        
    def create_background(self):
        #  background is  yellow line plus laser sights and lines
        # background is a Node to hold all displayable objects
        # the screen can be cleared by simply rdmoving all the children
        # except the line and sights
        # The top line shoukd be at row location 3, to allow teo text lines
        background_screen = Node()
        # a yellow border around the whole screen
        B = cs.BORDER
        path = ui.Path.rect(-B/2, -B/2, cs.GAME_W - B, cs.GAME_H - 2 * B)
        path.line_width = B
        path.move_to(0, cs.TOP_LINE)
        path.line_to(cs.FLIGHT_W + 4, cs.TOP_LINE)
        path.move_to(0, cs.GAME_H - cs.HUD_H_L-15)
        # add lines around console and scanner, with arcs at corners
        
        # horiz
        x1 = cs.HUD_LEFT.max_x - cs.RADIUS - B
        y1 = cs.GAME_H - cs.HUD_H_L - 15
        path.line_to(x1, y1)
        path.add_arc(x1, y1 - cs.RADIUS, cs.RADIUS, math.pi/2,  0, False)
        # vert
        x2 = cs.HUD_LEFT.max_x - B
        y2 = cs.GAME_H - cs.HUD_H-15+cs.RADIUS
        path.line_to(x2, y2)
        path.add_arc(x2 + cs.RADIUS, y2, cs.RADIUS, math.pi, -math.pi/2, True)
        # horiz
        x3 = cs.HUD_CENTRE.max_x-cs.RADIUS
        y3 = cs.GAME_H - cs.HUD_H-15
        path.line_to(x3, y3)
        path.add_arc(x3, y3 + cs.RADIUS, cs.RADIUS, -math.pi/2, 0, True)
        # vert
        x4 = cs.HUD_CENTRE.max_x
        y4 = cs.GAME_H - cs.HUD_H_R - cs.RADIUS-15
        path.line_to(x4, y4)
        path.add_arc(x4 + cs.RADIUS, y4, cs.RADIUS, -math.pi,  math.pi/2, False)
        # horiz
        path.line_to(cs.HUD_RIGHT.max_x - 15, y4 + cs.RADIUS)
        y = cs.GAME_H - cs.HUD_LEFT.max_y - cs.HUD_H + cs.HUD_LEFT.h + 0 * B
        path.append_path(ui.Path.rounded_rect(cs.HUD_LEFT.x - B, y,
                                              cs.HUD_LEFT.w,
                                              cs.HUD_H - cs.HUD_LEFT.h + B,
                                              cs.RADIUS))
        path.append_path(ui.Path.rounded_rect(cs.HUD_RIGHT.x - B, y,
                                              cs.HUD_RIGHT.w - 2 * B,
                                              cs.HUD_H - cs.HUD_RIGHT.h + B,
                                              cs.RADIUS))
        yellow_line = ShapeNode(path,
                                fill_color='clear',
                                stroke_color=cs.YELLOW,
                                position=(0, 3 * B),
                                anchor_point=(0, 0),
                                z_position=-1,
                                parent=background_screen)
        yellow_line.name = 'yellow_line'
        
        self.laser_lines = self.draw_laser_lines()
        background_screen.add_child(self.laser_lines)
        self.laser_sight = self.draw_laser_sight()
        background_screen.add_child(self.laser_sight)
        
        return background_screen
        
    def create_controls(self):
        # control joystick, press to fire
        self.joystick = Joystick(position=cs.JOYSTICK_1_POSITION,
                                 color='white',
                                 show_xy=False,
                                 msg='',
                                 radius=cs.JOYSTICK_1_RADIUS)
        self.joystick_thrust = Joystick(position=cs.JOYSTICK_2_POSITION,
                                        color='white',
                                        alpha=0.8,
                                        show_xy=False,
                                        msg='',
                                        mode='NS',
                                        autoreturn=False,
                                        radius=cs.JOYSTICK_2_RADIUS)
        image = pil_to_ui(set_colorkey('Fire2.png'))
        self.fire_button = SpriteNode(Texture(image),
                                      size=cs.FIRE_BUTTON_RECT.size,
                                      position=cs.FIRE_BUTTON_RECT.center(),
                                      )
                                       
    def draw_laser_lines(self):
        # create laser lines. These are fixed and always present
        # set alpha = 1 to show
        path = ui.Path()
        path.line_width = 2
        path.move_to(*cs.FLIGHT_RECT.center())
        path.line_to(32, cs.FLIGHT_RECT.min_y)
        path.move_to(*cs.FLIGHT_RECT.center())
        path.line_to(48, cs.FLIGHT_RECT.min_y)
        path.move_to(*cs.FLIGHT_RECT.center())
        path.line_to(cs.FLIGHT_RECT.max_x - 48, cs.FLIGHT_RECT.min_y)
        path.move_to(*cs.FLIGHT_RECT.center())
        path.line_to(cs.FLIGHT_RECT.max_x - 32, cs.FLIGHT_RECT.min_y)
        laser_lines = ShapeNode(path, stroke_color='white',
                                fill_color='clear',
                                anchor_point=(0.5, 0),
                                position=cs.FLIGHT_RECT.center())
        laser_lines.alpha = 0
        laser_lines.rotation = math.pi
        laser_lines.name = 'laser lines'
        return laser_lines
                            
    def draw_laser_sight(self):
        # create laser sight. These are fixed and always oresent
        # set alpha = 1 to show
        start = 8
        finish = 16
        x = cs.FLIGHT_RECT.center().x
        y = cs.FLIGHT_RECT.center().y
        path = ui.Path()
        path.line_width = 2
        
        path.move_to(x + start, y)
        path.line_to(x + finish, y)
        
        path.move_to(x - start, y)
        path.line_to(x - finish, y)
        path.move_to(x, y + start)
        path.line_to(x, y + finish)
                
        path.move_to(x, y - start)
        path.line_to(x, y - finish)
        
        laser_sight = ShapeNode(path, stroke_color='white',
                                fill_color='clear',
                                anchor_point=(0.5, 0.5),
                                position=cs.FLIGHT_RECT.center())
        laser_sight.alpha = 0
        laser_sight.name = 'laser sight'
        return laser_sight
                       
    def update(self):
        self.mainloop.game_loop()
        if not cs.WIREFRAME:
            self.mainloop.swat.planet_image.update(self.t)
            self.mainloop.swat.sun_image.update(0)
        self.emit_counter += 1
        if 'joystick' in self.active_touches.values():  # and self.emit_counter >= self.emit_rate:
            
            self.emit_counter = 0
            if self.is_joystick_active:
                # 2. Polling: The joystick object already knows its current x, y
                # from the last touch_moved event.
                self.joystick.update()
                """Pushes commands based on current joystick state."""
                if self.mainloop.current_screen in cs.SCR_OUTSIDE:
                    # in flight screen, joystick is analogue
                    x, y = self.joystick.x, self.joystick.y
                    # logger.debug(f'>{x:.2f},{y:.2f}')
                    self.input_queue.put(f'>{x:.2f},{y:.2f}')
                else:
                    for key in self.joystick.keys_pressed:
                        self.input_queue.put(key.capitalize())
             
        elif 'fire' in self.active_touches.values() and self.emit_counter >= self.emit_rate:
            self.emit_counter = 0
            self.input_queue.put('Fire Laser')
            
        # no joystick touched, emit 0,0 at slower rate
        elif self.emit_counter >= 2 * self.emit_rate:
            self.emit_counter = 0
            # self.input_queue.put('>0.00, 0.00')
        for obj in [obj for obj in self.mainloop.universe
                    if obj.exploding]:
            obj.explosion_time += self.dt * EXPLOSION_SPEED
            if obj.explosion_time >= 1.0:
                obj.exploding = False
                obj.flags |= cs.FLG_REMOVE
        # if self.mainloop.mcount % 7 == 0:
        #   self.msg.text = (f'Draw:{(self.elapsed_top *1000):.1f}ms'
        #                   f' Loop:{(self.mainloop.loop_elapsed *1000):.1f}ms'
        #                   f'Total {(self.elapsed_top + self.mainloop.loop_elapsed)*1000:.1f}ms')
            
    def draw(self):
        # draw whatever is in mainloop universe
        self.t1 = time()
        if self.mainloop.current_screen in [*cs.SCR_OUTSIDE, cs.SCR_INTRO_ONE,
                                            cs.SCR_INTRO_TWO, cs.SCR_MISSION]:
            objects = [obj
                       for obj in self.mainloop.universe
                       if obj.type != 0]
            
            # Draw all objects
            for obj in objects:
                if obj.exploding:
                    # Draw the explosion instead of the ship
                    self._explosion_t += self.dt * EXPLOSION_SPEED
                    obj.model.explosion_time = self._explosion_t
                    if self._explosion_t >= 1.0:
                        obj.flags |= cs.FLG_REMOVE
                        obj.exploding = False
                        self._explosion_t = 0.0
                    self.renderer.explode(obj.model, self.camera, cs.FLIGHT_RECT)
                    
                else:
                    # Draw normal ship (Renderer.draw checks .visible)
                    self.renderer.draw([obj.model], self.camera, cs.FLIGHT_RECT)
        self.elapsed_top = time() - self.t1
                
    def key_change(self, key_name, name=None, color=None, enabled=None):
        # change appearance of key
        try:
           for button in self.keypad.subviews:
              if button.name == key_name:
                break
           else:
               raise AttributeError(f'Button {key_name} not found')
               return
           if name is not None:
               button.name = name
           if color is not None:
               button.background_color = color
           if enabled is not None:
               button.enabled = enabled
        except AttributeError as e:
            AttributeError(f'Button attribute not valid {e}')
   
    def button_tapped(self, sender):
        """Handles discrete button taps (EliteKeypad or standard buttons)."""
        try:
            if isinstance(sender.superview, EliteKeypad):
                # Convert keypad names to expected letters
                self.input_queue.put(sender.name)
            else:
                self.input_queue.put(sender.title.lower())
        except Exception:
            print(traceback.format_exc())
                            
    def touch_began(self, touch):
        """Registers which controller element a specific touch ID belongs to."""
        # Track the touch ID to prevent 'sliding' from one control to another
        if self.joystick.bbox.contains_point(touch.location):
            self.active_touches[touch.touch_id] = 'joystick'
            self.joystick.touch_began(touch)
            self.is_joystick_active = True
        elif self.joystick_thrust.bbox.contains_point(touch.location):
            self.active_touches[touch.touch_id] = 'thrust'
            self.joystick_thrust.touch_began(touch)
        elif cs.FIRE_BUTTON_RECT.contains_point(touch.location):
            self.active_touches[touch.touch_id] = 'fire'
        elif self.obj_status.bbox.contains_point(touch.location):
            self.active_touches[touch.touch_id] = 'target'
        else:
            self.active_touches[touch.touch_id] = 'screen'
            # print('screen', touch.location)
            
        self.touched = touch.location
    
    def touch_moved(self, touch):
        """Processes movement independently for each active touch ID."""
        self.moved = True
        
        # Identify which control this specific touch is operating
        control = self.active_touches.get(touch.touch_id)
        if control == 'joystick':
            self.joystick.touch_moved(touch)
            # emission of queue messages handled by self.update
                
        elif control == 'thrust':
            self.joystick_thrust.touch_moved(touch)
            self.joystick_thrust.update()
            self.input_queue.put(f'<{self.joystick_thrust.y}')
            # for key in self.joystick_thrust.keys_pressed:
            #    if key == 'up':
            #       self.input_queue.put('inc_speed')
            #    elif key == 'down':
            #        self.input_queue.put('dec_speed')
    
    def touch_ended(self, touch):
        """Cleans up the specific touch and handles 'tap' logic for the queue."""
        control = self.active_touches.pop(touch.touch_id, None)
        if control == 'joystick':
            self.joystick.touch_ended(touch)
            self.is_joystick_active = False
            self.input_queue.put('>0.00,0.00')
        elif control == 'thrust':
            self.joystick_thrust.touch_ended(touch)
        elif control == 'screen' and cs.FLIGHT_RECT.contains_point(touch.location):
            self.input_queue.put(f'#{touch.location.x:.0f},{touch.location.y:.0f}')
        elif control == 'target' and self.obj_status.bbox.contains_point(touch.location):
            self.input_queue.put(f'->{touch.location.x:.0f},{touch.location.y:.0f}')
        # If the screen was tapped quickly without moving
        elif not self.moved and not self.mainloop.space.safe_mode:
          self.input_queue.put('Fire Laser')
           
        self.moved = False
          
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  
class Keyboard:
    """Holds the current state of every logical key for one frame."""
    
    # because there is no keyboard we dont really need to share keys e,g,F
    
    def __init__(self, parent_scene):
       self.parent_scene = parent_scene
       
    def poll(self, mode=None):
        """
        Consumes an element from the queue based on the requested mode.
        mode 0: Movement and flight keys)
        mode 1: Screen change keys
        mode None: Everything
        """
        
        if self.parent_scene is None:
            return None
    
        # Definitions for modes
        # movement_keys = {'up', 'down', 'left', 'right', 'enter', 'joy2_up', 'joy2_down', 'Missile', 'Select'}
        screen_keys = {'Launch', 'Equip', 'Galaxy Chart', 'Local Chart', 'Data', 'Trade', 'Prices',
                       'Market',  'Status', 'Pause', 'Resume', 'Menu', 'Quit'}
        # We use a temporary list to store items we aren't consuming
        
        # so we can put them back in the queue later
        skipped_items = []
        found_command = None
    
        # 2. Process the queue
        q = self.parent_scene.input_queue
        
        while not q.empty():
            item = q.get()
            
            # Determine the mode of the current item
            
            screen_mode = 1 if item in screen_keys else 0
            # Check if this item matches our requested mode
            if mode is None or screen_mode == mode:
                found_command = item
                # If we found a valid command mapping, stop searching
                if found_command:
                    setattr(self, found_command, True)
                    break
            else:
                # Not the mode we are looking for; save it to re-queue
                skipped_items.append(item)
    
        # 3. Put non-matching items back into the queue for the next poll call
        for item in skipped_items:
            q.put(item)
    
        return found_command


def run_game():
    g = EliteScene()
    # g.setup = g.setup_
    # g.setup_()
    #
    run(g, show_fps=True)

              
if __name__ == '__main__':
 run_game()
