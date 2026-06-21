# A rendering of 2 introction screens:
# 1. A rotating Cobra with option to load last save game
# 2. A parade of ships that take turns to present themselves
# These have mostly been created using AI and are not original code

from vector import set_init_matrix
import constants as cs
import math
import logging
logger = logging.getLogger(__name__)

ELITE_TEXT = "./elitetx3.png"
# Constants for the carousel
CAROUSEL_RADIUS = 800      # radius of the circle of ships
CAROUSEL_Y = 200             # y centre of the circle
CAROUSEL_X = 0             # x centre of the circle
CAROUSEL_Z = 3000          # z depth for all ships in circle
INCLINATION_ANGLE = -math.pi/4
CENTRE_IDX = 8             # index 8 (9th element) is the "hero" ship
UNIVERSE_SIZE = 17         # max ships in universe list
SHIP_RANGE = list(range(9, 34))  # ships 9..33, cycles

# States
ST_FILLING = 0   # adding ships one per frame until universe is full
ST_FWD = 1   # hero ship moves forward (z decreases)
ST_BACK = 2   # hero ship returns to original z
ST_ROTATE = 3   # shuffle universe list, bring in next ship
ST_SETUP = 4   # Initialise and setup
ST_UPDATE = 5  # run rotating ship for intro1

FWD_LIMIT = 300          # how close the hero ship comes
FWD_SPEED = 30           # z units per frame toward camera
BACK_SPEED = 30           # z units per frame back to rest
ROTATE_FRAMES = 40          # frames to animate the rotation shift

SHIP_TYPE = {
    "PLANET":  (-1, ''), "SUN":  (-2,  ''), "None":  (0, ''),
    "MISSILE":  (1, ''), "CORIOLIS":  (2, 'STATION'), "ESCAPE_POD":  (3, ''),
    "PLATE": (4, ''), "CANISTER":  (5, 'Debris'), "BOULDER":  (6, 'Debris'),
    "ASTEROID":  (7, 'Debris'), "SPLINTER":  (8, 'Debris'), 
    "SHUTTLE":  (9, 'Innocent Trader'), "TRANSPORTER": (10, 'Innocent Trader'), 
    "COBRA_MK_3":  (11, 'Innocent Trader'), "PYTHON":  (12, 'Innocent Trader'),
    "BOA": (13, 'Innocent Trader'), "ANACONDA":  (14, 'Innocent Trader'),
    "ROCK_HERMIT": (15, 'Innocent Trader'), 
    "VIPER":  (16, 'Police'), 
    "SIDEWINDER":  (17, 'Pirate'), "MAMBA":  (18, 'Pirate'), "KRAIT":  (19, 'Pirate'), 
    "ADDER":  (20, 'Pirate'), "GECKO":  (21, 'Pirate'), "COBRA_MK_1":  (22, 'Pirate'),
    "WORM":  (23, 'Hostile Trader'), "COBRA_MK_3_P":  (24, 'Pirate'), "ASP_MK_2":  (25, 'Pirate'),
    "PYTHON_P":  (26, 'Pirate'), "FER_DE_LANCE":  (27, 'Bounty Hunter'), "MORAY":  (28, 'Pirate'), 
    "THARGOID":  (29, 'Hostile Alien'), "THARGON":  (30, 'Hostile Alien'),
    "CONSTRICTOR":  (31, 'Hostile'), "COUGAR":  (32, 'Innocent Trader'), 
    "DODO":  (33, 'Station'),  "STATIONV":  (34, 'Station'),
}

class EliteIntro:
    def __init__(self, gs):
        self.gs = gs
        self.universe = gs.universe
        self.swat = gs.swat
        self.gfx = gs.gfx

        self.ship_no = 0
        self.show_time = 0
        self.direction = 100
        
        self.swat.clear_universe()
        
        self.car_state = ST_SETUP
        
        # Minimum distances to prevent ships from clipping through the camera
        # Based on the original min_dist array
        self.min_distances = [
            0, 200, 800, 200, 200, 200, 300, 384, 200,
            200, 200, 420, 900, 500, 800, 384, 384,
            384, 384, 384, 200, 384, 384, 384, 0,
            384, 0, 384, 384, 700, 384, 0, 0, 900
        ]
        
        self.intro_matrix = set_init_matrix()
        
    # -------Intro 1
    def intro_1(self):
        """Sets up the rolling Cobra MkIII screen.
        State machine handles setup and run states
        Entry assumes universe has been ckeared previously"""
        
        if self.swat.universe[0].type == 0:
            self.car_state = ST_SETUP
            
        if self.car_state == ST_SETUP:
            self.gs.sound.play_midi(cs.SND_ELITE_THEME, True)
            
            # Add Cobra MkIII far away (z=4500)
            self.swat.add_new_ship(cs.SHIP_COBRA3,  0, 300, 4500, None, -127, -127)
            
            # only need to set these once for Pythonista
            # Draw the logo and text
            self.gfx.draw_sprite(ELITE_TEXT, x=-1, y=10)  # -1 centers
            self.gfx.clear_display()
            self.gfx.display_centre_text(20, "Original Game (C) I.Bell & D.Braben.", color=cs.WHITE)
            self.gfx.display_centre_text(21, "Re-engineered by C.J.Pinder.", color=cs.WHITE)
            self.gfx.display_centre_text(22, "Converted to Pythonista by C.M.Thomas", color=cs.WHITE)
            self.gfx.display_centre_text(23, "Load Saved Commander (Ok)?", color=cs.GOLD)
            self.gfx.text_render()
            self.car_state = ST_FWD
            
        if self.car_state == ST_FWD:
            """Moves the Cobra closer and displays credits."""
            # Move ship toward camera
            current_obj = self.universe[0]
            current_obj.location.z -= 50
            self.swat.update_model(current_obj)
            if current_obj.location.z <= 384:
                current_obj.location.z = 384
                self.car_state = ST_ROTATE
                
        if self.car_state == ST_ROTATE:
            # Set a constant roll for the intro effect
            current_obj = self.universe[0]
            current_obj.rotx += 0.5  # flight_yaw = 0.5 unit per cycle
            current_obj.rotz += 0.5  # flight_roll = 0.5
            
            self.swat.update_model(current_obj)
                    
    # -------Intro 2
    def intro_2(self):
        """Runs the Ship Parade carousel.
        State machine handles setup and run states
        Entry assumes universe has been ckeared previously"""
        
        if self.swat.universe[0].type == 0:
            self.car_state = ST_SETUP
           
        if self.car_state == ST_SETUP:
            self.gfx.clear_display()
            self.gfx.draw_sprite(ELITE_TEXT, x=-1, y=10)
            self.gfx.display_centre_text(29, "Press Select, Commander.", color=cs.GOLD)
            self.gfx.text_render()
        
            # Carousel state
            self.intro_matrix = set_init_matrix()
            self.car_ship_pool = [i for i in range(11, 32) if i != 0]   # 9..32
            self.car_pool_idx = 0  # next ship to pull from pool
            self.car_state = ST_FILLING
            self.car_fill_idx = 0  # how many ships placed so far
            self.car_hero_z = CAROUSEL_Z  # current z of hero ship
            self.car_rot_frame = 0  # frame counter for ST_ROTATE
        
        # ST_FILLING : add one ship per frame until universe holds UNIVERSE_SIZE
        if self.car_state == ST_FILLING:
            if self.car_fill_idx == 0:
                # First call: initialise the ship-number list
                self.car_ship_numbers = []
    
            self.car_ship_numbers.append(self._car_pool_next())
            self.car_fill_idx += 1
    
            # Rebuild (or build incrementally) universe each frame
            self._car_rebuild_universe(self.car_ship_numbers)
    
            if self.car_fill_idx >= UNIVERSE_SIZE:
                # Universe is full — update the hero's true z for FWD animation
                self.car_hero_z = CAROUSEL_Z
                self._car_update_name()
                self.car_state = ST_FWD
            return
    
        # Update every ship's model each frame so they rotate on the spot
        try:
            for obj in self.universe:
                obj.rotx += 0.1
                self.swat.update_model(obj)
        except AttributeError:
            # no models set up yet
            pass
    
        # ST_FWD : hero ship flies toward camera
        if self.car_state == ST_FWD:
            self.car_hero_z -= FWD_SPEED
            hero = self._car_hero()
            hero.location.z = self.car_hero_z
            self.swat.update_model(hero)
    
            if self.car_hero_z <= FWD_LIMIT:
                self.car_state = ST_BACK
            return
            
        # ST_BACK : hero ship returns to its circle z
        if self.car_state == ST_BACK:
            self.car_hero_z += BACK_SPEED
            hero = self._car_hero()
            hero.location.z = self.car_hero_z
            self.swat.update_model(hero)
    
            if self.car_hero_z >= CAROUSEL_Z:
                self.car_hero_z = CAROUSEL_Z
                hero.location.z = CAROUSEL_Z
                self.car_rot_frame = 0
                self.car_state = ST_ROTATE
            return
            
        # ST_ROTATE : shift ship list by one, introduce next ship from pool
        if self.car_state == ST_ROTATE:
            self.car_rot_frame += 1
    
            if self.car_rot_frame >= ROTATE_FRAMES:
                # Shuffle: drop element 0, append next ship from pool
                self.car_ship_numbers.pop(0)
                self.car_ship_numbers.append(self._car_pool_next())
    
                self._car_rebuild_universe(self.car_ship_numbers)
                self.car_hero_z = CAROUSEL_Z
                self._car_update_name()
                self.car_state = ST_FWD
            return
            
    @staticmethod
    def _carousel_positions(n, radius, cx, cy, cz):
        """Return (x, y, z) for each of n ships arranged on a circle in the XZ plane.
        Viewed side-on: ships spread left/right (x) and near/far (z).
        Index CENTRE_IDX sits at the front-centre, closest to camera."""

        positions = []
        for i in range(n):
            # CENTRE_IDX maps to angle=0 => front of circle (minimum z)
            angle = -math.pi/2 + 2 * math.pi * (i - CENTRE_IDX) / n
            x = int(cx + radius * math.cos(angle))
            y = int(cy + 0.25 * radius * math.sin(angle))
            z = int(cz - radius * math.sin(angle))   # subtract so index 8 is nearest
            positions.append((x, y, z))
        return positions

    def _car_pool_next(self):
        """Return next ship number from the cycling pool."""
        ship_no = self.car_ship_pool[self.car_pool_idx % len(self.car_ship_pool)]
        self.car_pool_idx += 1
        return ship_no
        
    def _car_rebuild_universe(self, ship_numbers):
        """Rebuild universe with the given list of ship numbers at circle positions."""
        self.swat.clear_universe()
        positions = self._carousel_positions(
            len(ship_numbers), CAROUSEL_RADIUS, CAROUSEL_X, CAROUSEL_Y, CAROUSEL_Z
        )
        for i, ship_no in enumerate(ship_numbers):
            x, y, z = positions[i]
            self.swat.add_new_ship(ship_no, x, y, z, None, -127, -127)
        
    def _car_hero(self):
        """Return the universe object that is the hero (centre) ship."""
        return self.universe[CENTRE_IDX]
    
    def _car_update_name(self):
        """Redraw the HUD with the current hero ship name."""
        hero_no = self.car_ship_numbers[CENTRE_IDX]
        ship_name = {v: k for k, v in cs.SHIP_DICT.items()}.get(hero_no, str(hero_no))
        self.gfx.clear_display()
        self.gfx.draw_sprite(ELITE_TEXT, x=-1, y=10)
        self.gfx.display_centre_text(28, f'{ship_name} ({SHIP_TYPE[ship_name][1]})' , color="WHITE")
        self.gfx.display_centre_text(29, "Press OK  or Cancel, Commander.", color=cs.GOLD)
        self.gfx.text_render()
