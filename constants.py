# Chris Thomas Apr 2026
# All screen sizes scale to Ipad screen
from change_screensize import get_screen_size
from scene import Rect
from PIL import Image
import logging

# ipad (1112.00, 834.00)
# ipad_mini (1133.00, 744.00)
# ipad13 (1366.00, 1024.00)
# iphone (852.00, 393.00)


def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)s.%(msecs)03d] %(levelname)s in %(name)s/%(funcName)s (line %(lineno)d): %(message)s',
        datefmt='%H:%M:%S'
    )
    # Set the root level, or specific package level
    logging.getLogger().setLevel(logging.ERROR)


logger = logging.getLogger(__name__)


def is_debug_level():
    return logging.getLevelName(logger.getEffectiveLevel()) == 'DEBUG'
    

# --------Global modes
OLD_SCHOOL = False
SOUND = 1
WIREFRAME = 0
WIREFRAME_REMOVAL = True
FILL = True
YAW_COUPLING = 0.15
TELEPORT = True
UNIVERSE_STATUS = True
INSTANT_DOCK = True
MAX_FUEL = 70
FLIGHT_DIRECTOR = True
FIRE_ACCURACY = 8  # higher makes it easier to hit target default 8
CLASSIC_DISTANCE = True
SCANNER_LABELS = True
PITCH_RATE = 32

if OLD_SCHOOL:
   WIREFRAME = 1
   WIREFRAME_REMOVAL = False
   FILL = False
   YAW_COUPLING = 0.0
   TELEPORT = False
   UNIVERSE_STATUS = False
   INSTANT_DOCK = False
   MAX_FUEL = 70
   FLIGHT_DIRECTOR = False
   FIRE_ACCURACY = 1  # higher makes it easier to hit target default 8
   CLASSIC_DISTANCE = True
   SCANNER_LABELS = False

# --------Screen areas
# flight area, scanner, with scale
# hud has been split into left and right
# stay fixed to left and right
# scanner fills the gap


hud_l = Image.open('images/hud_left_1.png')
hud_r = Image.open('images/hud_right_1.png')

hud_l_w, hud_l_h = hud_l.size
hud_r_w, hud_r_h = hud_r.size

W, H = get_screen_size()

HUD_SCALE = min(H / 834, 1.0)

logger.debug(f'{W=} {H=}')
FRAMERATE = 30

GAME_W = int(0.67 * W)
GAME_H = int(H-20)
BORDER = 4
RADIUS = 10
FLIGHT_W = GAME_W - 2 * BORDER

HUD_W = FLIGHT_W
HUD_H_L = hud_l_h * HUD_SCALE
HUD_H_R = hud_r_h * HUD_SCALE
HUD_W_L = hud_l_w * HUD_SCALE
HUD_W_R = hud_r_w * HUD_SCALE

HUD_H = GAME_H * 0.33
HUD_RECT = Rect(BORDER, BORDER,
                HUD_W, HUD_H + BORDER)
HUD_LEFT = Rect(BORDER, 4*BORDER,
                HUD_W_L + 0 * BORDER,
                HUD_H_L + BORDER)

HUD_RIGHT = Rect(HUD_W - HUD_W_R + BORDER, 4*BORDER,
                 HUD_W_R + 2 * BORDER, HUD_H_R + BORDER)
HUD_CENTRE = Rect(HUD_W_L + 2 * BORDER, 3*BORDER,
                  HUD_W - HUD_W_L - HUD_W_R - 2 * BORDER, HUD_H + BORDER)
                                      
TOP_H = 0.08 * GAME_H
FLIGHT_H = GAME_H - HUD_H - 5 * BORDER - TOP_H
FLIGHT_RECT = Rect(BORDER, HUD_CENTRE.max_y + 3 * BORDER,
                   FLIGHT_W, FLIGHT_H)
TOP_RECT = Rect(BORDER, GAME_H - BORDER - TOP_H, FLIGHT_W, TOP_H)

SCANNER_H = HUD_H * 0.75
SCANNER_RECT = Rect(HUD_CENTRE.x, HUD_CENTRE.y + 0.125 * HUD_CENTRE.h,
                    HUD_CENTRE.w, SCANNER_H)

COMPASS_W = HUD_RECT.height/4
COMPASS_X = SCANNER_RECT.max_x - COMPASS_W/2 + 4
COMPASS_Y = HUD_RECT.max_y - COMPASS_W/2 + 8
COMPASS_RECT = Rect(COMPASS_X - COMPASS_W/2,
                    COMPASS_Y - COMPASS_W/2,
                    COMPASS_W, COMPASS_W)

METER_LENGTH = 80 * HUD_SCALE
METER_HEIGHT = 10 * HUD_SCALE
METER_BASE_Y = 113 * HUD_SCALE + 3 * BORDER
METER_BASE_LEFTX = 189 * HUD_SCALE
METER_BASE_RIGHTX = FLIGHT_RECT.max_x - 217 * HUD_SCALE
METER_DELTA_Y = -16 * HUD_SCALE

# keyboard fills 1/3 screen
KEYBOARD_X = GAME_W
KEYBOARD_W = W - GAME_W
KEYBOARD_H = KEYBOARD_W * 3/4  # 4:3 ratio
KEYBOARD_Y = H * 0.75 - KEYBOARD_H  # joystick size
KEYBOARD_RECT = Rect(KEYBOARD_X, KEYBOARD_Y, KEYBOARD_W, KEYBOARD_H)

# joysticks are centred on keyboard * 0.25 and 0.75
JOYSTICK_1_RADIUS = KEYBOARD_W * 0.2
JOYSTICK_2_RADIUS = KEYBOARD_W * 0.15  # 3/4 joystick_1
JOYSTICK_1_POSITION = (KEYBOARD_X + KEYBOARD_W * 0.75, JOYSTICK_1_RADIUS * 1.1)
JOYSTICK_2_POSITION = (KEYBOARD_X + KEYBOARD_W * 0.25, JOYSTICK_1_RADIUS * 1.1)
# midway between joysticks, midway between joystick y and lower edge of keyboard
# size joystick2. 2
centrex = KEYBOARD_RECT.center().x
centrey = (JOYSTICK_1_RADIUS * 1.75)  # + KEYBOARD_Y-KEYBOARD_H) / 2
radius = KEYBOARD_W * 0.067
rect = (centrex-radius, centrey - radius, 2 * radius, 2 * radius)
FIRE_BUTTON_RECT = Rect(*rect)

# text grid (always on flight_surface)
# Text grid is a fixed row/cols.
# scale font size and spacing to fit screen
TEXT_START_X = 16  # no of pixels from left to start text
TEXT_START_Y = 8  # no of pixels from top to start text
NUM_LINES = 34  # 0-36
TEXT_LENGTH = 49   # 0-48

# 1. Vertical Logic
# The total distance from our start Y to the bottom edge (min_y)
total_v_space = FLIGHT_RECT.height + TOP_RECT.h - TEXT_START_Y
TEXT_Y_INCR = total_v_space / NUM_LINES
FONT_H = round(TEXT_Y_INCR)  # Actual font size for scene.text()
# Font height should be slightly less than or equal to the increment
# to ensure there is no overlapping.
# 0.8 is a good 'safe' ratio for monospaced fonts in Pythonista.
FONT_H = TEXT_Y_INCR * 0.8

# 2. Horizontal Logic
# Ensuring the length of characters fits the width
total_h_space = FLIGHT_RECT.width - (TEXT_START_X * 2)
TEXT_X_INCR = total_h_space / TEXT_LENGTH
FONT_W = TEXT_X_INCR

# 3. Reference Lines
# If TOP_LINE is meant to be the Y-coord of the first line of text:
# In scene, Y increases UPWARDS.
# So the first line is at the top of the rect minus the start offset.
TOP_LINE = TEXT_Y_INCR * 2.5 + TEXT_START_Y


# Fuller colour set
# color (27 total, 24-bit RGB sets)
BLACK = (0, 0, 0)
NAVY = (0, 0, 0.5)
BLUE = (0, 0, 1.0)
FOREST_GREEN = (0, 0.5, 0)
TEAL = (0, 0.5, 0.5)
BLUE_GREEN = (0, 0.5, 1.0)
GREEN = (0, 1.0, 0)
PALE_GREEN = (0, 1.0, 0.5)
CYAN = (0, 1.0, 1.0)
MAROON = (0.5, 0, 0)
PURPLE = (0.5, 0, 0.5)
INDIGO = (0.5, 0, 1.0)
OLIVE = (0.5, 0.5, 0)
GRAY = (0.5, 0.5, 0.5)
GREY = (0.5, 0.5, 0.5)
SAND_BLUE = (0.5, 0.5, 1.0)
KERMIT_GREEN = (0.5, 1.0, 0)
POND_SCUM = (0.5, 1.0, 0.5)
AQUA = (0.5, 1.0, 1.0)
RED = (1.0, 0, 0)
DARK_RED = (0.55, 0.0, 0.0)
BARBIE = (1.0, 0, 0.5)
MAGENTA = (1.0, 0, 1.0)
GOLD = (1.0, 0.84, 0.0)
ORANGE = (1.0, 0.5, 0)
CORAL = (1.0, 0.5, 0.5)
PINK = (1.0, 0.5, 1.0)
YELLOW = (1.0, 1.0, 0)
KHAKI = (1.0, 1.0, 0.5)
WHITE = (1.0, 1.0, 1.0)
GREY_2 = (0.67, 0.67, 0.67)  # scanner
# 7 colours for planets
GOVERNMENT_TYPES = [
    "Anarchy", "Feudal", "Multi-Government", "Dictatorship",
    "Communist", "Confederacy", "Democracy", "Corporate State"
]
COLOUR_LIST = [ORANGE, CORAL, FOREST_GREEN, TEAL, BLUE_GREEN, PALE_GREEN,
               CYAN, MAROON, KHAKI, PURPLE,  OLIVE,
               SAND_BLUE, POND_SCUM, AQUA, BARBIE,
               MAGENTA, ORANGE, CORAL, KHAKI]

JOYSTICK_DEAD_ZONE = 0.5

# ── Screen constants ──────────────────────────────────────────────────────────
SCR_INTRO_ONE = 0
SCR_INTRO_TWO = 1
SCR_FRONT_VIEW = 2
SCR_REAR_VIEW = 3
SCR_LEFT_VIEW = 4
SCR_RIGHT_VIEW = 5
SCR_GALACTIC_CHART = 6
SCR_SHORT_RANGE = 7
SCR_MARKET_PRICES = 8
SCR_EQUIP_SHIP = 9
SCR_CMDR_STATUS = 10
SCR_TRADE = 11
SCR_COMMANDER = 12
SCR_INVENTORY = 13
SCR_QUIT = 14
SCR_GAME_OVER = 15
SCR_ESCAPE_POD = 16
SCR_BREAK_PATTERN = 17
SCR_SAVE_CMDR = 18
SCR_LAUNCH = 19
SCR_PLANET_DATA = 22
SCR_OUTSIDE = [SCR_FRONT_VIEW, SCR_REAR_VIEW,
               SCR_LEFT_VIEW, SCR_RIGHT_VIEW]
SCR_HYPERSPACE_COMPLETE = 23
SCR_DOCKING_COMPLETE = 24
SCR_LAUNCH_COMPLETE = 25
SCR_MISSION = 26

# space.py redefines these for laser only
# SCR_FRONT_VIEW = 1
# SCR_REAR_VIEW  = 2
# SCR_RIGHT_VIEW = 3
# SCR_LEFT_VIEW  = 4
# SCR_BREAK_PATTERN = 5


# --- Constants ---
PULSE_LASER = 1
BEAM_LASER = 2
MILITARY_LASER = 0x97
MINING_LASER = 0x32
NO_OF_SHIPS = 33

GFX_SCALEX = FLIGHT_RECT.w / 255   # adjust to taste
GFX_SCALEY = FLIGHT_RECT.h / 255   # adjust to taste
MAX_UNIV_OBJECTS = 23

PLANET_RADIUS = 32767
STATION_RADIUS = 180
JUMP_ANIMATION = 0.6
# Unit Constants
TONNES = 0
KILOGRAMS = 1
GRAMS = 2
CR = '\n'
# Commodity Indices
SLAVES = 3
NARCOTICS = 6
FIREARMS = 10
ALIEN_ITEMS_IDX = 16

# images

IMG_MISSILE_YELLOW = 'missyell.bmp'
IMG_MISSILE_RED = 'missred.bmp'
IMG_MISSILE_GREEN = 'missgrn.bmp'

# ═══════════════════════════════════════════════════════════════════════════════
# Sound stubs
# ═══════════════════════════════════════════════════════════════════════════════

SND_BEEP = 'beep'
SND_BOOP = "boop"
SND_CRASH = "crash"
SND_BLUE_DANUBE = 'danube'
SND_DOCK = "docking3"
SND_ECM = "ecm"
SND_ELITE_THEME = 'theme'
SND_EXPLODE = 'explode'
SND_GAMEOVER = "gameover"
SND_HYPERSPACE = "hyper"
SND_HIT_ENEMY = "hit_enemy"
SND_LAUNCH = 'Jump2'
SND_MISSILE = "missile"
SND_PULSE = "pulse"
SND_INCOMMING_FIRE_1 = "incom1"
SND_INCOMMING_FIRE_2 = "incom2"

# Ship Flags
FLG_DEAD = 0x01
FLG_REMOVE = 0x02
FLG_SLOW = 0x04
FLG_ANGRY = 0x08
FLG_BOLD = 0x10
FLG_INACTIVE = 0x20
FLG_FLY_TO_PLANET = 0x40
FLG_FLY_TO_STATION = 0x80
FLG_HAS_ECM = 0x100
FLG_FIRING = 0x200
FLG_HOSTILE = 0x400
FLG_POLICE = 0x800
FLG_CLOAKED = 0x1000
FLG_MISSILE = 0x2000
FLG_ALIEN = 0x4000
FLG_STATION = 0x8000  # for scanner
FLG_PLANET = 0x10000  # for scanner
FLG_SEEKER = 0x20000

MISSILE_UNARMED = -2
MISSILE_ARMED = -1

SHIP_MISSILE = 1
SHIP_CORIOLIS = 2
SHIP_ESCAPE_CAPSULE = 3
SHIP_ALLOY = 4
SHIP_CARGO = 5
SHIP_BOULDER = 6
SHIP_ASTEROID = 7
SHIP_ROCK = 8
SHIP_SHUTTLE = 9
SHIP_TRANSPORTER = 10
SHIP_COBRA3 = 11
SHIP_PYTHON = 12
SHIP_BOA = 13
SHIP_ANACONDA = 14
SHIP_HERMIT = 15
SHIP_VIPER = 16
SHIP_SIDEWINDER = 17
SHIP_MAMBA = 18
SHIP_KRAIT = 19
SHIP_ADDER = 20
SHIP_GECKO = 21
SHIP_COBRA1 = 22
SHIP_WORM = 23
SHIP_COBRA3_LONE = 24
SHIP_ASP2 = 25
SHIP_PYTHON_LONE = 26
SHIP_FER_DE_LANCE = 27
SHIP_MORAY = 28
SHIP_THARGOID = 29
SHIP_THARGON = 30
SHIP_CONSTRICTOR = 31
SHIP_COUGAR = 32
SHIP_DODEC = 33
SHIP_STATIONV = 34
SHIP_PLANET = -1
SHIP_SUN = -2
SHIP_PLAYER = -96


INITIAL_FLAGS = {
    0:  0,
    SHIP_MISSILE:      0,
    SHIP_CORIOLIS:     FLG_STATION,
    SHIP_ESCAPE_CAPSULE: FLG_SLOW | FLG_FLY_TO_PLANET,
    SHIP_ALLOY:        FLG_INACTIVE,
    SHIP_CARGO:        FLG_INACTIVE,
    SHIP_BOULDER:      FLG_INACTIVE,
    SHIP_ASTEROID:     FLG_INACTIVE,
    SHIP_ROCK:         FLG_INACTIVE,
    SHIP_SHUTTLE:      FLG_FLY_TO_PLANET | FLG_SLOW,
    SHIP_TRANSPORTER:  FLG_FLY_TO_PLANET | FLG_SLOW,
    SHIP_COBRA3:       0,
    SHIP_PYTHON:       0,
    SHIP_BOA:          0,
    SHIP_ANACONDA:     FLG_SLOW,
    SHIP_HERMIT:       FLG_SLOW,
    SHIP_VIPER:        FLG_BOLD | FLG_POLICE,
    SHIP_SIDEWINDER:   FLG_BOLD | FLG_ANGRY,
    SHIP_MAMBA:        FLG_BOLD | FLG_ANGRY,
    SHIP_KRAIT:        FLG_BOLD | FLG_ANGRY,
    SHIP_ADDER:        FLG_BOLD | FLG_ANGRY,
    SHIP_GECKO:        FLG_BOLD | FLG_ANGRY,
    SHIP_COBRA1:       FLG_BOLD | FLG_ANGRY,
    SHIP_WORM:         FLG_SLOW | FLG_ANGRY,
    SHIP_COBRA3_LONE:  FLG_BOLD | FLG_ANGRY,
    SHIP_ASP2:         FLG_BOLD | FLG_ANGRY,
    SHIP_PYTHON_LONE:  FLG_BOLD | FLG_ANGRY,
    SHIP_FER_DE_LANCE: FLG_POLICE,
    SHIP_MORAY:        FLG_BOLD | FLG_ANGRY,
    SHIP_THARGON:      FLG_ANGRY | FLG_ALIEN,
    SHIP_THARGOID:     FLG_BOLD | FLG_ANGRY | FLG_ALIEN,
    SHIP_CONSTRICTOR:  FLG_ANGRY,
    SHIP_COUGAR:       FLG_POLICE | FLG_CLOAKED,
    SHIP_DODEC:        FLG_STATION,
    SHIP_STATIONV:     FLG_STATION,
    SHIP_PLANET:       FLG_PLANET
}

# In Python, we usually map these to class references or data dictionaries
SHIP_DICT = {
    "PLANET": -1,
    "SUN": -2,
    "None": 0,
    "MISSILE": 1,
    "CORIOLIS": 2,
    "ESCAPE_POD": 3,
    "PLATE": 4,
    "CANISTER": 5,
    "BOULDER": 6,
    "ASTEROID": 7,
    "SPLINTER":  8,
    "SHUTTLE": 9,  # (Orbit)
    "TRANSPORTER": 10,
    "COBRA_MK_3": 11,
    "PYTHON": 12,
    "BOA": 13,
    "ANACONDA": 14,
    "ROCK_HERMIT": 15,
    "VIPER": 16,
    "SIDEWINDER": 17,
    "MAMBA": 18,
    "KRAIT": 19,
    "ADDER": 20,
    "GECKO": 21,
    "COBRA_MK_1": 22,
    "WORM": 23,
    "COBRA_MK_3_P": 24,
    "ASP_MK_2": 25,
    "PYTHON_P": 26,
    "FER_DE_LANCE": 27,
    "MORAY": 28,
    "THARGOID": 29,
    "THARGON": 30,
    "CONSTRICTOR": 31,
    "COUGAR": 32,
    "DODO": 33,
    "STATIONV": 34
}


if __name__ == '__main__':
    print(GAME_W, GAME_H)
    print(f'{TOP_RECT=}')
    print(f'{FLIGHT_RECT=}')
    print(f'{HUD_RECT=}')
    print(f'{SCANNER_RECT=}')
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    
    # Create a figure and an axes
    fig, ax = plt.subplots()
    
    # Create a Rectangle patch
    # Rectangle((x, y), width, height, angle=0.0, **kwargs)
    rect = patches.Rectangle(TOP_RECT.origin, *TOP_RECT.size, linewidth=BORDER, edgecolor='r', facecolor='none')
    rect2 = patches.Rectangle(FLIGHT_RECT.origin, *FLIGHT_RECT.size, linewidth=BORDER, edgecolor='g', facecolor='none')
    rect3 = patches.Rectangle(HUD_RECT.origin, *HUD_RECT.size, linewidth=BORDER, edgecolor='b', facecolor='none')
    rect4 = patches.Rectangle(SCANNER_RECT.origin, *SCANNER_RECT.size, linewidth=BORDER, edgecolor='b', facecolor='none')
    hud_left = patches.Rectangle(HUD_LEFT.origin,  *HUD_LEFT.size, linewidth=BORDER, edgecolor='r', facecolor='none')
    hud_right = patches.Rectangle(HUD_RIGHT.origin, *HUD_RIGHT.size, linewidth=BORDER, edgecolor='r', facecolor='none')
    hud_centre = patches.Rectangle(HUD_CENTRE.origin, *HUD_CENTRE.size, linewidth=BORDER, edgecolor='black', facecolor='none')
    joy1 = patches.Circle(JOYSTICK_1_POSITION, JOYSTICK_1_RADIUS)
    joy2 = patches.Circle(JOYSTICK_2_POSITION, JOYSTICK_2_RADIUS)
    fire = patches.Circle(FIRE_BUTTON_RECT.origin, FIRE_BUTTON_RECT.w/2, facecolor='red')
    keyboard = patches.Rectangle(KEYBOARD_RECT.origin, *KEYBOARD_RECT.size, linewidth=BORDER, edgecolor='black', facecolor='none')
    # Add the patch to the Axes
    ax.add_patch(rect)
    ax.add_patch(rect2)
    ax.add_patch(rect3)
    ax.add_patch(rect4)
    ax.add_patch(hud_left)
    ax.add_patch(hud_right)
    ax.add_patch(hud_centre)
    ax.add_patch(joy1)
    ax.add_patch(joy2)
    ax.add_patch(fire)
    ax.add_patch(keyboard)
    cx, cy = FLIGHT_RECT.center()
    # Add Cross at FLIGHT_RECT.centre()
    ax.plot(cx, cy, 'x', color='black', markersize=10, markeredgewidth=2)
    # Set axis limits to ensure the rectangle is visible
    ax.set_xlim(0, W)
    ax.set_ylim(0, GAME_H)
    for i in range(NUM_LINES):
        # ax.text(x, y, "String", fontsize, ha='horizontal_alignment')
        x = TEXT_START_X
        y = GAME_H - TEXT_START_Y - TEXT_Y_INCR * i
        ax.text(x, y, str(i), fontsize=FONT_H/3, fontweight='bold', ha='left', va='top', color='darkblue')
     
    # Add labels and title
    ax.set_xlabel('X axis')
    ax.set_ylabel('Y axis')
    ax.set_title('ELITE Areas')
    
    # Save the plot
    plt.show()
