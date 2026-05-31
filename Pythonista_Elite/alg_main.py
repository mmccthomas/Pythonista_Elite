# alg_main.py
# Elite - The New Kind, Python/Pythonista port
# Converted from C by C.J.Pinder. Original (C) I.Bell & D.Braben 1984.

import time
import random
import game_engine
from copy import copy
from stars import Starfield
from graphics import Graphics
from autopilot import Pilot
from trade import TradeManager
from space import Space
from swat import Swat, UnivObject, Ship
from elite import EliteState, Commander, GalaxySeed
import elite
from planet import PlanetGenerator
from docked import Docked
from intro import EliteIntro
from missions import MissionManager
import constants as cs
from constants import logger
from vector import set_init_matrix, Vector


ESCAPE_SETUP = 1
ESCAPE_FLEE = 2
ESCAPE_RECOVER = 3
ESCAPE_DOCK = 4
LAUNCH_SETUP = 5
LAUNCH_CIRCLES = 6
LAUNCH_COMPLETE = 7


class Sound():
 
    def __init__(self, enabled=True):
       self.sounder = game_engine.SoundComponent()
       self.enabled = enabled
       
    def play_sample(self, sound_id):
        file_name = f'sounds/{sound_id}.wav'
        if self.enabled:
            self.sounder.play_sound_effect(file_name)
            
    def play_midi(self, sound_id, loop=False):
        file_name = f'sounds/{sound_id}.mid'
        if self.enabled:
           self.sounder.play_midi(file_name)
    
    def stop_midi(self):
        if self.enabled:
            self.sounder.stop_midi()
    
    def update_sound(self):
        pass
    
    def sound_startup(self):
        if self.enabled:
            self.play_midi(cs.SND_ELITE_THEME)
    
    def sound_shutdown(self):
        if self.enabled:
            self.sounder.stop_music()
            self.stop_midi()


# ═══════════════════════════════════════════════════════════════════════════════
# Keyboard stubs  –  replace with scene touch/keyboard events
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# Game-state
# ═══════════════════════════════════════════════════════════════════════════════


class MyShip:
    max_speed = 40
    max_roll = 31
    max_climb = 8
    max_fuel = 70


class Commander_:
    name = "JAMESON"
    front_laser = 0
    rear_laser = 0
    left_laser = 0
    right_laser = 0
    docking_computer = False
    ecm = False
    energy_bomb = False
    escape_pod = False
    ship_x = ship_y = 0
    galaxy_number = 0
    galaxy = GalaxySeed()
    
    
class MainLoop():
    
    def __init__(self, parent_scene):
     
       self.parent_scene = parent_scene
       self.myship = MyShip()
       self.cmdr = Commander()
       self.saved_cmdr = Commander(0xAD, 0x38, 0x14, 0x9C, 0x15, 0x1D)
       
       self.current_screen = cs.SCR_INTRO_ONE
       self.docked = True
       self.finish = False
       self.game_over = False
       self.game_paused = False
       self.auto_pilot = False
       self.witchspace = False
       self.hyper_ready = False
       self.detonate_bomb = False
       self.instant_dock = False
       self.warp_stars = False
            
       self.docked_planet = GalaxySeed(0xAD, 0x38, 0x14, 0x9C, 0x15, 0x1D)
       self.hyperspace_planet = GalaxySeed(0xAD, 0x38, 0x14, 0x9C, 0x15, 0x1D)
       self.current_planet_data = None

       # Flight Variables
       self.game_over = False
                       
       self.laser_temp = 0
       self.auto_pilot = False

       # Options
       self.instant_dock = False
                               
       self.flight_speed = 1
       self.rolling = False
       self.climbing = False
  
       self.front_shield = 255
       self.aft_shield = 255
       self.energy = 255
       self.draw_lasers = 0
       self.mcount = 0
       self.message_count = 0
       self.message_string = ""
       
       self.cross_x = -1
       self.cross_y = -1
       self.old_cross_x = -1
       self.old_cross_y = -1
       self.cross_timer = 0
       self.escape_sequence = ESCAPE_SETUP
       self.launch_sequence = LAUNCH_SETUP
       self.launch_timer = 0
       self.break_mode = 'launch'
       self.NUMBER_FRAMES = 60
       self.find_input = False
       self.find_name = ""
       
       # ------ class instances
       self.kbd = parent_scene.kbd
       self.keypad = parent_scene.keypad
       self.msg = parent_scene.msg
       self.hud = parent_scene.hud
       # Stub universe array
       self.universe = [None] * cs.MAX_UNIV_OBJECTS
       self.ship_count = {}
       self.commander = Commander()
       self.gfx = Graphics(parent_scene)
       self.trade = TradeManager(self)
       self.stars = Starfield(self)
       self.swat = Swat(self)
       self.universe = self.swat.universe
       self.pilot = Pilot(self)
       self.planet = PlanetGenerator(self)
       self.in_dock = Docked(self)
       self.ship = UnivObject(parent_scene)
       self.sound = Sound(parent_scene.enable_sound)
       self.space = Space(self)
       self.missions = MissionManager(self)
       self.elite_state = EliteState()
       self.intro = EliteIntro(self)
       
       self.initialise_game()
       self.space.dock_player()
       self.input_queue = self.parent_scene.input_queue
       self.sound.sound_startup()
       # self.kbd startup handled by Keyboard.poll()
       self.current_screen = cs.SCR_INTRO_ONE

    # -------- functions
        
    @staticmethod
    def set_rand_seed(seed):
        random.seed(seed)
              
    def restore_saved_commander(self):
        self.elite_state.restore_saved_commander(self.planet, self.trade)
        self.current_planet_data = self.elite_state.current_planet_data
                                                            
    def save_commander_file(self, path):
        ok, msg = elite.save_game_json(self.cmdr, path)
        return ok
        
    def load_commander_file(self, path):
        ok, msg = elite.load_game_json(self.cmdr, path)
        return ok
        
    @staticmethod
    def get_filename(path):
        return path.split('/')[-1]
        
    @staticmethod
    def rand255():
        return random.randint(0, 255)
        
    @staticmethod
    def rand16bit():
        return random.randint(0, 65535)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # Core game logic  (direct translations of the C functions)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def initialise_game(self):
    
        self.set_rand_seed(time.time())
        self.current_screen = cs.SCR_INTRO_ONE
    
        self.restore_saved_commander()
    
        self.flight_speed = 1
        self.flight_roll = 0
        self.flight_climb = 0
        self.docked = True
        self.front_shield = 255
        self.aft_shield = 255
        self.energy = 255
        self.draw_lasers = 0
        self.mcount = 0
        self.hyper_ready = False
        self.detonate_bomb = False
        self.find_input = False
        self.witchspace = False
        self.game_paused = False
        self.auto_pilot = False
    
        self.stars.create_new_stars()
        self.swat.clear_universe()
    
        self.myship.max_speed = 40
        self.myship.max_roll = 31
        self.myship.max_climb = 8
        self.myship.max_fuel = 70
        
    def finish_game(self):
        self.finish = True
        self.game_over = True
                
    # ── Laser sights ──────────────────────────────────────────────────────────────
    
    def draw_laser_sights(self):
        laser = 0
        view_ = {cs.SCR_FRONT_VIEW: ("Front View", self.cmdr.front_laser),
                 cs.SCR_REAR_VIEW: ("Rear View", self.cmdr.rear_laser),
                 cs.SCR_LEFT_VIEW: ("Left View", self.cmdr.left_laser),
                 cs.SCR_RIGHT_VIEW: ("Right View", self.cmdr.right_laser)}
        view_ident = view_[self.current_screen][0]
        self.gfx.display_centre_text(1, view_ident, 120, cs.WHITE)
        laser = view_[self.current_screen][1]
                    
        # make laser sight visible
        self.parent_scene.laser_sight.alpha = int(laser)
        return laser
                    
    # ── Arrow key dispatchers ─────────────────────────────────────────────────────
    
    def arrow_right(self):
        self.space.decrease_flight_roll()
        # self.space.decrease_flight_roll()
        self.rolling = True
    
    def arrow_left(self):
        self.space.increase_flight_roll()
        # self.space.increase_flight_roll()
        self.rolling = True
     
    def arrow_up(self):
        self.space.increase_flight_climb()
        self.climbing = True
    
    def arrow_down(self):
        self.space.decrease_flight_climb()
        self.climbing = True
    
    # ── Auto-dock ─────────────────────────────────────────────────────────────────
    
    def auto_dock(self):
    
        ship = Ship()
        ship.location = Vector(0.0, 0.0, 0.0)
        ship.rotmat = set_init_matrix()
        ship.type = -96
        ship.velocity = self.flight_speed
        ship.acceleration = 0
        ship.bravery = 0
        ship.rotz = 0
        ship.rotx = 0
    
        self.pilot.auto_pilot_ship(ship)   # modifies ship in-place
    
        self.flight_speed = min(22, ship.velocity) if ship.velocity > 22 else ship.velocity
    
        if ship.acceleration > 0:
            self.flight_speed = min(22, self.flight_speed + 1)
        if ship.acceleration < 0:
            self.flight_speed = max(1,  self.flight_speed - 1)
    
        if ship.rotx == 0:
            self.space.flight_climb = 0
        if ship.rotx < 0:
            self.space.increase_flight_climb()
            if ship.rotx < -1:
                self.space.increase_flight_climb()
        if ship.rotx > 0:
            self.space.decrease_flight_climb()
            if ship.rotx > 1:
               self.space.decrease_flight_climb()
    
        if ship.rotz == 127:
            self.space.flight_roll = -14
        else:
            if ship.rotz == 0:
               self.space.flight_roll = 0
            if ship.rotz > 0:
                self.space.increase_flight_roll()
                if ship.rotz > 1:
                    self.space.increase_flight_roll()
            if ship.rotz < 0:
                self.space.decrease_flight_roll()
                if ship.rotz < -1:
                    self.space.decrease_flight_roll()
        
    # ── Escape sequence ───────────────────────────────────────────────────────────
    
    def run_escape_sequence(self):
        # convert to state machine
        self.current_screen = cs.SCR_ESCAPE_POD
        if self.escape_sequence == ESCAPE_SETUP:
            self.flight_speed = 1
            self.space.flight_roll = 0
            self.space.flight_climb = 0
            
            newship = self.swat.add_new_ship("COBRA_MK_3", 0, 0, 200, None, -127, -127)
            self.universe[newship].velocity = 7
            self.sound.play_sample(cs.SND_LAUNCH)
            self.escape_counter = 90
            self.escape_sequence = ESCAPE_FLEE
            
        if self.escape_sequence == ESCAPE_FLEE:
           self.escape_counter -= 1
           if self.escape_counter <= 0:
              self.escape_sequence = ESCAPE_RECOVER
           if self.escape_counter == 50:
               self.universe[newship].flags |= cs.FLG_DEAD
               self.sound.play_sample(cs.SND_EXPLODE)
           
           self.gfx.clear_display()
           self.stars.update_starfield()
           self.space.update_universe()
   
           self.universe[newship].location.x = 0
           self.universe[newship].location.y = 0
           self.universe[newship].location.z += 2
   
           self.gfx.display_centre_text(
               21,
               "Escape pod launched - Ship auto-destruct initiated.",
               120, cs.WHITE)
              
           self.gfx.update_screen()
           
        if self.escape_sequence == ESCAPE_RECOVER:
            if (self.swat.ship_count.get("CORIOLIS", 0)
                    or self.swat.ship_count.get("DODEC", 0)):
                self.escape_sequence == ESCAPE_DOCK
        
            self.auto_dock()
    
            if abs(self.flight_roll) < 3 and abs(self.flight_climb) < 3:
                for i in range(cs.MAX_UNIV_OBJECTS):
                    if self.universe[i] is not None and self.universe[i].type != 0:
                        self.universe[i].location.z -= 1500
    
            self.warp_stars = True
            self.gfx.clear_display()
            self.stars.update_starfield()
            self.space.update_universe()
            
            self.gfx.update_screen()
            
        if self.escape_sequence == ESCAPE_DOCK:
            self.swat.abandon_ship(self)
        
    # ── Info message ──────────────────────────────────────────────────────────────
    
    def info_message(self, message, color=None):
        self.message_string = message
        self.message_count = 37
       
    # ── Main input handler ────────────────────────────────────────────────────────
    
    def quit_screen(self):
        self.check_change_screen()
        key = self.kbd.poll()
        match key:
            case 'y':
                self.finish_game()
            case 'n':
                if self.docked:
                    self.current_screen = cs.SCR_CMDR_STATUS
                else:
                    self.current_screen = cs.SCR_FRONT_VIEW
    
    def find_planet(self):
        # Find planet by name.
        # pops up a list dialog populated with sorted planet names
        glx = GalaxySeed().copy()
        planet_names = []
        for _ in range(256):
            planet_names.append(self.planet.name_planet(glx))
            for _ in range(4):
                glx.waggle()
        planet_names = sorted(planet_names)
        name = self.gfx.list_files(planet_names)
        if name:
            self.in_dock.find_planet_by_name(name)
            
    def chart_screen(self):
        # galactic or short range chart
        self.check_change_screen()
        key = self.kbd.poll()
        if key:
            self.parent_scene.msg.text = f'received: {key}'
        match key:
           case None:
               pass
           case 'Up':
               self.in_dock.move_cross(0, 1)
           case 'Down':
               self.in_dock.move_cross(0, -1)
           case 'Left':
               self.in_dock.move_cross(-1, 0)
           case 'Right':
               self.in_dock.move_cross(1, 0)
           case 'Select':
               self.in_dock.move_cursor_to_origin()
           case 'Find':
               self.find_planet()
           case key if key.startswith('#'):
               self.in_dock.move_cursor_to_xy(key)
           case key if key.startswith('$'):
               self.in_dock.find_planet_by_name(key.removeprefix('$'))
            
        if self.current_screen == cs.SCR_GALACTIC_CHART:
            self.in_dock.display_galactic_chart()
        else:
            self.in_dock.display_short_range_chart()
                                    
    def market_trade_screen(self):
        self.in_dock.display_market_prices()
        key = self.kbd.poll()
        match key:
            case 'Up':
                self.in_dock.select_previous_stock()
            case 'Down':
                self.in_dock.select_next_stock()
            case 'Left':
                self.in_dock.sell_stock()
            case 'Right':
                self.in_dock.buy_stock()
        
    def market_prices_screen(self):
        # i think this is fixed screen when in flight
        self.check_change_screen()
        self.kbd.poll()
        
    def _enable_flight_keys(self):
        # enable normal flight keys plus others where purchased
        for keyname in ['Jump', 'Missile', 'Target',
                        'Look Port', 'Hyper Space',
                        'Look Stbd', 'Look Fwd',
                        'Look Aft', 'Fire Laser']:
            self.parent_scene.keypad.key_change(keyname, enabled=True)
            
        self.parent_scene.keypad.key_change('Equip', name='Inventory')
        self.parent_scene.keypad.key_change('Market', name='Target Prices')
        self.parent_scene.keypad.key_change('Trade', name='Cargo')
        
        self.additional_items = {'ecm': 'ECM',
                                 'energy_bomb': 'Bomb',
                                 'docking_computer': 'Docking',
                                 'galactic_hyperdrive': 'New Galaxy',
                                 'escape_pod': 'Escape'}
        for k, v in self.additional_items.items():
            state = getattr(self.cmdr, k)
            self.parent_scene.keypad.key_change(v, enabled=state)
            
    def _entering_dock(self):
        # check mission brief and set keys
        self.missions.check_mission_brief(self.docked_planet)
        self.in_dock.display_commander_status()
        
        # swap keys for docked mode
        for keyname in self.flight_keys:
            self.keypad.key_change(keyname, enabled=False)
        self.keypad.key_change('Cargo', name='Trade')
        self.parent_scene.keypad.key_change('Inventory', name='Equip')
        self.parent_scene.keypad.key_change('Target Prices', name='Market')
                   
    def launch(self):
        # enable flight keys and launch
        self._enable_flight_keys()
        self.space.launch_player()
       
    def equipment_screen(self):
        self.in_dock.equip_ship()
        key = self.kbd.poll()
        match key:
            case 'Up':
                self.in_dock.select_previous_equip()
            case 'Down':
                self.in_dock.select_next_equip()
            case 'Left':
                pass
            case 'Right':
                self.in_dock.buy_equip()
                              
    def check_change_screen(self):
        # Accessible from all screens
        # just changes state
        # emit only Screen keys, designated in Elite.Keyboard, others placed back in queue
        key = self.kbd.poll(mode=1)
        match key:
            case 'Launch':
                self.break_mode = 'launch'
                if self.docked:
                   self.swat.clear_universe()
                   self.current_screen = cs.SCR_BREAK_PATTERN
                else:
                    self.current_screen = cs.SCR_FRONT_VIEW
            case 'Equip':
                self.current_screen = cs.SCR_EQUIP_SHIP
            case 'Inventory':
                self.current_screen = cs.SCR_INVENTORY
            case 'Galaxy Chart':
                self.current_screen = cs.SCR_GALACTIC_CHART
            case 'Local Chart':
                self.current_screen = cs.SCR_SHORT_RANGE
            case 'Data':
                self.current_screen = cs.SCR_PLANET_DATA
            case 'Trade' | 'Market' | 'Target Prices':
                if not self.witchspace:
                    self.current_screen = cs.SCR_MARKET_PRICES
            case 'Status':
                self.current_screen = cs.SCR_CMDR_STATUS
            case 'Cargo':
                self.current_screen = cs.SCR_INVENTORY
            case 'Pause' | 'Resume':
                # pause key is toggle
                self.game_paused = not self.game_paused
                if self.game_paused:
                    self.keypad.key_change(key_name='Pause',
                                           name='Resume')
                else:
                     self.keypad.key_change(key_name='Resume',
                                           name='Pause')                        
            case 'Quit':
                pass
            case 'Help':
                pass                    
               
    def in_flight_keys(self):
        self.check_change_screen()
        key = self.kbd.poll()
        if key is not None:
           self.msg.text = key
        match key:
            case None:
                pass
            case 'Look Fwd':
                self.current_screen = cs.SCR_FRONT_VIEW
                self.stars.flip_stars()
            case 'Look Aft':
                self.current_screen = cs.SCR_REAR_VIEW
                self.stars.flip_stars()
            case 'Look Port':
                self.current_screen = cs.SCR_LEFT_VIEW
                self.stars.flip_stars()
            case 'Look Stbd':
                self.current_screen = cs.SCR_RIGHT_VIEW
                self.stars.flip_stars()
            case 'Fire Laser':
                if self.draw_lasers == 0:
                    self.draw_lasers = self.swat.fire_laser()
            case 'Docking':                
                self.break_mode = 'docking'
                if self.instant_dock:
                    self.space.engage_docking_computer()
                else:
                    self.pilot.engage_auto_pilot()
                    self.keypad.key_change(key_name='Docking',
                                           name='Cancel Docking')                            
            case 'Cancel Docking':
                 self.pilot.disengage_auto_pilot()
                 self.keypad.key_change(key_name='Cancel Docking',
                                        name='Docking')         
                        
            case 'ECM':
                if self.cmdr.ecm:
                    self.swat.activate_ecm(1)
            case 'find':
                self.find_planet()
            case 'Hyper Space':
                self.break_mode = 'hyperspace'
                self.space.start_hyperspace()
            case 'New Galaxy':
                self.break_mode = 'hyperspace'
                self.space.start_galactic_hyperspace()
            case 'Jump':
                if not self.witchspace:
                   self.space.jump_warp()
            case 'Missile':
                self.swat.fire_missile()
            case 'Target':
                self.swat.arm_missile()
            case 'Target off':
                self.swat.unarm_missile()
            case 'inc_speed':
                if self.flight_speed < self.myship.max_speed:
                    self.flight_speed += 1
            case 'dec_speed':
                if self.flight_speed > 1:
                    self.flight_speed -= 1
            case 'Up':
                self.arrow_up()
            case 'Down':
                self.arrow_down()
            case 'Left':
                self.arrow_left()
            case 'Right':
                self.arrow_right()
            case key if key.startswith('>'):
               self.space.roll_pitch_control(key)    
            case 'Bomb':
                if self.cmdr.energy_bomb:
                    self.detonate_bomb = True
                    self.cmdr.energy_bomb = False
            case 'Escape':
                if self.cmdr.escape_pod and not self.witchspace:
                    self.current_screen = cs.SCR_ESCAPE_POD
            case 'Cancel Escape':
                self.pilot.disengage_auto_pilot()
                                                    
    def in_flight_screen(self):
        # This is the flight loop
        self.in_flight_keys()
        
        self.gfx.update_screen()
         
        if self.game_paused:
            return
  
        if self.message_count > 0:
            self.message_count -= 1
        if (self.mcount & 128  == 0):
         
            # Damp roll / climb when no key held
           damping_factor = 0.92  # Adjust between 0.0 and 1.0 (lower is faster stop)
           stop_threshold = 0.1   # The "Deadzone"
           """
           if self.rolling:
               self.space.flight_roll *= damping_factor
               if abs(self.space.flight_roll) < stop_threshold:
                   self.space.flight_roll = 0
               self.rolling = bool(self.space.flight_roll)
           
           if self.climbing:
               self.space.flight_climb *= damping_factor
               if abs(self.space.flight_climb) < stop_threshold:
                   self.space.flight_climb = 0
               self.climbing = bool(self.space.flight_climb)
    
           # Damp roll / climb when no key held
          
           if self.rolling:
               if self.space.flight_roll > 0:
                   self.space.decrease_flight_roll()
               if self.space.flight_roll < 0:
                   self.space.increase_flight_roll()
           self.rolling = bool(self.space.flight_roll)
           
           if self.climbing:
               if self.space.flight_climb > 0:
                   self.space.decrease_flight_climb()
               if self.space.flight_climb < 0:
                   self.space.increase_flight_climb()
           self.climbing = bool(self.space.flight_climb)
           """
        # Clear view for space screens
        self.gfx.clear_display()
        self.stars.update_starfield()
 
        if self.pilot.auto_pilot_active:
            self.auto_dock()
            if (self.mcount & 127) == 0:
                self.info_message("Docking Computers On")
 
        self.space.update_universe()
        
        self.draw_laser_sights()
        if self.draw_lasers:
            self.parent_scene.laser_lines.alpha = 1
            self.draw_lasers -= 1
        else:
            self.parent_scene.laser_lines.alpha = 0
 
        if self.message_count > 0:
            self.gfx.display_centre_text(cs.NUM_LINES-1, self.message_string, 120, cs.WHITE)
 
        if self.space.hyper_ready:
            self.space.display_hyper_status()
            if (self.mcount & 3) == 0:
                self.space.countdown_hyperspace()
          
        self.mcount = (self.mcount - 1) & 255
 
        if (self.mcount & 7) == 0:
            self.space.regenerate_shields()
 
        if (self.mcount & 31) == 10:
            if self.energy < 50:
                self.info_message("ENERGY LOW")
                self.sound.play_sample(cs.SND_BEEP)
                     
 
        if self.mcount == 0 and not self.witchspace:
            self.swat.random_encounter()
 
        self.swat.cool_laser()
        self.swat.time_ecm()
        self.space.update_console()
        
        if self.finish:
            self.current_screen = cs.SCR_GAME_OVER
         
    # ── Commander save/load screens ───────────────────────────────────────────────
    def set_commander_name(self, path):
        fname = self.get_filename(path)
        name = ""
        for ch in fname:
            if not ch.isalnum():
                break
            name += ch.upper()
            if len(name) == 31:
                break
        self.cmdr.name = name
        
    def save_commander_screen(self):
        self.current_screen = cs.SCR_SAVE_CMDR
    
        self.gfx.clear_display()
        self.gfx.display_centre_text(10, "SAVE COMMANDER", 140, cs.GOLD)
        # self.gfx.draw_line(0, 36, 511, 36)
        self.gfx.update_screen()
    
        path = self.cmdr.name + ".nkc"
        okay, path = self.gfx.request_file("Save Commander", path, "nkc")
                
        rv = self.save_commander_file(path)
        if rv:
            self.gfx.display_centre_text(11, "Error Saving Commander!", 140, cs.GOLD)
            return
    
        self.gfx.display_centre_text(11, "Commander Saved.", 140, cs.GOLD)
        self.set_commander_name(path)
    
        self.saved_cmdr = self.cmdr         # shallow copy; use copy.copy() if needed
        self.saved_cmdr.ship_x = self.elite_state.docked_planet.x
        self.saved_cmdr.ship_y = self.elite_state.docked_planet.y
        
    def load_commander_screen(self):
        self.swat.clear_universe()
        self.gfx.clear_display()
        self.gfx.display_centre_text(0, "LOAD COMMANDER", 140, cs.GOLD)
        self.gfx.update_screen()
        self.cmdr = copy(self.commander)
        rv = self.load_commander_file('test')
        if not rv:
            self.saved_cmdr = self.cmdr
            self.gfx.display_centre_text(11, "Error Loading Commander!", 140, cs.GOLD)
            self.gfx.display_centre_text(12, "Press any key to continue.", 140, cs.GOLD)
            self.gfx.update_screen()
            self.restore_saved_commander()
        # self.set_commander_name(path)
        self.saved_cmdr = self.cmdr
        # self.space.update_console()
        
    # ── Intro screens ─────────────────────────────────────────────────────────────
       
    def first_intro_screen(self):
        # This routine always runs through
        self.intro.intro_1()
        key = self.kbd.poll()        
        
        match key:                    
            case 'OK':                
                self.sound.stop_midi()
                self.swat.clear_universe()
                self.load_commander_screen()
                
                self.current_screen = cs.SCR_COMMANDER
                
            case 'Cancel':
                self.current_screen = cs.SCR_INTRO_TWO
                self.swat.clear_universe()
                self.sound.stop_midi()
    
    def second_intro_screen(self):
        # This routine always runs through
        self.intro.intro_2()
        key = self.kbd.poll()
        match key:
            case _ if key is not None:
                self.current_screen = cs.SCR_COMMANDER
                self.swat.clear_universe()
                self.sound.stop_midi()
        
    # ── Game Over sequence ────────────────────────────────────────────────────────
    
    def run_game_over_screen(self):
        self.current_screen = cs.SCR_GAME_OVER
    
        self.flight_speed = 6
        self.flight_roll = 0
        self.flight_climb = 0
        self.swat.clear_universe()
    
        newship = self.swat.add_new_ship(cs.SHIP_COBRA3, 0, 0, -400, None, 0, 0)
        self.universe[newship].flags |= cs.FLG_DEAD
    
        for _ in range(5):
            stype = cs.SHIP_CARGO if (self.rand255() & 1) else cs.SHIP_ALLOY
            ns = self.swat.add_new_ship(stype,
                                        (self.rand255() & 63) - 32,
                                        (self.rand255() & 63) - 32,
                                        -400, None, 0, 0)
            self.universe[ns].rotz = ((self.rand255() * 2) & 255) - 128
            self.universe[ns].rotx = ((self.rand255() * 2) & 255) - 128
            self.universe[ns].velocity = self.rand255() & 15
    
        for _ in range(100):
            self.gfx.clear_display()
            self.stars.update_starfield()
            self.space.update_universe()
            self.gfx.display_centre_text(12, "GAME OVER", 140, cs.GOLD)
            self.gfx.update_screen()
        self.sound.sound_shutdown()
        
    # ── Break pattern (launch / dock / hyperspace transition) ─────────────────────
    
    def display_break_pattern(self):
        # docked is reset by space.launch_player, called by launch()
        # need to decide launching, hyperspacing or docking
        if self.launch_sequence == LAUNCH_SETUP:
            # Transition to/from docked
            # self.gfx.launch_animation()
            self.gfx.clear_display()
                                   
            self.launch_sequence = LAUNCH_CIRCLES
            
        if self.launch_sequence == LAUNCH_CIRCLES:
            if self.launch_timer < self.NUMBER_FRAMES:
                for i in range(self.launch_timer):
                    colour = random.choice(cs.COLOUR_LIST)
                    if self.docked:
                        self.gfx.draw_circle(*cs.FLIGHT_RECT.center(), 30 + i * 15, colour)
                    else:
                        self.gfx.draw_circle(*cs.FLIGHT_RECT.center(), 30 + (self.NUMBER_FRAMES-i) * 15, colour)
                self.launch_timer += 1
            else:
                self.launch_timer = 0
                self.launch_sequence = LAUNCH_COMPLETE
            # self.gfx.update_screen()
        if self.launch_sequence == LAUNCH_COMPLETE:
           # now need to decide where to go next
           #choices are SCR_LAUNCH, SCR_FRONT_VIEW, SCR_CMDR_STATUS
           # could use hyper_ready, docked
           # launch will be docked = false
           # docking is docked = True
           match self.break_mode:
               case 'launch':
                   self.current_screen = cs.SCR_LAUNCH
               case 'docking':
                   self.current_screen = cs.SCR_CMDR_STATUS
               case 'hyperspace':
                   self.current_screen = cs.SCR_FRONT_VIEW
            
           # self.gfx.launch_animation()
           self.launch_sequence = LAUNCH_SETUP
                        
    #  -------Main loop
    def game_loop(self):
      # A loop will be handled   by parent_scene update()
      # This is refactored as a state machine.
      # each state will manage its own keys
      # logger.debug('main')
          
      # logger.debug(self.parent_scene.letter)
      # State Machine one of these will be run on each iteration
      # each will call a screen handler to check for key before calling routine
      # logger.debug(f'memory used {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // (2 ** 20)}MB')
      self.check_change_screen()
      match self.current_screen:
          case cs.SCR_INTRO_ONE:
              self.first_intro_screen()
          case cs.SCR_INTRO_TWO:
              self.second_intro_screen()
          case cs.SCR_COMMANDER | cs.SCR_CMDR_STATUS:
              self.in_dock.display_commander_status()
          case cs.SCR_LAUNCH:
              self.launch()
          case cs.SCR_BREAK_PATTERN:
              self.display_break_pattern()
          case cs.SCR_GALACTIC_CHART | cs.SCR_SHORT_RANGE:
              self.chart_screen()
          case cs.SCR_MARKET_PRICES:
              if self.docked:
                  self.swat.clear_universe()
                  self.market_trade_screen()
              else:
                  self.in_dock.display_market_prices()
          case cs.SCR_PLANET_DATA:
              self.in_dock.display_data_on_planet()
          case cs.SCR_EQUIP_SHIP:
              self.equipment_screen()
          case cs.SCR_INVENTORY:
              self.in_dock.display_inventory()
          case cs.SCR_ESCAPE_POD:
              self.run_escape_sequence()
          case cs.SCR_GAME_OVER:
              self.run_game_over_screen()
          case cs.SCR_QUIT:
              self.quit_screen()
          case _ if self.current_screen in cs.SCR_OUTSIDE:
              self.in_flight_screen()
          case _:
              # shouldn't' get here
              raise RuntimeError(f'unknown state {self.current_screen}')
                  

def loop():
    # This to allow stepping through logic without running gui
        
    from Elite import EliteScene
 
    test_parent_scene = EliteScene()
    test_parent_scene.test = True
    test_parent_scene.setup()
    g = test_parent_scene.mainloop
    #  g.gfx.display_centre_text(20, "Press Fire or Space, Commander.", color="GOLD")
    # g.gfx.text_render()
    # [a, *[b]*3, c] will give [a, b, b, b, c]
    operations = {1: ['OK'], 2: ['OK'], 9: ['Market', 'Down', 'Down'],
                  11: ['Equip', *['Down'] * 6, 'Right'],
                  18: [], 21: ['Status'], 25: ['Data'],
                  30: ['Help'], 35: ['Local Chart'],
                  40: ['Select', '$Zaonce'], 41: [],
                  55: [], 210: ['Galaxy Chart'],
                  70: ['Launch'], 150:['#0.5,0.1'], 170:['#0.00,0.00']} #75: ['Hyper Space'],  80:['Docking'],  1300: [], 150: ['Up']}
         
            
    # cycle through loop, picking up messages at specific iterations
    for i in range(200):
       if i in operations:
          for command in operations[i]:
              g.input_queue.put(command)
       g.game_loop()
       objects = [obj.model
                   for obj in g.universe
                   if hasattr(obj, 'model') and obj.model]
        
       g.parent_scene.renderer.draw(objects, g.parent_scene.camera, g.parent_scene.flight_rect)
       
        
if __name__ == '__main__':
    #import cProfile
    # # loop()
    #logger.debug('finished')
    #cProfile.run('loop()')

    
    import cProfile
    import pstats
    import io
    
    def my_function():
        # Example workload
        loop()
    
    # 1. Create a Profile object
    pr = cProfile.Profile()
    pr.enable()
    
    # 2. Call the function you want to profile
    my_function()
    
    pr.disable()
    
    # 3. Process the results using pstats
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    
    # 4. Filter and print
    # We manually iterate through the stats to check the threshold
    ps.print_stats()
    
    # Print only lines where cumtime > 0
    print("Filtering results for cumtime > 0...\n")
    output = s.getvalue().splitlines()
    
    # The first few lines are headers; we look for the data rows
    for line in output:
        # Basic logic: if the line contains a decimal (time) 
        # and isn't just the header, we check the value.
        try:
            # Split line by whitespace and check the 4th column (cumtime)
            parts = line.split()
            if len(parts) >= 4:
                cumtime = float(parts[3])
                if cumtime > 0:
                    #  ncalls  tottime  percall  cumtime  percall filename:lineno(function)
                    print(f'  {str(parts[0]):^6}  {parts[1]}  {parts[2]}  {parts[3]}  {parts[4]} {parts[5].split("/")[-1]}')
        except (ValueError, IndexError):
            # This handles headers and non-data lines
            if "ncalls" in line or "filename" in line:
                print(line)
