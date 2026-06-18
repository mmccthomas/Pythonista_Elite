
# alg_main.py is  a conversion of alg_main.c by C.J.Pinder
# There are many, many changes, especially to the main loop
# methods such as escape and break are converted to state machines.

# Elite - The New Kind, Python/Pythonista port
# Converted from C by C.J.Pinder. Original (C) I.Bell & D.Braben 1984.

import random
import math
from ui import in_background
import game_engine
from copy import copy
from pathlib import Path
from game_engine import Point2
from stars import Starfield
from graphics import Graphics
from autopilot import Pilot
from trade import TradeManager
from space import Space
from swat import Swat, UnivObject
from elite import EliteState, Commander, GalaxySeed
import elite
from planet import PlanetGenerator
from docked import Docked
from intro import EliteIntro
from missions import MissionManager
import constants as cs
import logging
from vector import unit_vector
cs.setup_logging()
logger = logging.getLogger(__name__)

ESCAPE_SETUP = 1
ESCAPE_FLEE = 2
ESCAPE_RECOVER = 3
ESCAPE_DOCK = 4
LAUNCH_SETUP = 5
LAUNCH_CIRCLES = 6
LAUNCH_COMPLETE = 7


def angle(theta):
   return math.degrees(math.acos(theta))

         
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
    max_speed = 50
    max_roll = 31
    max_climb = 8
    max_fuel = cs.MAX_FUEL
    

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
    

class IntervalTrigger:
    # class used to trigger events at specific intervals
    # easier to use that mcount
    # assume check is called every cycle
    
    def __init__(self, n_seconds):
        self.tick_count = 0
        # Calculate how many 1/60s updates fit into N seconds
        self.ticks_required = n_seconds * 60

    def check(self):
        self.tick_count += 1
        if self.tick_count >= self.ticks_required:
            self.tick_count = 0  # Reset
            return True
        return False


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
       self.instant_dock = cs.INSTANT_DOCK
       self.warp_stars = False
       
       self.present_planet = GalaxySeed(0xAD, 0x38, 0x14, 0x9C, 0x15, 0x1D)
       self.hyperspace_planet = GalaxySeed(0xAD, 0x38, 0x14, 0x9C, 0x15, 0x1D)
       self.current_planet_data = None
       self.galaxy_seed = GalaxySeed(0x5A, 0x4A, 0x02, 0x48, 0xB7, 0x53)

       # Flight Variables
       self.game_over = False
                       
       self.laser_temp = 0
       self.auto_pilot = False
                                      
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
       self.left_message_count = 0
       self.left_message_string = ""
              
       self.cross_x = -1
       self.cross_y = -1
       self.old_cross_x = -1
       self.old_cross_y = -1
       self.cross_timer = 0
       self.escape_sequence = "ESCAPE_SETUP"
       self.launch_sequence = LAUNCH_SETUP
       self.launch_timer = 0
       self.break_mode = 'launch'
       self.NUMBER_FRAMES = 60
       self.find_input = False
       self.find_name = ""
       self.current_name = None
       self.last_found_name = None
       self.on_final_approach = False
       self.tick_count = 0
       self.status_objects = []
       self.path_locations = []
       # individual counters
       self.univ_status = IntervalTrigger(1.0)
       self.alt_temp_status = IntervalTrigger(0.25)
       self.regen_shields = IntervalTrigger(0.125)
       self.energy_status = IntervalTrigger(0.25)
       self.encounter = IntervalTrigger(4.25)
       self.docking_on = IntervalTrigger(0.5)
                          
       # ------ Class instances
       try:  # testing
           self.kbd = parent_scene.kbd
           self.keypad = parent_scene.keypad
           self.msg = parent_scene.msg
           self.msg_right = parent_scene.msg_right
           self.msg_left = parent_scene.msg_left
           self.obj_status = parent_scene.obj_status
           self.hud = parent_scene.hud
           self.camera = parent_scene.camera
           self.gfx = Graphics(parent_scene)
           self.sound = Sound(parent_scene.enable_sound)
           self.renderer = parent_scene.renderer
           self.camera = parent_scene.camera
           
       except AttributeError:
           pass
       cs.setup_logging()
       # Stub universe array
       self.universe = [None] * cs.MAX_UNIV_OBJECTS
       self.ship_count = {}
       self.commander = Commander()
       
       self.trade = TradeManager(self)
       self.stars = Starfield(self)
       self.swat = Swat(self)
       self.universe = self.swat.universe
       self.pilot = Pilot(self)
       self.planet = PlanetGenerator(self)
       self.in_dock = Docked(self)
       self.ship = UnivObject()
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

    # -------- General functions
    @staticmethod
    def set_rand_seed(seed):
        # setting a fixed seed makes game deterministic
        random.seed(seed)
              
    def restore_saved_commander(self):
        self.elite_state.restore_saved_commander(self.planet, self.trade)
        self.current_planet_data = self.elite_state.current_planet_data
                                                            
    def save_commander_file(self, path):
        ok, msg = elite.save_game_json(self.cmdr, path)
        self.info_message(msg)
        return ok
        
    def load_commander_file(self, path):
        path = self.get_filename(path)
        ok, msg = elite.load_game_json(self.cmdr, path)
        if ok:
           self.current_name = path.stem
        self.info_message(msg)
        return ok
        
    @staticmethod
    def get_filename(path):
        dir_path = Path('./files')
        if path is None:
            # Filter for files only (ignoring subdirectories)
            files = [f for f in dir_path.iterdir() if f.is_file() and f.stem not in ('Elite_ships1', 'Elite_ships', 'PLANET_DATA')]
            if not files:
                return None
            # get most recently used file
            # Use max() with the stat().st_mtime as the sorting key
            latest_file = max(files, key=lambda f: f.stat().st_mtime)
            path = latest_file
        return path
        
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
    
        self.set_rand_seed(0)  # was time.time())
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
        self.myship.max_fuel = cs.MAX_FUEL
        
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
        try:
            view_ident = view_[self.current_screen][0]
            self.gfx.display_centre_text(1, view_ident, 120, cs.WHITE)
            laser = view_[self.current_screen][1]
                        
            # make laser sight visible
            self.parent_scene.laser_sight.alpha = int(laser)
            return laser
        except KeyError:
            pass  # called when not outside view
                            
    # ── Auto-dock ─────────────────────────────────────────────────────────────────
    
    def auto_dock(self):
           
        # self.yaw_coupling = 0
        self.ship = self.space.ship
        if self.mcount == 0:
            logger.debug(f' Dist: {self.pilot.distance_to_target:.0f}km')
        self.pilot.auto_pilot_ship_(self.ship)   # modifies ship in-place
        
        # flight speed tracks velocity
        self.flight_speed = min(self.myship.max_speed * (1 + 4 * self.pilot.escape), self.ship.velocity)
        # control joystick
        self.space.joystick_position()
             
    # ── Escape sequence ───────────────────────────────────────────────────────────
    def run_escape_sequence(self):
        # convert to state machine
        self.current_screen = cs.SCR_ESCAPE_POD
        match self.escape_sequence:
            case "ESCAPE_SETUP":
                self.flight_speed = 1
                self.space.flight_roll = 0
                self.space.flight_climb = 0
            
                self.escape_ship = self.swat.add_new_ship(cs.SHIP_COBRA3, 0, 0, 200, None, -127, -127)
                self.universe[self.escape_ship].velocity = 7
                self.sound.play_sample(cs.SND_LAUNCH)
                self.escape_counter = 90
                self.escape_sequence = "ESCAPE_FLEE"
            
            case "ESCAPE_FLEE":
               self.escape_counter -= 1
               if self.escape_counter <= 0:
                  self.escape_sequence = "ESCAPE_RECOVER"
               if self.escape_counter == 100:
                   self.universe[self.escape_ship].flags |= cs.FLG_DEAD
                   self.universe[self.escape_ship].exploding = True
                   self.sound.play_sample(cs.SND_EXPLODE)
               
               self.gfx.clear_display()
               self.stars.update_starfield()
               self.space.update_universe()
       
               self.universe[self.escape_ship].location.x = 0
               self.universe[self.escape_ship].location.y = 0
               self.universe[self.escape_ship].location.z += 2
       
               self.gfx.display_centre_text(
                   cs.NUM_LINES - 1,
                   "Escape pod launched - Ship auto-destruct initiated.",
                   120, cs.WHITE)
                  
               self.gfx.update_screen()
           
            case "ESCAPE_RECOVER":
                if self.space.close_to_station():
                    self.escape_sequence == "ESCAPE_DOCK"
                self.pilot.escape = True
                self.auto_dock()
        
                # if abs(self.flight_roll) < 3 and abs(self.flight_climb) < 3:
                #    for i in range(cs.MAX_UNIV_OBJECTS):
                #        if self.universe[i] is not None and self.universe[i].type != 0:
                #            self.universe[i].location.z -= 1500
        
                self.warp_stars = True
                self.gfx.clear_display()
                self.stars.update_starfield()
                self.space.update_universe()
                
                self.gfx.update_screen()
            
            case "ESCAPE_DOCK":
                self.pilot.escape = False
                self.swat.abandon_ship(self)
        
    # ── Info message ──────────────────────────────────────────────────────────────
    
    def info_message(self, message, color=None):
        self.message_string = message
        self.message_count = 37
    
    def info_message_left(self, message, color=None):
        self.left_message_string = message
        self.left_message_count = 37
       
    # ── Main input handler ────────────────────────────────────────────────────────
    
    def show_universe_status(self):
        """ provide a text readout of all universe objects
        Ranked by
        1. firing enemy
        2. close to sun
        3. close to planet
        2. close enemy
        3. trader
        4. canister
        5. station
        6. any other items in distance order (closest first)
        Display distance and direction using arrows """
        start = 0x21d0
        code = [7, 8, 9, 6, 23, 25]
        
        objects = [obj for obj in self.universe if obj.type != 0]
        textline = []

        def sortkey(obj):
         
            firing_enemy = (obj.flags & cs.FLG_FIRING) > 0
            close_sun = obj.type == cs.SHIP_SUN and obj.distance < 40000
            close_planet = obj.type == cs.SHIP_PLANET and obj.distance < 40000
            close_enemy = ((obj.flags & cs.FLG_BOLD & cs.FLG_ANGRY)
                           or (obj.flags & cs.FLG_ALIEN)
                           and obj.distance < 20000) > 0
            trader = ((obj.flags == 0)
                      and obj.distance < 20000)
            canister = obj.type == cs.SHIP_CARGO
            station = (obj.flags & cs.FLG_STATION) > 0
            
            order = [firing_enemy, close_sun, close_planet, close_enemy, trader, canister, station]
            rank = sum([item * (2**(6-i)) for i, item in enumerate(order)])
            if rank == 0:
               rank = rank - obj.distance / 10000
            return rank
        
        self.status_objects = sorted(objects, key=lambda x: sortkey(x), reverse=True)
        for obj in self.status_objects:
            vec = unit_vector(obj.location - self.ship.location)
            # Horizontal angle (Azimuth)
            azimuth = math.degrees(math.atan2(vec.x, vec.z))
            elevation = math.degrees(math.atan2(vec.y, math.sqrt(vec.x**2 + vec.z**2)))
            if -45 < azimuth < 45:
                n = 0
            elif 45 <= azimuth < 135:
                n = 1
            elif azimuth >= 135 or azimuth < -135:
                n = 2
            elif azimuth >= -135 or azimuth < -45:
                n = 3
            f = f'{chr(start + code[n])}'
            if elevation > 20:
                v = f'{chr(start + code[4])}'
            elif elevation < -20:
                v = f'{chr(start + code[5])}'
            else:
                v = ' '
            
            arrows = f'{v}{f}' if n < 2 else f'{f}{v}'
            textline.append(f'{obj.name:<9} {arrows} {obj.distance/1000:.1f}k')
        self.obj_status.text = '\n'.join(textline)
                                            
    def set_commander_name(self, path):
        return
        fname = self.get_filename(path)
        self.cmdr.name = fname.stem.upper()
                           
    def find_planet(self):
        # Find planet by name.
        # pops up a list dialog populated with sorted planet names
        glx = self.cmdr.galaxy_seed.copy()
        planet_names = []
        for _ in range(256):
            planet_names.append(self.planet.name_planet(glx))
            for _ in range(4):
                glx.waggle()
        planet_names = sorted(planet_names)
        if self.last_found_name:
           planet_names.insert(0, self.last_found_name.upper())
        name = self.gfx.list_files(planet_names)
        if name:
            self.in_dock.find_planet_by_name(name.capitalize())
            self.last_found_name = name
        self.find_route(name)    
        
    def find_route(self, target_name):
        glx = self.cmdr.galaxy_seed.copy()
        path, pathnames = self.planet.get_planet_route(self.present_planet.name, target_name.capitalize(), glx)      
        self.obj_status.text = 'Route:\n' + '\n'.join(pathnames)
        planets = self.planet.get_planet_list(glx)        
        self.path_locations = [planets[p] for p in path]
                           
    def plot_find_path(self):
        if self.path_locations:
           previous = self.path_locations[0]
           sx, sy = self.in_dock._to_screen(Point2(previous.x, previous.y)).as_tuple()
           for i, p in enumerate(self.path_locations[1:]):
               cx,cy =  self.in_dock._to_screen(Point2(p.x,p.y)).as_tuple()                              
               self.gfx.draw_line(sx, sy, cx, cy)
               sx, sy = cx, cy
                                                     
    def launch(self):
        # enable flight keys and launch
        self._change_flight_keys()
        self.space.launch_player()
        
    def check_change_screen(self):
        # Accessible from all screens
        # just changes state
        # emit only Screen keys, designated in Elite.Keyboard, others placed back in queue
        key = self.kbd.poll(mode=1)
        match key:
            case 'Launch':
                self.break_mode = 'launch'
                if self.docked:
                   # logger.debug('clearing universe after launch')
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
            case 'Prices':
                self.current_screen = cs.SCR_MARKET_PRICES
            case 'Trade' | 'Market':
                self.current_screen = cs.SCR_TRADE
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
            case 'Menu':
                self.game_paused = True
                self.menu_screen()
                
        if self.current_screen not in cs.SCR_OUTSIDE:
            self.space.hide_planet()
                
    #  -------Screens
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
                
    def market_prices_screen(self):
        # display prices of hyperspace_planet
        self.check_change_screen()
        self.in_dock.display_hyperspace_planet_prices()
        
    def chart_screen(self):
        # galactic or short range chart
        self.check_change_screen()
        key = self.kbd.poll()
        # if key:
        #    self.parent_scene.msg.text = f'received: {key}'
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
            self.plot_find_path()
        else:
            self.in_dock.display_short_range_chart()            
            self.path_locations = []
                                  
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
                
    def quit_screen(self):
        self.parent_scene.view.close()
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
                    
    @in_background
    def menu_screen(self):
        # Touch-based file save/load/continue/quit etc
        # on entry, load file points to lst used file
        def all_files():
            from os import listdir
            files = [file.split('.')[0] for file in listdir('files') if file not in ('Elite_ships.json', 'PLANET_DATA.TXT')]
            return files
            
        dir_path = Path('./files')
        if self.current_name is None:
            path = self.get_filename(None)
        else:
            path = Path(dir_path / self.current_name).with_suffix('.json')
        
        item_list = ['Resume', f'Save Commander:- {path.stem}',
                     f'Load Commander:- {path.stem}',
                     'Catalogue', 'Delete File',
                     'Add Name',  'Quit']
        action = self.gfx.list_files(item_list, prompt='Action?')
        if action:
           
            match action.split()[0]:
               case 'Save':
                   # save current state
                   ok = self.save_commander_file(path)
                   self.game_paused = False
               case 'Load':
                   # load selected file
                   ok = self.load_commander_file(path)
                   if ok:
                      self.set_commander_name(path)
                   self.game_paused = False
        
               case 'Catalogue':
                   # list all saved files. Selecting one changes current name
                   # and repeats Menu
                   selection = self.gfx.list_files(all_files(), prompt='Selection?')
                   if selection:
                       self.current_name = selection
                       self.input_queue.put('Menu')
                   
               case 'Delete':
                   from os import remove
                   selection = self.gfx.list_files(all_files(), prompt='Selection?')
                   if selection:
                      response = self.gfx.ask_yes_no_(prompt=f'Delete {selection}?')
                      if response == 1:
                          remove(f'files/{selection}.json')
                   self.game_paused = False
               case 'Add':
                   name = self.gfx.enter_text('Enter New Name')
                   if name:
                       self.current_name = name.capitalize()
                       self.input_queue.put('Menu')
                   
               case 'Resume':
                   self.game_paused = False
               case 'Quit':
                   response = self.gfx.ask_yes_no_(prompt='Quit?')
                   if response == 1:
                       self.current_screen = cs.SCR_QUIT
                       self.game_paused = False
                                                                                  
    def first_intro_screen(self):
        # This routine always runs through
        self.intro.intro_1()
        key = self.kbd.poll()
        
        match key:
            case 'OK':
                self.sound.stop_midi()
                self.swat.clear_universe()
                self.load_commander_screen()
                self.space.populate_universe()
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
                
    def mission_screen(self):
        mission_phase = self.missions.check_mission_brief(self.present_planet)
        # logger.debug('')
        key = self.kbd.poll()
        match key:
            case 'OK':
                self.cmdr.mission = mission_phase
                self.current_screen = cs.SCR_COMMANDER
                self.missions.state = 0
                self.space.populate_universe()
                self.space.dock_player()
                self.sound.stop_midi()
                
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
        self.saved_cmdr.ship_x = self.elite_state.present_planet.x
        self.saved_cmdr.ship_y = self.elite_state.present_planet.y
        
    def load_commander_screen(self):
        self.swat.clear_universe()
        self.gfx.clear_display()
        self.gfx.display_centre_text(0, "LOAD COMMANDER", 140, cs.GOLD)
        self.gfx.update_screen()
        self.cmdr = copy(self.commander)
        rv = self.load_commander_file(None)
        if not rv:
            self.saved_cmdr = self.cmdr
            self.gfx.display_centre_text(11, "Error Loading Commander!", 140, cs.GOLD)
            self.gfx.display_centre_text(12, "Press any key to continue.", 140, cs.GOLD)
            self.gfx.update_screen()
            self.restore_saved_commander()
        self.set_commander_name(self.current_name)
        self.present_planet = self.planet.find_planet(self.cmdr.ship_x,
                                                      self.cmdr.ship_y,
                                                      self.cmdr.galaxy_seed)
        self.hyperspace_planet = self.present_planet
        self.galaxy_seed = self.cmdr.galaxy_seed
        self.saved_cmdr = self.cmdr
        # self.space.update_console()
    
    def run_game_over_screen(self):
        key = self.kbd.poll()
        match key:
            case 'OK':
                self.sound.stop_midi()
                self.swat.clear_universe()
                self.restore_saved_commander()
                self.space.populate_universe()
                self.current_screen = cs.SCR_COMMANDER
                self.game_over = False
                self.space.dock_player()
                return
                
        self.gfx.clear_display()
        try:
            self.swat.planet_image.planet.alpha = 0
            self.swat.sun_image.planet.alpha = 0
        except AttributeError:
            pass
        
        self.gfx.display_centre_text(cs.NUM_LINES-1, "Press OK to load backup", color=cs.GOLD)
        self.current_screen = cs.SCR_GAME_OVER
    
        self.flight_speed = 1
        self.flight_roll = 0
        self.flight_climb = 0
        self.swat.clear_universe()
    
        newship = self.swat.add_new_ship(cs.SHIP_COBRA3, 0, 0, -1000, None, 0, 0)
        self.universe[newship].flags |= cs.FLG_DEAD
        
        stype = cs.SHIP_CARGO if (self.rand255() & 1) else cs.SHIP_ALLOY
        ns = self.swat.add_new_ship(stype,
                                    (self.rand255() & 63) - 32,
                                    (self.rand255() & 63) - 32,
                                    -400, None, 0, 0)
        self.universe[ns].rotz = ((self.rand255() * 2) & 255) - 128
        self.universe[ns].rotx = ((self.rand255() * 2) & 255) - 128
        self.universe[ns].velocity = self.rand255() & 15
        
        self.stars.update_starfield()
        self.space.update_universe()
        self.gfx.display_centre_text(12, "GAME OVER", 140, cs.GOLD)
        self.gfx.display_centre_text(14, self.space.end_reason, color=cs.GOLD)
        self.gfx.update_screen()
        self.sound.sound_shutdown()
        self.gfx.text_render()
        
    # --------In Flight Screen
    def in_flight_screen(self):
        # This is the flight loop
        self.in_flight_keys()
        
        self.gfx.update_screen()
         
        if self.game_paused:
            return
        
        if self.message_count > 0:
            self.message_count -= 1
            
        if self.parent_scene.t > (self.space.jump_start + cs.JUMP_ANIMATION):
           self.stars.speedup = 1
            
        if self.space.hyper_ready:
            self.space.display_hyper_status()
            # if (self.mcount & 3) == 0:
            self.space.countdown_hyperspace()
        
        if self.univ_status.check() and cs.UNIVERSE_STATUS:
            self.show_universe_status()
                
        if self.alt_temp_status.check():
            self.space.update_altitude()
            self.space.update_cabin_temp()
            
        # Clear view for space screens
        self.gfx.clear_display()
        self.stars.update_starfield()
 
        if self.pilot.auto_pilot_active:
            self.auto_dock()
        else:
            if not self.space.hyper_ready and self.space.safe_mode and cs.FLIGHT_DIRECTOR:
                self.pilot.target_loc = self.pilot.ip_waypoint()
                self.pilot.draw_target()
 
        self.space.update_universe()
        
        self.draw_laser_sights()
        
        if self.draw_lasers:
            self.parent_scene.laser_lines.alpha = 1
            self.draw_lasers -= 1
        else:
            self.parent_scene.laser_lines.alpha = 0
        if self.witchspace:
            self.gfx.display_text(41, 0, 'Witch Space !', 120, cs.RED)
        else:
            self.gfx.display_text(41, 0, self.present_planet.name, 120, cs.GOLD)
            
        # clear left message every second
        if self.mcount & 63 == 0:
           self.msg_left.text = ''
           
        if self.message_count > 0:
            self.gfx.display_centre_text(cs.NUM_LINES-1, self.message_string, 120, cs.WHITE)
            
        if self.left_message_count > 0:
            self.gfx.display_text(1, cs.NUM_LINES, self.left_message_string, 120, cs.WHITE)
                   
        self.mcount = (self.mcount - 1) & 255
       
        if self.regen_shields.check():
            self.space.regenerate_shields()
 
        if self.energy_status.check():
            if self.energy < 50:
                self.info_message("ENERGY LOW")
                self.sound.play_sample(cs.SND_BEEP)
 
        if self.encounter.check() and not self.witchspace:
            self.swat.random_encounter()
 
        self.swat.cool_laser()
        self.swat.time_ecm()
        self.space.update_console()
        
        if self.game_over:
            self.current_screen = cs.SCR_GAME_OVER
                               
    def in_flight_keys(self):
        self.check_change_screen()
        key = self.kbd.poll()
        
        match key:
            case None:
                self.space.roll_pitch_control(None)
            case key if key.startswith('>'):
                self.space.roll_pitch_control(key)
            case key if key.startswith('<'):
                self.space.speed_control(key)
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
                    
            case 'Cancel Docking':
                self.pilot.disengage_auto_pilot()
                
            case 'Cancel Target':
                self.pilot.disengage_auto_pilot()
                self.keypad.key_change(key_name='Cancel Target',
                                       name='Docking', color='lightgreen')
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
                if self.flight_speed > 0:
                    self.flight_speed -= 1
            case 'Up':
                self.space.increase_flight_climb()
                self.climbing = True
            case 'Down':
                self.space.decrease_flight_climb()
                self.climbing = True
            case 'Left':
                self.space.increase_flight_roll()
                self.rolling = True
            case 'Right':
                self.space.decrease_flight_roll()
                self.rolling = True
            case 'Bomb':
                if self.cmdr.energy_bomb:
                    self.detonate_bomb = True
                    self.cmdr.energy_bomb = False
                    self.keypad.key_change('Bomb', enabled=False)
            case 'Escape':
                if self.cmdr.escape_pod and not self.witchspace:
                    self.current_screen = cs.SCR_ESCAPE_POD
            case 'Cancel Escape':
                self.pilot.disengage_auto_pilot()
            case 'Compass Planet':
                self.space.set_compass('sun')
                self.keypad.key_change('Compass Planet', name='Compass Sun')
            case 'Compass Sun':
                self.space.set_compass('planet')
                self.keypad.key_change('Compass Sun', name='Compass Planet')
            # testing keys
            case 'To Sun' | 'To Planet' | 'To Station':
                self.space.jump_direct(key)
            case key if key.startswith('->'):
                # only allow target locking if docking computer fitted
                if self.cmdr.docking_computer:
                    self.keypad.key_change(key_name='Docking',
                                           name='Cancel Target', color=cs.ORANGE)
                    logger.debug(key)
                    self.swat.target_object(key)
                 
    def _change_flight_keys(self, enable=True):
        # enable normal flight keys plus others where purchased
        for keyname in ['Jump', 'Missile', 'Target',
                        'Look Port', 'Hyper Space',
                        'Look Stbd', 'Look Fwd',
                        'Look Aft', 'Fire Laser', 'Compass Planet']:
            self.keypad.key_change(keyname, enabled=enable)
        for keyname in ['To Sun', 'To Planet', 'To Station']:
            self.keypad.key_change(keyname, enabled=cs.TELEPORT and enable)
            
        self.keypad.key_change('Cancel Docking', name='Docking')
        self.keypad.key_change('Compass Sun', name='Compass Planet')
        self.keypad.key_change('Equip', enabled=not enable)
        self.keypad.key_change('Trade', enabled=not enable)
        if enable:
            self.keypad.key_change('Market', name='Target Prices')
        else:
            self.keypad.key_change('Target Prices', name='Market')
                    
        self.additional_items = {'ecm': 'ECM',
                                 'energy_bomb': 'Bomb',
                                 'docking_computer': 'Docking',
                                 'galactic_hyperdrive': 'New Galaxy',
                                 'escape_pod': 'Escape'}
        for k, v in self.additional_items.items():
            state = getattr(self.cmdr, k)
            self.keypad.key_change(v, enabled=(state and enable))
       
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
           # choices are SCR_LAUNCH, SCR_FRONT_VIEW, SCR_CMDR_STATUS
           # could use hyper_ready, docked
           # launch will be docked = false
           # docking is docked = True
           logger.debug(f'finished break {self.break_mode}')
           match self.break_mode:
               case 'launch':
                   self.current_screen = cs.SCR_LAUNCH
               case 'docking':
                   self.current_screen = cs.SCR_MISSION
               case 'hyperspace':
                   self.current_screen = cs.SCR_FRONT_VIEW
               case _:
                   self.current_screen = cs.SCR_MISSION
                   
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
          case _ if self.current_screen in cs.SCR_OUTSIDE:
              self.in_flight_screen()
          case cs.SCR_INTRO_ONE:
              self.first_intro_screen()
          case cs.SCR_INTRO_TWO:
              self.second_intro_screen()
          case cs.SCR_MISSION:
              self.mission_screen()
          case cs.SCR_COMMANDER | cs.SCR_CMDR_STATUS:
              self.in_dock.display_commander_status()
          case cs.SCR_LAUNCH:
              self.launch()
          case cs.SCR_BREAK_PATTERN:
              self.display_break_pattern()
          case cs.SCR_GALACTIC_CHART | cs.SCR_SHORT_RANGE:
              self.chart_screen()
          case cs.SCR_MARKET_PRICES:
              self.market_prices_screen()
          case cs.SCR_TRADE:
              self.market_trade_screen()
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
          
          case _:
              # shouldn't' get here
              raise RuntimeError(f'unknown state {self.current_screen}')

                                    
# ----------Test Loop
def loop():
    # This to allow stepping through logic without running gui
        
    from Elite import EliteScene
 
    test_parent_scene = EliteScene()
    test_parent_scene.test = True
    test_parent_scene.setup()
    g = test_parent_scene.mainloop
    current_glx = GalaxySeed(0xAD, 0x38, 0x14, 0x9c, 0x15, 0x1d)
    planets = g.planet.get_closest_planets(GalaxySeed(), current_glx, max_distance=None)
    for planet in planets:
       sm = g.trade.generate_stock_market(planet.glx.econ)
       logger.debug(f'{sm[7]["current_quantity"]}')
    #  g.gfx.display_centre_text(20, "Press Fire or Space, Commander.", color="GOLD")
    # g.gfx.text_render()
    # [a, *[b]*3, c] will give [a, b, b, b, c]
    operations = {1: ['OK'], 8: ['OK'], 35: ['Local Chart'],
                  40: ['Select', '$Leesti'],
                  
                  70: ['Launch'],
                  150: ['To Station'],
                  # 152: [*['Up']*811],
                  # 155: ['Docking'],
                  # 150: ['Hyper Space'],
                  
                  # 140: ['Status'],
                  165: [],  # complete
                  267: [],
                  
                  963: ['Docking'],
                  1002: [],
                  1079: [],
                  # 142: ['Launch'],
                  # 340: [],  # finished align
                  # 555: ['->974,957'],
                  # 560: ['Cancel Docking'],
                  # 7359: [], # station spawned
                  # 7500: ['Docking']
                  }
    # cycle through loop, picking up messages at specific iterations
    for i in range(200):
       logger.debug(i)
       if i in operations:
          if i == 1:
              pass
          for command in operations[i]:
              g.input_queue.put(command)
          print(i, g.present_planet, command)
       # logger.debug(f'{g.trade.stock_market=}')
       univ = [obj.type for obj in g.universe]
       if univ[3] != 0 and ((3 ^ g.mcount) & 7) == 0:
           logger.debug(f'{g.swat.ship_names[univ[3]]}')
           logger.debug(f'dist:{g.universe[3].distance:.0f} dir:{angle(g.universe[3].direction):.0f}')
           logger.debug(f'fshield:{g.front_shield:.0f} ashield:{g.aft_shield} energy:{g.energy}')
       
       g.game_loop()
       
       objects = [obj.model
                  for obj in g.universe
                  if hasattr(obj, 'model') and obj.model]
        
       g.parent_scene.renderer.draw(objects, g.parent_scene.camera, cs.FLIGHT_RECT)
       
        
if __name__ == '__main__':
    import cProfile
    loop()
    # logger.debug('finished')
    #
    # cProfile.run('loop()')
    
    import pstats
    import io
    
    def my_function():
        # Example workload
        # loop()
        pass
    
    # 1. Create a Profile object
    pr = cProfile.Profile()
    pr.enable()
    
    # 2. Call the function you want to profile
    my_function()
    
    pr.disable()
    
    # 3. Process the results using pstats
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('ncall')
    
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
                    print(f'  {str(parts[0]):^6}  {parts[1]}    {parts[2]}    {parts[3]}    {parts[4]}   {parts[5].split("/")[-1]}')
        except (ValueError, IndexError):
            # This handles headers and non-data lines
            if "ncalls" in line or "filename" in line:
                print(line)
   
  

