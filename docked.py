import math
from dataclasses import dataclass
import constants as cs
from game_engine import Point2
from constants import PULSE_LASER, BEAM_LASER, MILITARY_LASER, MINING_LASER
import logging
logger = logging.getLogger(__name__)

# Economy and government type strings
ECONOMY_TYPES = [
    "Rich Industrial", "Average Industrial", "Poor Industrial",
    "Mainly Industrial", "Mainly Agricultural", "Rich Agricultural",
    "Average Agricultural", "Poor Agricultural"
]

GOVERNMENT_TYPES = [
    "Anarchy", "Feudal", "Multi-Government", "Dictatorship",
    "Communist", "Confederacy", "Democracy", "Corporate State"
]

LASER_NAMES = ["Pulse", "Beam", "Military", "Mining", "Custom"]


UNIT_NAMES = ["t", "kg", "g"]

TONNES, KILOGRAMS, GRAMS = 0, 1, 2

# Rank thresholds
RATINGS = [
    (0x0000, "Harmless"),
    (0x0008, "Mostly Harmless"),
    (0x0010, "Poor"),
    (0x0020, "Average"),
    (0x0040, "Above Average"),
    (0x0080, "Competent"),
    (0x0200, "Dangerous"),
    (0x0A00, "Deadly"),
    (0x1900, "---- E L I T E ---"),
]

# Equipment type enum values
(EQ_FUEL, EQ_MISSILE, EQ_CARGO_BAY, EQ_ECM, EQ_FUEL_SCOOPS,
 EQ_ESCAPE_POD, EQ_ENERGY_BOMB, EQ_ENERGY_UNIT, EQ_DOCK_COMP,
 EQ_GAL_DRIVE, EQ_PULSE_LASER, EQ_FRONT_PULSE, EQ_REAR_PULSE,
 EQ_LEFT_PULSE, EQ_RIGHT_PULSE, EQ_BEAM_LASER, EQ_FRONT_BEAM,
 EQ_REAR_BEAM, EQ_LEFT_BEAM, EQ_RIGHT_BEAM, EQ_MINING_LASER,
 EQ_FRONT_MINING, EQ_REAR_MINING, EQ_LEFT_MINING, EQ_RIGHT_MINING,
 EQ_MILITARY_LASER, EQ_FRONT_MILITARY, EQ_REAR_MILITARY,
 EQ_LEFT_MILITARY, EQ_RIGHT_MILITARY) = range(30)

Y_INC = 16
X_INC = 16
EQUIP_START_X = 2


@dataclass
class EquipItem:
    canbuy: int = 0
    y:      int = 0
    show:   int = 1
    level:  int = 1
    price:  int = 0
    name:   str = ""
    type:   int = 0


def _make_equip_stock():
    """Return a fresh list of the 34 equipment items."""
    return [
        EquipItem(0, 0, 1,  1,     2, " Fuel",                EQ_FUEL),
        EquipItem(0, 0, 1,  1,   300, " Missile",             EQ_MISSILE),
        EquipItem(0, 0, 1,  1,  4000, " Large Cargo Bay",     EQ_CARGO_BAY),
        EquipItem(0, 0, 1,  2,  6000, " E.C.M. System",       EQ_ECM),
        EquipItem(0, 0, 1,  5,  5250, " Fuel Scoops",         EQ_FUEL_SCOOPS),
        EquipItem(0, 0, 1,  6, 10000, " Escape Pod",          EQ_ESCAPE_POD),
        EquipItem(0, 0, 1,  7,  9000, " Energy Bomb",         EQ_ENERGY_BOMB),
        EquipItem(0, 0, 1,  8, 15000, " Extra Energy Unit",   EQ_ENERGY_UNIT),
        EquipItem(0, 0, 1,  9, 15000, " Docking Computers",   EQ_DOCK_COMP),
        EquipItem(0, 0, 1, 10, 50000, " Galactic Hyperdrive", EQ_GAL_DRIVE),
        EquipItem(0, 0, 1,  3,  4000, "+Pulse Laser",         EQ_PULSE_LASER),
        EquipItem(0, 0, 0,  3,     0, "-Pulse Laser",         EQ_PULSE_LASER),
        EquipItem(0, 0, 0,  3,  4000, ">Front",               EQ_FRONT_PULSE),
        EquipItem(0, 0, 0,  3,  4000, ">Rear",                EQ_REAR_PULSE),
        EquipItem(0, 0, 0,  3,  4000, ">Left",                EQ_LEFT_PULSE),
        EquipItem(0, 0, 0,  3,  4000, ">Right",               EQ_RIGHT_PULSE),
        EquipItem(0, 0, 1,  4, 10000, "+Beam Laser",          EQ_BEAM_LASER),
        EquipItem(0, 0, 0,  4,     0, "-Beam Laser",          EQ_BEAM_LASER),
        EquipItem(0, 0, 0,  4, 10000, ">Front",               EQ_FRONT_BEAM),
        EquipItem(0, 0, 0,  4, 10000, ">Rear",                EQ_REAR_BEAM),
        EquipItem(0, 0, 0,  4, 10000, ">Left",                EQ_LEFT_BEAM),
        EquipItem(0, 0, 0,  4, 10000, ">Right",               EQ_RIGHT_BEAM),
        EquipItem(0, 0, 1, 10,  8000, "+Mining Laser",        EQ_MINING_LASER),
        EquipItem(0, 0, 0, 10,     0, "-Mining Laser",        EQ_MINING_LASER),
        EquipItem(0, 0, 0, 10,  8000, ">Front",               EQ_FRONT_MINING),
        EquipItem(0, 0, 0, 10,  8000, ">Rear",                EQ_REAR_MINING),
        EquipItem(0, 0, 0, 10,  8000, ">Left",                EQ_LEFT_MINING),
        EquipItem(0, 0, 0, 10,  8000, ">Right",               EQ_RIGHT_MINING),
        EquipItem(0, 0, 1, 10, 60000, "+Military Laser",      EQ_MILITARY_LASER),
        EquipItem(0, 0, 0, 10,     0, "-Military Laser",      EQ_MILITARY_LASER),
        EquipItem(0, 0, 0, 10, 60000, ">Front",               EQ_FRONT_MILITARY),
        EquipItem(0, 0, 0, 10, 60000, ">Rear",                EQ_REAR_MILITARY),
        EquipItem(0, 0, 0, 10, 60000, ">Left",                EQ_LEFT_MILITARY),
        EquipItem(0, 0, 0, 10, 60000, ">Right",               EQ_RIGHT_MILITARY),
    ]


class Docked:
    """Screens and logic from the original planet.c / charts module."""
    def __init__(self, game_state):
        self.gfx = game_state.gfx
        
        self.gs = game_state    # docked, witchspace, energy, universe...
        self.SCALE = min(cs.FLIGHT_RECT.width, cs.FLIGHT_RECT.height) / 255
        self.scale = Point2(cs.GFX_SCALEX, cs.GFX_SCALEY)
        self.cross = Point2(0, 0)
        self.old_cross = Point2(-1, -1)
        self.cross_timer = 0
           
        self.hilite_market = -1
        self.hilite_equip = -1
        self.START_ROW = 5
        self.EQUIP_START_ROW = 3
        self.equip_stock = _make_equip_stock()
        self.item_count = 1
        self.incoming_message = ''
        # self.galactic_frame = Rect()
    
    # Fuel circle / cross
    
    def draw_fuel_limit_circle(self, c: Point2):
     
        gfx = self.gfx
        # TODO fix this
        # scale local chart to fuel limit.
        # fuel limit circle should fill screen
        # adjust zoom_scale to fit
        
        # gfx.set_clip_region(cs.FLIGHT_RECT.x, cs.FLIGHT_RECT.y, cs.FLIGHT_RECT.w, cs.FLIGHT_RECT.h - cs.FLIGHT_RECT.y)
        radius = 1.9 * self.gs.cmdr.fuel / 10 * self.scale * self.zoom_scale
        
        # logger.debug(f'{radius=} {self.gs.cmdr.fuel=}')
        cross_size = 1 * self.zoom_scale * self.SCALE
        cx, cy = c.as_tuple()
        gfx.draw_circle(cx, cy, radius.x, cs.GREEN)
        gfx.draw_line(cx, cy - cross_size, cx, cy + cross_size)
        gfx.draw_line(cx - cross_size, cy, cx + cross_size, cy)
        return radius
    
    # Distance helpers

    @staticmethod
    def calc_distance_to_planet(from_planet, to_planet):
        dx = abs(to_planet.x - from_planet.x)
        dy = abs(to_planet.y - from_planet.y)
        light_years = int(math.sqrt(dx**2 + dy**2)) * 4
        return light_years

    def show_distance(self, from_planet, to_planet):
        light_years = self.calc_distance_to_planet(from_planet, to_planet)
        text = f" {light_years // 10:2d}.{light_years % 10} Light Years "
        return text
    
    # Cross / hyperspace target

    def show_distance_to_planet(self):
        gfx = self.gfx
        gs = self.gs
        p = self.cross.round()
        
        # ,without any change px, py shoukd be   0x9c  0x38 (156, 56)
        # scene.rect(0,0,0,0)([0xAD38, 0x149C, 0x151D], 'Lave'),
        planet = gs.planet.find_planet(*p.as_tuple(), gs.galaxy_seed)
        # logger.debug(f'{px=} {py=} {gs.hyperspace_planet}')
        planet_name = gs.planet.name_planet(planet)
        gs.hyperspace_planet = planet
        gfx.display_text(3, cs.NUM_LINES - 1, f"{planet_name:<8} ({planet.x:.0f},{planet.y:.0f})")
        dist_text = self.show_distance(gs.present_planet, gs.hyperspace_planet)
        self.gfx.display_text(23, cs.NUM_LINES - 1, dist_text)

    def _next_planet(self, glx):
        for _ in range(4):
            glx.waggle()
                
    def find_planet_by_name(self, find_name):
        gfx = self.gfx
        gs = self.gs
        glx = self.gs.cmdr.galaxy_seed.copy()

        for _ in range(256):
            planet_name = gs.planet.name_planet(glx)
            if planet_name == find_name:
                gs.hyperspace_planet = glx
                # gfx.clear_text_area()
                # gfx.display_text(3, cs.NUM_LINES - 1, f"{planet_name:<8} ({glx.x:.0f}, {glx.y:.0f})")
                # self.show_distance(356, gs.present_planet, gs.hyperspace_planet)
                self._update_cross_for_hyperspace()
                return
            self._next_planet(glx)
                
        # gfx.clear_text_area()
        gfx.display_text(0, 21, "Unknown Planet")
   
    # conversion planet_space to/from flight_screen_space
    # offset and baseline are defined in short-range and galactic chart
    def _to_screen(self, point: Point2) -> Point2:
        coord = (point - self.baseline) * (self.zoom_scale * self.scale) + self.offset
        return coord
      
    def _to_planet(self, point: Point2) -> Point2:
        planet_coord = self.baseline + (point - self.offset) / (self.zoom_scale * self.scale)
        return planet_coord.round()
            
    # ------Crosshair
    def move_cursor_to_origin(self):
        self.cross = self.old_cross = Point2(self.gs.present_planet.x, self.gs.present_planet.y)
                                                                                         
    def move_cursor_to_xy(self, key):
        gs = self.gs
        x, y = key.removeprefix('#').split(',')
        # x, y are in screen coordinates
        p = self._to_planet(Point2(int(x), int(y)))
        planet = gs.planet.find_planet(*p.as_tuple(), gs.galaxy_seed)
        # centre cross on nearest planet
        self.cross = self.old_cross = Point2(planet.x, planet.y)
        # gs.msg.text = f'{x=}, {y=},   {planet.x},{planet.y}'
            
    def move_cross(self, dx, dy):
        self.cross_timer = 5
        self.cross = self.old_cross + Point2(dx, dy) * (6 - self.zoom_scale)
        self.old_cross = self.cross
            
    def draw_cross(self, p: Point2):
        c = self._to_screen(p)
        size = 16 if self.gs.current_screen == cs.SCR_SHORT_RANGE else 8
        self.gfx.draw_colour_line(c.x - size, c.y, c.x + size, c.y, cs.WHITE, width=4)
        self.gfx.draw_colour_line(c.x, c.y - size, c.x, c.y + size, cs.WHITE, width=4)
            
    def crosshair_countdown(self):
        # Crosshair countdown
        if self.cross_timer > 0:
            self.cross_timer -= 1
            if self.cross_timer == 0:
                self.show_distance_to_planet()
                
    def move_if_changed(self):
        # Redraw crosshair if moved
        if self.old_cross.x == -1:
            self.move_cursor_to_origin()
        
        self.draw_cross(self.old_cross)
        self.old_cross = self.cross
        self.draw_cross(self.cross)       # Crosshair countdown
                  
    def _update_cross_for_hyperspace(self):
        self.cross = Point2(self.gs.hyperspace_planet.x, self.gs.hyperspace_planet.y)
                        
    # ------Short-range chart
    
    def _plot_planets_and_names(self):
        # for short range chart, find nearest planets and plot names
        # row 18 is centre screen
        gs = self.gs
        gfx = self.gfx
        
        sorted_planets = gs.planet.get_closest_planets(gs.galaxy_seed, gs.present_planet, max_distance=self.gs.cmdr.fuel)
        for planet in sorted_planets:
            coord = self._to_screen(Point2(planet.x, planet.y)).round()
            
            planet_name = planet.name
            col = math.ceil(coord.x * cs.TEXT_LENGTH / cs.FLIGHT_RECT.max_x) + 1  # + 1 gives small margin left of the blob
            row = math.ceil((cs.FLIGHT_RECT.max_y - coord.y) / cs.TEXT_Y_INCR) + 2
            # logger.debug(f'{planet_name=}{coord=} {row=}')
            # move row if text clashes with existing text
            for i in [0, -1, 1]:
                if self.gfx.is_empty_text(row + i, col, len(planet_name)):
                    r, c = row + i, col
                    if r >= 3:
                       gfx.display_text(c, r, planet_name)
                       break
                    
            # planet seed has property tech 0-14
            blob_size = round(planet.glx.tech / 3 + 2) * 4
            
            colour = cs.COLOUR_LIST[planet.glx.colour]
            gfx.plot_pixel(*coord.as_tuple(), colour, blob_size)
            
    def display_short_range_chart(self):
        # short range chart is centred around current location and scaled
        # x  and yange in range 0-255
        # screen is 0,0 top left
        # to just outside fuel circle
        # it shows names as close as possible  to planets, without overlap
        # make sure there is one space to left of name. if not, try to use row above or below
        # this version will scale to flight_rect
        gfx = self.gfx
        gs = self.gs
        # scale with fuel circle self.scale is
        
        # logger.debug(f'{fuel_radius=} {cs.FLIGHT_H=}')
        
        self.zoom_scale = 5 * 70 / cs.MAX_FUEL
        
        self.offset = Point2(*cs.FLIGHT_RECT.center())
        self.baseline = Point2(gs.present_planet.x, gs.present_planet.y)
        if self.old_cross.x == -1:
            self.move_cursor_to_origin()
            
        gfx.clear_display()
        gfx.display_centre_text(0, "SHORT RANGE CHART", 140, cs.GOLD)
        centre = self._to_screen(Point2(gs.present_planet.x, gs.present_planet.y))
        self.draw_fuel_limit_circle(centre)
        self._plot_planets_and_names()
        self.move_if_changed()
        self.show_distance_to_planet()
        self.gfx.text_render()
    
    # -------Galactic chart

    def display_galactic_chart(self):
        gfx = self.gfx
        gs = self.gs
        self.zoom_scale = 1
        self.offset = Point2(cs.FLIGHT_RECT.x, cs.FLIGHT_RECT.y)
        self.baseline = Point2(0, 0)
        if self.old_cross.x == -1:
            self.move_cursor_to_origin()
            
        gfx.clear_display()
        gfx.display_centre_text(0, f"GALACTIC CHART {self.gs.cmdr.galaxy_number + 1}", 140, cs.GOLD)
        self.draw_fuel_limit_circle(self._to_screen(Point2(gs.present_planet.x, gs.present_planet.y)))
        
        glx = self.gs.cmdr.galaxy_seed.copy()
        # self._plot_planets_and_names()
        
        for _ in range(256):
            p = self._to_screen(Point2(glx.x, glx.y))
            # 0-14 -> 2-6
            blob_size = round(glx.tech / 3 + 2) * 1.5
            colour = cs.COLOUR_LIST[glx.colour]
            gfx.plot_pixel(*p.as_tuple(), colour, blob_size)
            self._next_planet(glx)
        
        self.move_if_changed()
        self.show_distance_to_planet()
        self.gfx.text_render()
    
    # Planet data screen

    def display_data_on_planet(self):
        gfx = self.gfx
        gs = self.gs
        
        gfx.clear_display()
        planet_name = gs.planet.name_planet(gs.hyperspace_planet)
        gfx.display_centre_text(0, f"DATA ON {planet_name}", 140, cs.GOLD)

        pd = gs.planet.generate_planet_stats(gs.hyperspace_planet)
        gs.current_planet_data = pd
        dist_text = self.show_distance(gs.present_planet, gs.hyperspace_planet)
        self.gfx.display_text(23, cs.NUM_LINES - 1, dist_text)
    
        gfx.display_text(0, 4, f"Economy: {ECONOMY_TYPES[pd.economy]}")
        gfx.display_text(0, 6, f"Government: {GOVERNMENT_TYPES[pd.government]}")
        gfx.display_text(0, 8, f"Tech.Level: {pd.tech_level + 1:3d}")
        gfx.display_text(0, 10, f"Population: {pd.population} Billion")
        # gfx.display_text(0, 12, gs.planet.expand_description(gs.planet.desc_list, gs.hyperspace_planet))
        gfx.display_text(0, 14, f"Gross Productivity: {pd.productivity:5d} M CR")
        gfx.display_text(0, 16, f"Average Radius: {pd.radius:5d} km")
        gfx.display_pretty_text(0, 18, gs.planet.describe_planet(gs.hyperspace_planet))
        self.gfx.text_render()
    
    # -------Commander status
    
    @staticmethod
    def laser_type(strength):
        
        mapping = {
            PULSE_LASER:    LASER_NAMES[0],
            BEAM_LASER:     LASER_NAMES[1],
            MILITARY_LASER: LASER_NAMES[2],
            MINING_LASER:   LASER_NAMES[3],
        }
        return mapping.get(strength, LASER_NAMES[4])

    def display_commander_status(self):
        gfx = self.gfx
        gs = self.gs
        cmdr = self.gs.cmdr
        gs.current_screen = cs.SCR_CMDR_STATUS

        gfx.clear_display()
        gfx.display_centre_text(0, f"COMMANDER {cmdr.name}", 140, cs.GOLD)
        gfx.display_centre_text(1, self.incoming_message, 140, cs.GOLD)
        line_no = 4
        gfx.display_colour_text(0, line_no, "Present System:", cs.GREEN)
        if not gs.witchspace:    # self.gs.ship_x, self.gs.cmdr.ship_y)
            planet_name = gs.planet.get_planet_name(gs.present_planet).title()
            gfx.display_text(17, line_no, planet_name)
        line_no += 1
        gfx.display_colour_text(0, line_no, "Hyperspace System:", cs.GREEN)
        gfx.display_text(19, line_no, gs.planet.get_planet_name(gs.hyperspace_planet).title())
        CONDITION_TEXT = ["Docked", "Green", "Yellow", "Red"]
        # Condition
        if gs.docked:
            condition = 0
        else:
            condition = 1
            for obj in gs.universe:
                t = obj.type
                if t == cs.SHIP_MISSILE or (cs.SHIP_ROCK < t < cs.SHIP_DODEC):
                    condition = 2
                    break
            if condition == 2 and gs.energy < 128:
                condition = 3
        line_no += 1
        gfx.display_colour_text(0,  line_no, "Condition:",    cs.GREEN)
        gfx.display_text(11, line_no, CONDITION_TEXT[condition])
        line_no += 1
        gfx.display_colour_text(0, line_no, "Fuel:",         cs.GREEN)
        gfx.display_text(6, line_no, f"{cmdr.fuel // 10}.{cmdr.fuel % 10} Light Years")
        line_no += 1
        gfx.display_colour_text(0, line_no, "Cash:",         cs.GREEN)
        gfx.display_text(7, line_no, f"{cmdr.credits // 10}.{cmdr.credits % 10} Cr")

        legal = ("Clean" if cmdr.legal_status == 0
                 else "Fugitive" if cmdr.legal_status > 50
                 else "Offender")
        line_no += 1
        gfx.display_colour_text(0, line_no, "Legal Status:", cs.GREEN)
        gfx.display_text(14, line_no, legal)

        rank_title = next(t for score, t in reversed(RATINGS) if cmdr.score >= score)
        line_no += 1
        gfx.display_colour_text(0, line_no, "Rating:",       cs.GREEN)
        gfx.display_text(9, line_no, rank_title)
        line_no += 1
        gfx.display_colour_text(0, line_no, "EQUIPMENT:",    cs.GREEN)
        line_no += 1
        x = EQUIP_START_X
        
        def item(label):
            nonlocal x, line_no
            gfx.display_text(x, line_no, label)
            line_no += 1

        if cmdr.cargo_capacity > 20:
            item("Large Cargo Bay")
        if cmdr.escape_pod:
            item("Escape Pod")
        if cmdr.fuel_scoop:
            item("Fuel Scoops")
        if cmdr.ecm:
            item("E.C.M. System")
        if cmdr.energy_bomb:
            item("Energy Bomb")
        if cmdr.energy_unit:
            item("Extra Energy Unit" if cmdr.energy_unit == 1 else "Naval Energy Unit")
        if cmdr.docking_computer:
           item("Docking Computers")
        if cmdr.galactic_hyperdrive:
           item("Galactic Hyperspace")
        for mount, label in [
            (cmdr.front_laser,  "Front"),
            (cmdr.rear_laser,   "Rear"),
            (cmdr.left_laser,   "Left"),
            (cmdr.right_laser,  "Right"),
        ]:
            if mount:
                item(f"{label} {self.laser_type(mount)} Laser")
        # Add inventory here as it makes sense
        gfx.display_text(0, line_no, "INVENTORY", 140, cs.WHITE)
        line_no += 1
        for i in range(17):
            if cmdr.current_cargo[i] > 0:
                sm = gs.trade.stock_market[i]
                gfx.display_text(x, line_no, f"{sm['name']} {cmdr.current_cargo[i]}{UNIT_NAMES[sm['units']]}")
                line_no += 1
                
        self.gfx.text_render()
        
    # -------Markets
    def display_stock_price(self, i, sm_i):
        gfx = self.gfx
        row = i + self.START_ROW

        gfx.display_text(0,  row, sm_i['name'])
        gfx.display_text(13, row, UNIT_NAMES[sm_i['units']])
        gfx.display_text(19, row, f"{sm_i['current_price'] // 10}.{sm_i['current_price'] % 10}")

        qty = sm_i['current_quantity']
        gfx.display_text(28, row, f"{qty}{UNIT_NAMES[sm_i['units']]}" if qty > 0 else "-")

        held = self.gs.cmdr.current_cargo[i]
        gfx.display_text(37, row, f"{held}{UNIT_NAMES[sm_i['units']]}" if held > 0 else "-")
                
    def highlight_stock(self, i):
        # i is index of stock number
        row = i + self.START_ROW
        self.gfx.highlight(row, cs.DARK_RED)
        
    def select_previous_stock(self):
        if self.gs.docked and self.hilite_market > 0:
            self.hilite_market -= 1
        else:
            self.hilite_market = 16
            
    def select_next_stock(self):
        if self.gs.docked and self.hilite_market < 16:
            self.hilite_market += 1
        else:
            self.hilite_market = 0
            
    def buy_stock(self):
        cmdr = self.gs.cmdr
        sm = self.gs.trade.stock_market
        if not self.gs.docked:
            return
        item = sm[self.hilite_market]
        if item['current_quantity'] == 0 or cmdr.credits < item['current_price']:
            return
        if item['units'] == TONNES and self.gs.trade.total_cargo() == cmdr.cargo_capacity:
            return
        cmdr.current_cargo[self.hilite_market] += 1
        item['current_quantity'] -= 1
        cmdr.credits -= item['current_price']
        
    def sell_stock(self):
        cmdr = self.gs.cmdr
        sm = self.gs.trade.stock_market
        if not self.gs.docked or cmdr.current_cargo[self.hilite_market] == 0:
            return
        item = sm[self.hilite_market]
        cmdr.current_cargo[self.hilite_market] -= 1
        item['current_quantity'] += 1
        cmdr.credits += item['current_price']
        
    def display_market_prices(self):
        gfx = self.gfx
        gs = self.gs
        cmdr = self.gs.cmdr
        # self.sm = self.gs.trade.stock_market
        gfx.clear_display()
        planet_name = gs.planet.name_planet(gs.present_planet)
        gfx.display_centre_text(0, f"{planet_name} MARKET PRICES", 140, cs.GOLD)
        gfx.display_text(0, 23, f"Cash: {cmdr.credits // 10}.{cmdr.credits % 10}")
        for label, x in [("PRODUCT", 0), ("UNIT", 13), ("PRICE", 19),
                         ("FOR SALE", 26), ("IN HOLD", 35)]:
            gfx.display_colour_text(x, 3, label, cs.GREEN)
        sm = self.gs.trade.stock_market
        for i in range(17):
            self.display_stock_price(i, sm[i])

        if gs.docked:
            if self.hilite_market == -1:
                self.hilite_market = 0
            self.highlight_stock(self.hilite_market)
                    
        gfx.text_render()
        
    def display_hyperspace_planet_prices(self):
        gfx = self.gfx
        gfx.clear_display()
        planet_name = self.gs.planet.name_planet(self.gs.hyperspace_planet)
        gfx.display_centre_text(0, f"{planet_name} MARKET PRICES", 140, cs.GOLD)
        for label, x in [("PRODUCT", 0), ("UNIT", 13), ("PRICE", 19)]:
            gfx.display_colour_text(x, 3, label, cs.GREEN)
        econ = self.gs.hyperspace_planet.econ
        sm = self.gs.trade.generate_stock_market(econ)
        for i in range(17):
            row = i + self.START_ROW
            gfx.display_text(0,  row, sm[i]['name'])
            gfx.display_text(13, row, UNIT_NAMES[sm[i]['units']])
            gfx.display_text(19, row, f"{sm[i]['current_price'] // 10}.{sm[i]['current_price'] % 10}")
            # qty = sm[i]['current_quantity']
            # gfx.display_text(28, row, f"{qty}{UNIT_NAMES[sm[i]['units']]}" if qty > 0 else "-")
        gfx.text_render()
        
    # -------Inventory

    def display_inventory(self):
        gfx = self.gfx
        gs = self.gs
        cmdr = self.gs.cmdr
        gs.current_screen = cs.SCR_INVENTORY

        gfx.clear_display()
        gfx.display_centre_text(0, "INVENTORY", 140, cs.GOLD)

        gfx.display_colour_text(0, 2, "Fuel:",  cs.GREEN)
        gfx.display_text(6, 2, f"{cmdr.fuel // 10}.{cmdr.fuel % 10} Light Years")
        gfx.display_colour_text(0, 3, "Cash:",  cs.GREEN)
        gfx.display_text(7, 3, f"{cmdr.credits // 10}.{cmdr.credits % 10} Cr")

        for i in range(17):
            if cmdr.current_cargo[i] > 0:
                sm = gs.stock_market[i]
                gfx.display_text(0,  i+4, sm.name)
                gfx.display_text(10, i+4, f"{cmdr.current_cargo[i]}{UNIT_NAMES[sm.units]}")
        self.gfx.text_render()
    
    # Equipment screen

    def equip_present(self, eq_type):
        cmdr = self.gs.cmdr
        
        checks = {
            EQ_FUEL: lambda: cmdr.fuel >= cs.MAX_FUEL,
            EQ_MISSILE: lambda: cmdr.missiles >= 4,
            EQ_CARGO_BAY: lambda: cmdr.cargo_capacity > 20,
            EQ_ECM: lambda: bool(cmdr.ecm),
            EQ_FUEL_SCOOPS: lambda: bool(cmdr.fuel_scoop),
            EQ_ESCAPE_POD: lambda: bool(cmdr.escape_pod),
            EQ_ENERGY_BOMB: lambda: bool(cmdr.energy_bomb),
            EQ_ENERGY_UNIT: lambda: bool(cmdr.energy_unit),
            EQ_DOCK_COMP: lambda: bool(cmdr.docking_computer),
            EQ_GAL_DRIVE: lambda: bool(cmdr.galactic_hyperdrive),
            EQ_FRONT_PULSE: lambda: cmdr.front_laser == PULSE_LASER,
            EQ_REAR_PULSE: lambda: cmdr.rear_laser == PULSE_LASER,
            EQ_LEFT_PULSE: lambda: cmdr.left_laser == PULSE_LASER,
            EQ_RIGHT_PULSE: lambda: cmdr.right_laser == PULSE_LASER,
            EQ_FRONT_BEAM: lambda: cmdr.front_laser == BEAM_LASER,
            EQ_REAR_BEAM: lambda: cmdr.rear_laser == BEAM_LASER,
            EQ_LEFT_BEAM: lambda: cmdr.left_laser == BEAM_LASER,
            EQ_RIGHT_BEAM: lambda: cmdr.right_laser == BEAM_LASER,
            EQ_FRONT_MINING: lambda: cmdr.front_laser == MINING_LASER,
            EQ_REAR_MINING: lambda: cmdr.rear_laser == MINING_LASER,
            EQ_LEFT_MINING: lambda: cmdr.left_laser == MINING_LASER,
            EQ_RIGHT_MINING: lambda: cmdr.right_laser == MINING_LASER,
            EQ_FRONT_MILITARY: lambda: cmdr.front_laser == MILITARY_LASER,
            EQ_REAR_MILITARY: lambda: cmdr.rear_laser == MILITARY_LASER,
            EQ_LEFT_MILITARY: lambda: cmdr.left_laser == MILITARY_LASER,
            EQ_RIGHT_MILITARY: lambda: cmdr.right_laser == MILITARY_LASER,
        }
        return int(checks[eq_type]()) if eq_type in checks else 0

    def display_equip_price(self, y, item):
        gfx = self.gfx
        col = cs.WHITE if item.canbuy else cs.GREY
        c = 3 if item.name[0] == '>' else 0
        gfx.display_colour_text(c, y, item.name[1:], col)
        if item.price != 0:
            gfx.display_colour_text(
                21, y,
                f"{item.price // 10}.{item.price % 10}", col)
        
    def highlight_equip(self, i):
        # i is index of equipment number
        row = i + self.EQUIP_START_ROW
        self.gfx.highlight(row, cs.DARK_RED)
  
    def select_next_equip(self):
        if not self.gs.docked:
            return
        self.hilite_equip = (self.hilite_equip + 1) % len(self.items_to_buy)
                                 
    def select_previous_equip(self):
        if not self.gs.docked:
            return
        self.hilite_equip = (self.hilite_equip - 1) % len(self.items_to_buy)

    def list_equip_prices(self):
        # list  items for sale that are available at this tech level,
        #
        # tagged to show
        # item you csnt afford or already have are grey
        gs = self.gs
        
        tech_level = gs.current_planet_data.tech_level + 1

        self.equip_stock[0].price = (cs.MAX_FUEL - self.gs.cmdr.fuel) * 2

        y = self.EQUIP_START_ROW
        item_list = []
        for item in self.equip_stock:
            item.canbuy = int(
                not self.equip_present(item.type) and item.price <= self.gs.cmdr.credits
            )
            if item.show and tech_level >= item.level:
                item_list.append(item)
        for i, item in enumerate(item_list):
            self.display_equip_price(y + i, item)
        return item_list
                        
    def collapse_equip_list(self):
        # show selected subset
        for item in self.equip_stock:
            item.show = int(item.name[0] in (' ', '+'))

    @staticmethod
    def laser_refund(laser):
        return {
            PULSE_LASER:    4000,
            BEAM_LASER:     10000,
            MILITARY_LASER: 60000,
            MINING_LASER:   8000,
        }.get(laser, 0)

    def buy_equip(self):
        gs = self.gs
        cmdr = self.gs.cmdr
        item = self.items_to_buy[self.hilite_equip]
        self.collapse_equip_list()
        if item.name[0] == '+':
            # submenu, enables front, rear etc
            item.show = 0
            base = self.equip_stock.index(item) + 1
            for i in range(5):
                self.equip_stock[base + i].show = 1
            return

        if not item.canbuy:
            return
        mount_map = {
                EQ_FRONT_PULSE:    ('front_laser',  PULSE_LASER),
                EQ_REAR_PULSE:     ('rear_laser',   PULSE_LASER),
                EQ_LEFT_PULSE:     ('left_laser',   PULSE_LASER),
                EQ_RIGHT_PULSE:    ('right_laser',  PULSE_LASER),
                EQ_FRONT_BEAM:     ('front_laser',  BEAM_LASER),
                EQ_REAR_BEAM:      ('rear_laser',   BEAM_LASER),
                EQ_LEFT_BEAM:      ('left_laser',   BEAM_LASER),
                EQ_RIGHT_BEAM:     ('right_laser',  BEAM_LASER),
                EQ_FRONT_MINING:   ('front_laser',  MINING_LASER),
                EQ_REAR_MINING:    ('rear_laser',   MINING_LASER),
                EQ_LEFT_MINING:    ('left_laser',   MINING_LASER),
                EQ_RIGHT_MINING:   ('right_laser',  MINING_LASER),
                EQ_FRONT_MILITARY: ('front_laser',  MILITARY_LASER),
                EQ_REAR_MILITARY:  ('rear_laser',   MILITARY_LASER),
                EQ_LEFT_MILITARY:  ('left_laser',   MILITARY_LASER),
                EQ_RIGHT_MILITARY: ('right_laser',  MILITARY_LASER),
            }
        
        if item.type == EQ_FUEL:
            cmdr.fuel = gs.myship.max_fuel
            gs.space.update_console()
        elif item.type == EQ_MISSILE:
            cmdr.missiles += 1
            gs.space.update_console()
        elif item.type == EQ_CARGO_BAY:
            cmdr.cargo_capacity = 35
        elif item.type == EQ_ECM:
            cmdr.ecm = 1
        elif item.type == EQ_FUEL_SCOOPS:
            cmdr.fuel_scoop = 1
        elif item.type == EQ_ESCAPE_POD:
            cmdr.escape_pod = 1
        elif item.type == EQ_ENERGY_BOMB:
            cmdr.energy_bomb = 1
        elif item.type == EQ_ENERGY_UNIT:
            cmdr.energy_unit = 1
        elif item.type == EQ_DOCK_COMP:
            cmdr.docking_computer = 1
        elif item.type == EQ_GAL_DRIVE:
            cmdr.galactic_hyperdrive = 1
        elif item.type in mount_map:
            attr, laser = mount_map[item.type]
            cmdr.credits += self.laser_refund(getattr(cmdr, attr))
            setattr(cmdr, attr, laser)

        cmdr.credits -= item.price
        self.list_equip_prices()
        
    def equip_ship(self):
        gfx = self.gfx
        cmdr = self.gs.cmdr
        gfx.clear_display()
        gfx.display_centre_text(0, "EQUIP SHIP", 140, cs.GOLD)
        # already collapsed
        # self.collapse_equip_list()
        if self.hilite_equip == -1:
            self.hilite_equip = 0
        self.items_to_buy = self.list_equip_prices()
        self.highlight_equip(self.hilite_equip)
        gfx.display_text(0, 20, f"Cash: {cmdr.credits // 10}.{cmdr.credits % 10}")
        self.gfx.text_render()
