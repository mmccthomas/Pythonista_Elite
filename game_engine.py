# Author: Darron Vanaria
# Filesize: 23344 bytes
# LOC: 543

# GAME ENGINE: SurfaceController, Clock, TextGridArray, init()
#
#    Surfaces: 1. window_surface (may change resolution and fullscreen)
#              2. game_surface (filled color rectangle) subsurface of 1
#

import scene
import math  # for vector mathematics
import sound
import ui
import constants as cs
from image_helpers import set_colorkey, pil_to_ui


##############################################################################
# SOUND
#
class SoundComponent:

    def __init__(self):

        self.music_list = []
        
        self.music = None

        self.sound_effect_dict = {}
        

        self.current_volume = 0.1
        
        self.add_all_sound_effects()
        
    def add_all_sound_effects(self):
            
        for name, filename in cs.sounds.items():
            self.add_sound_effect(name, filename)
        self.add_music('sounds/title_music.wav')
        
    def add_sound_effect(self, name, filename):

        s = sound.Player(filename)

        s.volume = self.current_volume

        self.sound_effect_dict[name] = s

        return len(self.sound_effect_dict)

    def change_volume_sound_fx(self, new_vol):

        self.current_volume = new_vol

        if self.current_volume < 0:
            self.current_volume = 0
        if self.current_volume > 1:
            self.current_volume = 1

        for v in self.sound_effect_dict.values():
            v.volume = self.current_volume
            
    @ui.in_background
    def play_sound_effect(self, name):
        s = sound.play_effect(name)
       
        

    def add_music(self, filename):

        self.music_list.append(filename)

        return len(self.music_list)

    def play_music(self, index):

        self.music = sound.Player(self.music_list[index-1])
        self.music.volume = 0.5
        self.music.number_of_loops = -1

    def stop_music(self):
        if self.music:
            self.music.stop()
            
    def play_midi(self, filename):
        self.midi = sound.MIDIPlayer(filename)
        self.midi.play()
        
    def stop_midi(self):
        if self.midi:
            self.midi.stop()
                 

##############################################################################
# TEXT COMPONENTS (this is mostly used internally by the game engine)
#


class TextGridArray(scene.Node):

    # this object holds all the characters on a given "screen".
    # you can use multiple objects for different screens and retain in memory.
    WHITE_SQUARE = 5
    
    def __init__(self, w, h):

        # (w,h) are how many characters will fit on the surface that will be
        # used to draw on (passed directly to the draw() function).

        self.text_group = []
        self.font_manager = FontManager()

        self.GRID_WIDTH = w
        self.GRID_HEIGHT = h

        self.cursor_row = 0
        self.min_cursor_row = 0
        self.max_cursor_row = self.GRID_HEIGHT - 1

    def draw(self, parent):

        # this will add all Sprites in the text_group onto the supplied
        for text in self.text_group:
           # text.position = text.position.x, self.GRID_HEIGHT - text.position.y
           parent.add_child(text)

    def clear(self):
        # remove text sprites
        for text in self.text_group:
            text.remove_from_parent()

    def empty_container(self):
        for text in self.text_group:
            text.remove_from_parent()
        self.text_group = []
      
    def print(self, string, col, row, fg, bg=cs.BLACK, transparent=True):
        # transparent by default
        for count, c in enumerate(string):
            self.add_char(c, col + count, row, fg, bg, transparent)
    
    def print_centered(self, string, row, fg, bg=cs.BLACK, transparent=True):
        # transparent by default
        # calculate number of columns for font size
        length = (cs.GAME_W - 2 * cs.BORDER) / cs.FONT_W
        # pad string both ends to length
        string = f'{string:^{length}}'
        col = 1
        for count, c in enumerate(string):
            self.add_char(c, col + count, row, fg, bg, transparent)

    def unhighlight_row(self, row):
        # transparent again
        self.highlight_row(row, highlight_color=cs.BLACK, transparent=True)

    def highlight_row(self, row, highlight_color, transparent=False):
        # not transparent by default
        # this will only highlight existing characters in this row
        cells = [cell for cell in self.text_group if cell.r == row]
        for cell in cells:
            cell.bg_color = highlight_color
            cell.back.alpha = int(not transparent)
                
    def move_cursor(self, direction):

        new_loc = self.cursor_row + direction
        if new_loc >= self.min_cursor_row and new_loc <= self.max_cursor_row:
            self.cursor_row += direction

    # private
    def add_char(self, char, c, r, fg, bg, transparent=True):
       
        if c < 0 or c >= self.GRID_WIDTH:
            return
        if r < 0 or c >= self.GRID_WIDTH:
            return

        glyph = self.font_manager.get_glyph_copy(char)
        back_glyph = self.font_manager.get_glyph_by_index(self.WHITE_SQUARE)
        
        letter = TextCell(char, glyph, c, r, fg, bg, transparent, back_glyph)
        
        # check if there is already an existing character at this
        # location, if there is, remove the old object (3rd argument)
        
        # TODO does this need to change if centred?
        # 1. Define a small margin to prevent 'crowding'
        collision_margin = -2, -2  # Negative shrinks the hit-box, Positive expands it
        
        # 2. Use a list comprehension for atomicity and speed
        # This creates a new list without the overlapping elements
        text_to_delete = [text for text in self.text_group
                          if text.frame.inset(*collision_margin).intersects(letter.frame)
                          ]
        self.text_group = [
            text for text in self.text_group
            if not text.frame.inset(*collision_margin).intersects(letter.frame)
        ]
        for text in text_to_delete:
            text.remove_from_parent()
        self.text_group.append(letter)
        
    def add_char_by_index(self, index, c, r, fg, bg, transparent=True):
        if c < 0 or c >= self.GRID_WIDTH:
            return
        if r < 0 or c >= self.GRID_WIDTH:
            return
                
        glyph = self.font_manager.get_glyph_by_index(index)
        back_glyph = self.font_manager.get_glyph_by_index(self.WHITE_SQUARE)
        char = 'SPECIAL'

        letter = TextCell(char, glyph, c, r, fg, bg, transparent, back_glyph)
       
        # check if there is already an existing character at this
        # location, if there is, remove the old object
        # TODO does this need to change if centred?
        for text in self.text_group[:]:
            if text.frame.intersects(letter.frame):
                self.text_group.remove(text)
        self.text_group.append(letter)

    def add_file_contents(self, filename, fg, bg, transparent=False):
     
        self.add_file_contents_at(self, filename, 0, 0, fg, bg, transparent=True)
    
    def add_file_contents_at(self, filename, row, col, fg, bg, transparent=True):

        # all text source files must end with the word 'END'
        with open(filename, 'r') as f:
            lines = []
            line = f.readline()
            while line != 'END':
                lines.append(line)
                line = f.readline()

        # parse "lines" and add a new String for each
        for line in lines:
            self.print(line, col, row, fg, bg, transparent)
            row += 1


def swap_colors(sprite, original_color, replacement_color):
     
    sprite.color = replacement_color

        
# private to game engine #####################################################

class TextCell(scene.Node):
    # Node built from two sprites built from Texture glyph  (with specific colors)
    
    def __init__(self, char, glyph, c, r, fg, bg, isTransparent, back_glyph=None):
        super().__init__()
        self.size = (cs.FONT_W, cs.FONT_H)
        self.name = 'Letter'
        self.char = char
        self.c = c
        self.r = r
        self.fg = fg
        self.bg = bg
        self.isTransparent = isTransparent
        
        self.letter = scene.SpriteNode(glyph, position=(0, 0))
        self.letter.color = fg
        self.letter.color_blend_factor = 1.0
        self.letter.z_position = 10
        self.letter.size = self.size
        self.add_child(self.letter)
                           
        # 1. Create the background (a simple white square tinted)
        self.back = scene.SpriteNode(back_glyph, position=(0, 0))
        self.back.z_position = 9
        self.back.color = bg
        self.back.alpha = int(not isTransparent)
        self.back.size = self.size
        # self.back.color_blend_factor = 1.0
        self.add_child(self.back)
            
        x = cs.TEXT_X_INCR * c + cs.TEXT_START_X
        # invert as (0,0) is bottom left in Scene
        y = cs.GAME_H - cs.TEXT_Y_INCR * r - cs.TEXT_START_Y
        self.position = (x, y)

    @property
    def bg_color(self):
        return self.back.color
         
    @bg_color.setter
    def bg_color(self, newcolor):
        self.back.color = newcolor
        self.back.alpha = 1
                 

class FontManager():

    # This class will be used to load a single .png file that contains all
    # 128 characters (bitmaps) in an ASCII font set. It then builds a list of
    # subsurfaces (this list has 128 indices, 0 to 127).
    #
    # A function will be available that makes a copy of a given glyph and
    # returns the copy. The copy can be modified freely (changing colors for
    # example). This will allow multiple copies of the same glyph to be
    # manipulated independently.
    FONT_FILE = 'c64_font_size_3.png'
    FONT_WIDTH = 16
    FONT_HEIGHT = 16
    GLYPHS_ACROSS = 16
    GLYPHS_DOWN = 8
    
    def __init__(self):
        spritesheet = set_colorkey(self.FONT_FILE)
        
        self.font_set_master_surface = scene.Texture(pil_to_ui(spritesheet))
        self.master_glyph_set = []
        self.build_master_glyph_set()
        
    def build_master_glyph_set(self):
        w, h = self.font_set_master_surface.size
        
        # Calculate normalized dimensions once
        nw = self.FONT_WIDTH / w
        nh = self.FONT_HEIGHT / h
        
        # 0.5 pixel offset in normalized (0.0 - 1.0) space
        # This ensures we sample from the center of the pixels, not the edges.
        ox = 0.33 / w
        oy = 0.33 / h
    
        for i in range(self.GLYPHS_ACROSS * self.GLYPHS_DOWN):
            col = i % self.GLYPHS_ACROSS
            row = int(i / self.GLYPHS_ACROSS)
            
            # x is straightforward: move right per column
            x = col * nw
            
            # y starts at the top (1.0) and moves down
            # We subtract (row + 1) to get the BOTTOM-left corner of the character cell.
            y = 1.0 - ((row + 1) * nh)
            
            # Apply the inset:
            # Shift the origin (x, y) slightly 'in'
            # and shrink the width/height (w, h) by twice that amount
            safe_rect = scene.Rect(x + ox, y + oy,
                                   nw - (ox * 2), nh - (oy * 2))
            
            t = self.font_set_master_surface.subtexture(safe_rect)
            self.master_glyph_set.append(t)
                                                                
    def get_glyph_copy(self, char):

        # Python built-in function ord('a') returns the ASCII index 97
        index = ord(char)
        return self.master_glyph_set[index]
    
    def get_glyph_by_index(self, index):

        return self.master_glyph_set[index]


# Enhanced Point class for Elite Flatland
#
# Extends the Pythonista scene.Point with arithmetic operators.
# Supports point OP point and point OP scalar for all operations.

class Point2():
    """
    a class similar to scene.Point extended with arithmetic operators.
    need to avoid name clash with scene.Point

    Supports:
        point OP point   - element-wise operation
        point OP scalar  - scalar broadcast
        scalar OP point  - reflected scalar broadcast (where sensible)

    All operations return a new Point2.
    """
    def __init__(self, x, y):

        self.x = x
        self.y = y
                
    # contained within rectangle
    def in_rect(self, rect):
        if self.x < rect[0]:
           return False
        if self.y < rect[1]:
           return False
        if self.x > rect[0] + rect[2]:
           return False
        if self.y > rect[1] + rect[3]:
           return False
        return True
    # ── addition ──────────────────────────────────────────────────────────────

    def __add__(self, other):
        if isinstance(other, Point2):
            return Point2(self.x + other.x, self.y + other.y)
        return Point2(self.x + other, self.y + other)

    def __radd__(self, other):
        return Point2(other + self.x, other + self.y)

    # ── subtraction ───────────────────────────────────────────────────────────

    def __sub__(self, other):
        if isinstance(other, Point2):
            return Point2(self.x - other.x, self.y - other.y)
        return Point2(self.x - other, self.y - other)

    def __rsub__(self, other):
        return Point2(other - self.x, other - self.y)

    # ── multiplication ────────────────────────────────────────────────────────

    def __mul__(self, other):
        if isinstance(other, Point2):
            return Point2(self.x * other.x, self.y * other.y)
        return Point2(self.x * other, self.y * other)

    def __rmul__(self, other):
        return Point2(other * self.x, other * self.y)

    # ── division (true) ───────────────────────────────────────────────────────

    def __truediv__(self, other):
        if isinstance(other, Point2):
            return Point2(self.x / other.x, self.y / other.y)
        return Point2(self.x / other, self.y / other)

    def __rtruediv__(self, other):
        return Point2(other / self.x, other / self.y)

    # ── floor division ────────────────────────────────────────────────────────

    def __floordiv__(self, other):
        if isinstance(other, Point2):
            return Point2(int(self.x // other.x), int(self.y // other.y))
        return Point2(int(self.x // other), int(self.y // other))

    def __rfloordiv__(self, other):
        return Point2(int(other // self.x), int(other // self.y))

    # ── modulo ────────────────────────────────────────────────────────────────

    def __mod__(self, other):
        if isinstance(other, Point2):
            return Point2(self.x % other.x, self.y % other.y)
        return Point2(self.x % other, self.y % other)

    def __rmod__(self, other):
        return Point2(other % self.x, other % self.y)

    # ── negation ──────────────────────────────────────────────────────────────

    def __neg__(self):
        return Point2(-self.x, -self.y)

    # ── in-place operators (return new Point2 to stay immutable-friendly) ──────

    def __iadd__(self, other): return self.__add__(other)
    def __isub__(self, other): return self.__sub__(other)
    def __imul__(self, other): return self.__mul__(other)
    def __itruediv__(self, other): return self.__truediv__(other)
    def __ifloordiv__(self, other): return self.__floordiv__(other)
    def __imod__(self, other): return self.__mod__(other)

    # ── equality ──────────────────────────────────────────────────────────────

    def __eq__(self, other):
        if isinstance(other, Point2):
            return self.x == other.x and self.y == other.y
        return NotImplemented

    def __hash__(self):
        return hash((self.x, self.y))

    # ── repr ──────────────────────────────────────────────────────────────────

    def __repr__(self):
        return f"Point2({self.x}, {self.y})"

    # ── convenience helpers ───────────────────────────────────────────────────

    def floor(self):
        """Return a new Point2 with both components floor-divided to int."""
        return Point2(int(self.x), int(self.y))
        
    def round(self):
        """Return a new Point2 with both components rounded to int."""
        return Point2(int(self.x + 0.5), int(self.y + 0.5))
         
    def as_tuple(self):
        """Return (x, y) as a plain tuple."""
        return (self.x, self.y)

    def lerp(self, other, t: float):
        """Linear interpolation towards other by factor t (0=self, 1=other)."""
        return Point2(self.x + (other.x - self.x) * t,
                      self.y + (other.y - self.y) * t)
                    
    def hypot(self):
        return math.sqrt(self.x * self.x + self.y * self.y)


# Size2 is a synonym for Point2
Size2 = Point2
# end of private to game engine ##############################################


class DebugScene(scene.Scene):
       
    def setup(self):
       self.glyphs = []
       self.background_color = 'green'
       self.tpg = TextGridArray(1000, 800)
           
    def update_(self):
      for child in self.children:
          child.remove_from_parent()
      text = 'The quick brown fox jumped over the lazy dog'
      self.tpg.print_centered(text, 5, cs.WHITE, cs.BLACK, transparent=False)
      self.tpg.print(text, 2, 6, cs.BLACK, cs.YELLOW, transparent=True)
      
      self.tpg.draw(self)
      # self.tpg.highlight_row(5, cs.RED)
      

# Test Suite #################################################################


def main():
    print()
    print(' Test of module game_engine.py...')
        
    f = FontManager()
    print(f.master_glyph_set[1])
    
    # g = DebugScene()
    
    # scene.run(g)
    # for i, glyph in enumerate(f.master_glyph_set):
    #   g.glyphs.append((glyph, i // 16, i % 16))
    # g.update_()


sounder = SoundComponent()

if __name__ == '__main__':
  main()
