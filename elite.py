from dataclasses import dataclass, field, fields
import dataclasses
from typing import List, Optional
import json
import constants as cs
# from pathlib import Path
import logging
logger = logging.getLogger(__name__)

                                
@dataclass
class GalaxySeed:
    """The 6-byte seed used to generate an entire galaxy."""

    a: int = 0x5A  # MSB of s0
    b: int = 0x4A  # LSB of s0
    c: int = 0x02  # MSB of s1
    d: int = 0x48  # LSB of s1
    e: int = 0xB7  # MSB of s2
    f: int = 0x53  # LSB of s2
    
    def __repr__(self):
        seed_str = ", ".join([f"{s:#06x}" for s in self.raw_seed()]) + ' ' + self.name
        return seed_str
    
    def copy(self):
        return dataclasses.replace(self)
        
    # convert from GalaxySeed object to list of 3 16bit number
    def raw_seed(self):
       s0 = (self.a << 8) + self.b
       s1 = (self.c << 8) + self.d
       s2 = (self.e << 8) + self.f
       return [s0, s1, s2]
    
    # convert from list of 3 16bit number to GalaxySeed parameters
    def to_galaxy(self, raw_seed):
        s0, s1, s2 = raw_seed
        self.a = s0 >> 8 & 0xFF
        self.b = s0 & 0xFF
        self.c = s1 >> 8 & 0xFF
        self.d = s1 & 0xFF
        self.e = s2 >> 8 & 0xFF
        self.f = s2 & 0xFF
           
    def waggle(self):
        """The 'Waggle': moves the seed forward one step."""
        w0, w1, w2 = self.raw_seed()
        new_w2 = (w0 + w1 + w2) & 0xFFFF
        new_w = [w1, w2, new_w2]
        self.to_galaxy(new_w)
        
    @property
    def x(self):
        # use everywhere planet coords needed
        return self.c
        
    @property
    def y(self):
        # use everywhere planet coords needed
        return self.a
        
    @property
    def radius(self):
        # useful to keep with seed if seed is a planet
        # range 2816 to 6911
        return (((self.e & 15) + 11) * 256) + self.c
        
    @property
    def colour(self):
        # colour will indicate government
        return (self.d // 8) & 7
                
    @property
    def color(self):
        return (self.d // 8) & 7
        
    @property
    def tech(self):
        # 0 - 14
        gov = (self.d // 8) & 7
        return (self.econ ^ 7) + (self.c & 3) + (gov // 2) + (gov & 1)
        
    @property
    def econ(self):
        gov = (self.d // 8) & 7
        econ_ = self.a & 7
        if gov < 2:
            econ_ |= 2
        return econ_
                         
    @property
    def name(self):
        """
        seed: A list of 3 16-bit integers [w0, w1, w2]
        representing the planet's unique state.
        """
        seed = self.copy()
        syllables = ["AL", "LE", "XE", "GE", "ZA", "CE", "BI", "SO",
                     "US", "ES", "AR", "MA", "IN", "DI", "RE", "A?",
                     "ER", "AT", "EN", "BE", "RA", "LA", "VE", "TI",
                     "ED", "OR", "QU", "AN", "TE", "IS", "RI", "ON"]
        name = ""
        # A planet name is built from 3 or 4 syllables
        length = 3 if (seed.b & 0x40) == 0 else 4
        
        for i in range(length):
            # Determine the index for the syllable table (5 bits)
            index = seed.e & 0x1F
            if index > 0:
               syllable = syllables[index]
               syllable = syllable.replace('?', '')
               name += syllable
            seed.waggle()
        return name.capitalize()

                                                                                                
@dataclass
class Commander:
    name: str = "JAMESON"
    ship_x: int = 0x14
    ship_y: int = 0xAD
    galaxy_seed: GalaxySeed = field(default_factory=GalaxySeed)
    credits: int = 1000  # Credits * 10
    fuel: int = cs.MAX_FUEL  # Fuel * 10//
    galaxy_number: int = 0
    front_laser: int = cs.PULSE_LASER
    rear_laser: int = 0
    left_laser: int = 0
    right_laser: int = 0
    cargo_capacity: int = 20
    current_cargo: List[int] = field(default_factory=lambda: [0] * 17)
    ecm: bool = False
    fuel_scoop: bool = False
    energy_bomb: bool = False
    energy_unit: int = 0
    docking_computer: bool = False
    galactic_hyperdrive: bool = False
    escape_pod: bool = False
    missiles: int = 3
    legal_status: int = 0
    station_stock: List[int] = field(
        default_factory=lambda: [
            0x10,
            0x0F,
            0x11,
            0x00,
            0x03,
            0x1C,
            0x0E,
            0x00,
            0x00,
            0x0A,
            0x00,
            0x11,
            0x3A,
            0x07,
            0x09,
            0x08,
            0x00,
        ]
    )
    market_rnd: int = 0
    score: int = 0
    tally: int = 0
    mission: int = 0

# --- Global Game State ---


class EliteState:
    def __init__(self):
        # Navigation
        self.present_planet: Optional[GalaxySeed] = None
        self.hyperspace_planet: Optional[GalaxySeed] = None
        self.current_planet_data = None

        # Flight Variables
        self.game_over = False
        self.docked = True
        self.flight_speed = 0
        self.flight_roll = 0
        self.flight_climb = 0
        self.energy = 255
        self.laser_temp = 0
        self.auto_pilot = False

        # Options
        self.instant_dock = False
        self.wireframe = False

        # Commander
        self.cmdr = Commander()
        self.saved_cmdr = Commander()  # Jameson default

    def restore_saved_commander(self, planet_manager, trade_manager):
        """
        Equivalent to restore_saved_commander() in C.
        Sets up the initial planet and market based on the saved seed.
        """
        # Copy the default Jameson template
        self.cmdr = self.saved_cmdr

        # Find the planet Jameson is currently at based on coordinates
        self.present_planet = planet_manager.find_planet(
            self.cmdr.ship_x, self.cmdr.ship_y,
            self.cmdr.galaxy_seed)
        self.hyperspace_planet = self.present_planet

        # Generate the world and market
        self.current_planet_data = planet_manager.generate_planet_stats(
            self.present_planet
            
        )
        trade_manager.stock_market = trade_manager.generate_stock_market(self.current_planet_data.economy)
        trade_manager.set_stock_quantities(self.cmdr.station_stock)


# very much simplified load save file
# using json human readable data
# uses a list of all Commander parameters
# can't convert GalaxySeed to json so save numbers instead
cmdr_params = [f.name for f in fields(Commander) if f.name != 'galaxy_seed']


def get_file_name():
    return ''


def save_game_json(cmdr, file_name):
    # Save all variable data to human readable json file
    path = file_name  # Path("files") / Path(file_name).with_suffix(".json")
    logger.debug(cmdr)
    try:
        cmdr.name = path.stem.upper()
        save_data = {k: getattr(cmdr, k) for k in cmdr_params}
        save_data['galaxy_seed'] = cmdr.galaxy_seed.raw_seed()
        with open(path, "w") as output_file:
            json.dump(save_data, output_file, indent=4)

    except (FileNotFoundError, PermissionError):
        return False, "SAVE FILE COULD NOT BE CREATED"
    return True, "SAVE FILE CREATED"


def load_game_json(cmdr, file_name):
    logger.debug(f'loading {file_name}')
    # Load all variable data from human readable json file
    path = file_name
    try:
        with open(path, "r") as input_file:
            data = json.load(input_file)

        for k, v in data.items():
            if k == 'galaxy_seed':
                cmdr.galaxy_seed.to_galaxy(v)
            else:
                setattr(cmdr, k, v)
                                                         
        cmdr.name = path.stem.upper()
    except FileNotFoundError:
        return False, "SAVE FILE NOT FOUND"
    except KeyError as e:
        return False, f"Error: Save file is missing data for {e}"
    return True, "Game Loaded Successfully!"


if __name__ == "__main__":
    print(cmdr_params)
    cmdr = Commander()
    save_game_json(cmdr, "test")
    load_game_json(cmdr, "test")
    print(cmdr)

