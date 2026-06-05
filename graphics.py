# provide low level line and text items
# return items are for testing

# Dealing with text:
# Text are SpriteNodes, so we dont want to keep deleting and adding them
# on each iteration of the fame loop, 60 times per second
# so store the screen character positions as 3d numpy array with 3 layers
# to allow  single array, store as integers
# layer 0 is ord(character)
# layer 1 is integer representsion of text colour
# layer 2 is integer representsion of background colour. if it is black, it will be rendered as transparent

# printing characters update the array
# at the end of the screen we test against last rendered page.
# if its the same (including colour or background), do nothing
# if its different, delete all the sprites and add them again.
# each screen will need a clear and text render at start and end
# this will all be super quick.

# all lines and circles will be rendered using scene drawing, as they are small overhead on
# wireframe drawing

import game_engine
from constants import logger
import ui
import scene
import constants as cs
import matplotlib.colors as mcolors
import numpy as np
import textwrap
from PIL import Image
import pathlib

CHAR = 0
FG = 1
BG = 2


def _clip_line(x1, y1, x2, y2, x_min, y_min, x_max, y_max):
    """Liang-Barsky line clip. Returns clipped (x1,y1,x2,y2) or None."""
    dx, dy = x2 - x1, y2 - y1
    p = [-dx, dx, -dy, dy]
    # first point offset from max
    q = [x1 - x_min, x_max - x1, y1 - y_min, y_max - y1]
    t0, t1 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return None       # parallel and outside
        elif pi < 0:
            t0 = max(t0, qi / pi)
        else:
            t1 = min(t1, qi / pi)
    if t0 > t1:
        return None
    return np.array((x1 + t0*dx, y1 + t0*dy,
                     x1 + t1*dx, y1 + t1*dy))


def _clip_circle_segments(cx, cy, r, rect, n=100):
    # rect = (x, y, w, h)
    xmin, ymin, w, h = rect
    xmax, ymax = xmin + w, ymin + h
    
    # 1. Generate full circle points
    theta = np.linspace(0, 2*np.pi, n + 1)
    x = cx + r * np.cos(theta)
    y = cy + r * np.sin(theta)
    points = np.column_stack((x, y))
    
    # 2. Identify points inside the rectangle
    inside = (points[:, 0] >= xmin) & (points[:, 0] <= xmax) & \
             (points[:, 1] >= ymin) & (points[:, 1] <= ymax)
    
    segments = []
    for i in range(len(points) - 1):
        p1, p2 = points[i], points[i+1]
        in1, in2 = inside[i], inside[i+1]
        
        if in1 and in2:
            # Both points inside: keep the whole segment
            segments.append(np.concatenate([p1, p2]))
        elif in1 or in2:
            # One point inside, one out: Calculate intersection
            # This is a simplified "clipping" by snapping to the boundary
            p1_clipped = np.clip(p1, [xmin, ymin], [xmax, ymax])
            p2_clipped = np.clip(p2, [xmin, ymin], [xmax, ymax])
            
            # Only add if the segment still has length
            if not np.array_equal(p1_clipped, p2_clipped):
                segments.append(np.concatenate([p1_clipped, p2_clipped]))
                
    return np.array(segments) if segments else np.empty((0, 4))


class Graphics():
    
    def __init__(self, parent_scene):
     
       self.parent_scene = parent_scene
       if parent_scene:
           self.screen = self.parent_scene.background
       
       # this object holds all the characters on a given "screen".
       # you can use multiple objects for different screens and retain in memory.
       # text grid is a \node which hold multiple caracters
       self.text_grid = game_engine.TextGridArray(cs.GAME_W, cs.GAME_W)
       self.screen_rect = cs.FLIGHT_RECT
       self.centre_screen = self.screen_rect.center()
       self.X_CENTRE, self.Y_CENTRE = self.centre_screen
       
       # page_text is a 3d array holding ascii_code, color_of text, color of background
       # this allows instant comparison, and iteration
       
       # page_text is last rendered page
       self.page_text = np.zeros((3, cs.NUM_LINES, cs.TEXT_LENGTH), dtype=int)
       
       # 2. Define your fill pattern
       # We reshape it to (3, 1, 1) so it aligns with your (3, Lines, Length) shape
       self.fill_pattern = np.array([32, 0, 0]).reshape(3, 1, 1)
       self.page_text[:] = self.fill_pattern
       
       # current_text is this page WIP
       self.current_text = np.zeros_like(self.page_text)
       self.current_text[:] = self.fill_pattern
       
       self.set_clip_region(*cs.FLIGHT_RECT)
       
    # ------- Text Handling
    
    def to_color_int(self, color):
        """
        Converts hex, names, or tuples to a 24-bit integer using Matplotlib.
        to_rgb handles 'white', '#ffffff', and (1,1,1) automatically
        """
        rgb_normalized = mcolors.to_rgb(color)
        r, g, b = [int(x * 255) for x in rgb_normalized]
        return (r << 16) + (g << 8) + b
        
    def int_to_rgb(self, color_int):
        """ Converts a 24-bit integer back to a (0-255) RGB tuple"""
        r = (color_int >> 16) & 255
        g = (color_int >> 8) & 255
        b = color_int & 255
        return (r, g, b)
        
    def is_empty_text(self, row, col, length):
        try:
            return np.all([c == 32 for c in self.current_text[0][row][col-1:col+length]])
        except (ValueError, IndexError):
            # doesnt fit so skip
            return False
            
    def replace_text_section(self, r, c, text, color=cs.BLACK, background=cs.BLACK):
        """replace a section of ndarray board with replacement ndarray
        r, c: starting coordinates
        """
        if r < 0 or c < 0:
            return
        # constuct a list of character number, text colour, background colour
        new_text = np.array([[ord(char),
                              self.to_color_int(color),
                              self.to_color_int(background)]
                             for char in text])
        try:
            self.current_text[:, r, c: c + new_text.shape[0]] = new_text.T
        except (ValueError, IndexError):
            # doesnt fit so skip
            pass
          
    def clear_display(self):
       # clear the current WIP array
       self.current_text = np.zeros_like(self.page_text)
       self.current_text[:] = self.fill_pattern

    def update_screen(self):
        pass  # DRAW: present/flip the frame buffer
        self.text_render()
        
    def display_centre_text(self, row, text, size=120, color=cs.WHITE):
        """Renders text centered horizontally on the screen.
           In game engine, letters are anchored to bottom left
           write text into self.current_text array centred on screen
           Font sizing is not neccesary, only used in title bar, values were 120 or 140"""
                    
        # pad string both ends to length
        self.replace_text_section(row, 0, f'{text:^{cs.TEXT_LENGTH}}', color=color)
    
    def display_text(self, col, row, text, size=120, color=cs.WHITE):
        # write text into self.current_text array
        self.replace_text_section(row, col, text, color=color)
    
    def display_colour_text(self, col, row, text, size=120, color=cs.WHITE):
        self.display_text(col, row, text, size, color)
    
    def display_pretty_text(self, tx, ty, txt):
        """
        Word-wraps text within a specified box.
        This is a Pythonic replacement for the C pointer-shuffling logic.
        only used in missions
        text is at ty, ignore tx for now
        use wordwrap
        we get a list of strings. print them centred
        """
        wrapped_text = textwrap.wrap(txt, width=(cs.TEXT_LENGTH))
        
        for line_no, textline in enumerate(wrapped_text):
            self.display_centre_text(line_no + ty, textline)
            
    def draw_rectangle(self, col, row, width, height, color):
       # used to highlight section of line(s)
       self.current_text[2, row: row + height, col: col + width] = self.to_color_int(color)
       highlights = np.argwhere(self.current_text[BG])
       str_list = [f"({x},{y})" for x, y in highlights]
       logger.debug((" | ".join(str_list)))
         
    def highlight(self, row, color):
        # highlight entire row
        self.current_text[BG, row, :] = self.to_color_int(color)
             
    def _clear_text_area(self, sprites_only=False):
       
        try:
            for t in self.text_grid.text_group:
                t.remove_from_parent()
            if not sprites_only:
                self.text_grid.text_group = []
        except (NameError, AttributeError):
            pass
 
    def text_render(self):
        # clear the screen of sprites and write new ones if screen data changed
        # if text is unchanged, leave it alone
        if np.array_equal(self.page_text, self.current_text):
            return
            
        self._clear_text_area(sprites_only=False)
        try:
            # Get indices where the character is not a space
            indices = np.argwhere(self.current_text[0] != 32)
            for r, c in indices:
                # Extract values for this specific cell
                char = chr(self.current_text[CHAR, r, c])
                fg_val = self.int_to_rgb(self.current_text[FG, r, c])
                bg_val = self.int_to_rgb(self.current_text[BG, r, c])
                transparent = self.current_text[BG, r, c] == 0
                self.text_grid.add_char(char, c, r, fg_val, bg_val, transparent)
            try:
                # this structure is not recommended, but allows stepping over when debugging
                [self.screen.add_child(text_cell) for text_cell in self.text_grid.text_group]
            except AttributeError:
                pass
                # no screen in testing
            
            # store the updated screen
            self.page_text = self.current_text.copy()
       
            rows = [''.join([chr(char) for char in line]) for line in self.page_text[CHAR]]
            # logger.debug("\n".join(rows))
            
        except (AttributeError, NameError) as e:
            logger.debug(e)
                     
    # -------- Line Drawing
                
    def set_clip_region(self, x, y, w, h):
        # DRAW: set clipping rectangle
        # this should stop any of the line, ellipse from plotting outside frame
        x1, y1, x2, y2 = x, y, x + w, y + h
        self.clip_region = (x1, y1, x2, y2)
        # line would not draw if outside
        # circle woukd turn into an arc
        
    def _in_clip_region(self, x, y):
        x1, y1, x2, y2 = self.clip_region
        return x1 <= x <= x2 and y1 <= y <= y2
        
    def plot_pixel(self, x, y, color, size=1):
       # draw a small pixel, usually 1 pixel size
       # it can be large but is not clipped
       if self._in_clip_region(x, y):
           scene.fill(color)
           scene.stroke(color)
           scene.rect(0, 0, 0, 0)  # for bug
           if size == 1:
               scene.rect(x, y, size, size)
           else:
               scene.ellipse(x - size/2, y - size/2, size, size)
           return x, y
           
    def draw_line(self, x1, y1, x2, y2, colour=cs.WHITE, width=2):
        # DRAW: draw line from (x1,y1) to (x2,y2) in colour
        # use scene drawing as it will be updated every frame
        clipped = _clip_line(x1, y1, x2, y2, *self.clip_region)
        if clipped is not None:
            scene.stroke(colour)
            scene.rect(0, 0, 0, 0)
            scene.stroke_weight(width)
            scene.line(*clipped)
        return clipped
        
    def draw_colour_line(self, x1, y1, x2, y2, colour, width=2):
        clipped = self.draw_line(x1, y1, x2, y2, colour, width)
        return clipped
           
    def draw_circle(self, cx, cy, radius, colour, n=50, width=2):
        # draw circle outline centred on cx, cy
        # use scene drawing as it will be updated every frame
        clipped = _clip_circle_segments(cx, cy, radius, self.clip_region, n=n)
        if clipped is not None:
           scene.stroke(colour)
           scene.rect(0, 0, 0, 0)
           scene.stroke_weight(width)
           for segment in clipped:
               x1, y1, x2, y2 = segment
               scene.line(*segment)
        return clipped
                
    def draw_filled_polygon(self, points, color, width=2):
        # points is (c1, y1, x2, y2)
        # use scene drawing as it will be ipdated every frame
        points = np.array(points)
        scene.stroke(color)
        scene.rect(0, 0, 0, 0)
        scene.stroke_weight(width)
        # Reshape into (N, 4) where each row is [x1, y1, x2, y2]
        segments = points.reshape(-1, 4)
        clipped_lines = []
        for seg in segments:
            clipped = _clip_line(*seg, *self.clip_region)
            if clipped is not None:
                clipped_lines.append(clipped)
                scene.line(*clipped)
        return np.array(clipped_lines)
            
    def draw_sprite(self, image_name, x=0, y=0, w=None, h=None):  # x, y relative to flight screen center
        # image = set_colorkey(image_name)  # make transparent
        image = Image.open(pathlib.Path('images',  image_name))
        if w is None:
          w, h = image.size
        scene.image(image_name, x, y, w*3, h*3)
        
        # sprite = SpriteNode(Texture(pil_to_ui(image)),
        #                    position=self.centre_screen + Point(x, y))
        # if self.parent_scene:
        #    self.screen.add_child(sprite)
        
    # -----------Animations
    def launch_animation(self):
        A = scene.Action
        path = ui.Path()
        path.line_width = 1
        for i in range(1, 10):
            path.append_path(ui.Path.rect(-i*5, -i*2.5, i*10, i*5))
        self.rect_node = scene.ShapeNode(path,
                                         fill_color='clear',
                                         stroke_color=cs.RED,
                                         # line_width=1,
                                         position=self.centre_screen,
                                         parent=self.screen)
        # 3. Define the Resize Action
        self.rect_node.run_action(A.sequence(
                                     A.scale_to(20, 2, scene.TIMING_EASE_IN_OUT),
                                     A.remove()))
  
    # --------Planet Finder
    def list_files(self, file_list, prompt='Choose Planet Name'):
        # used in place of keyboard-based find planet function
        from dialogs import list_dialog
        return list_dialog(prompt, items=file_list)
       
    def enter_text(self, prompt='Choose Name'):
        # used in place of keyboard-based  function
        from console import input_alert
        return input_alert("Text")
        
    def ask_yes_no_(self, prompt=''):
        # used in place of keyboard-based  function
        from console import alert
        return alert(prompt, '', 'OK')
               
    # --------Unused methods
    def start_render(self):
        pass
        
    def finish_render(self):
        pass
    
    def request_file(self, title, default_path, extension):
        # UI: show a file picker; return (ok, path)
        return False, default_path
    
    def clear_area(self, *args):
        return

                                                                                          
# ------- Test
def test():
    from matplotlib import pyplot as plt
    from matplotlib.collections import LineCollection
    import matplotlib.patches as patches
    m1_brief_a = (
            "Greetings Commander, I am Captain Curruthers of "
            "Her Majesty's Space Navy and I beg a moment of your "
            "valuable time. We would like you to do a little job "
            "for us. The ship you see here is a new model, the "
            "Constrictor, equiped with a top secret new shield "
            "generator. Unfortunately it's been stolen."
        )
    graphic = Graphics(None)

    graphic.display_centre_text(0, 'abc123')
    graphic.display_centre_text(6, 'To be or not to be')
    graphic.display_text(0, 8, 'That is the question')
    graphic.display_pretty_text(0, 3, m1_brief_a)
    graphic.draw_rectangle(0, 7, 20, 1, cs.DARK_RED)
    graphic.text_render()
       
    graphic.set_clip_region(*cs.FLIGHT_RECT)
    line = graphic.draw_colour_line(100, 110, 200, 200, cs.BLACK)
    print(line)
    line = graphic.draw_colour_line(90, 110, 200, 200, cs.BLACK)
    print(line)
    
    fig, ax = plt.subplots()
    # You must set limits manually when using collections
    ax.set_xlim(0, cs.W)
    ax.set_ylim(0, cs.H)
    # flight rect outline
    rect = patches.Rectangle(cs.FLIGHT_RECT.origin, *cs.FLIGHT_RECT.size, linewidth=cs.BORDER, edgecolor='g', facecolor='none')
    ax.add_patch(rect)
    
    for i in range(10):
        loc = graphic.plot_pixel(i * 20 + 700, 500, cs.MAGENTA, 6)
        if loc:
           ax.plot(*loc, 'ro', markersize=3)
    line = graphic.draw_colour_line(600, 110, 700, 200, cs.BLACK)
    lc_data = line.reshape(-1, 2, 2)
    lc = LineCollection(lc_data, colors=cs.RED, linewidths=2)
    
    ax.add_collection(lc)
    # full circle
    segments = graphic.draw_circle(200, 300, 100, cs.MAGENTA, n=50)
    # Assume 'segments' is your (N, 4) array from the Liang-Barsky clip
    # We need to reshape it to (N, 2, 2) which is [(x1,y1), (x2,y2)]
    lc_data = segments.reshape(-1, 2, 2)
    lc = LineCollection(lc_data, colors=cs.RED, linewidths=2)
    ax.add_collection(lc)
    
    # clipped circle
    segments = graphic.draw_circle(500, 150, 50, cs.BLACK, n=50)
    lc_data = segments.reshape(-1, 2, 2)
    lc = LineCollection(lc_data, colors=cs.BLUE, linewidths=2)
    ax.add_collection(lc)
    
    # triangle
    polygon = [[150, 150, 400, 400], [400, 400, 450, 150], [450, 150, 150, 150]]
    segments = graphic.draw_filled_polygon(polygon, cs.BLACK)
    lc_data = segments.reshape(-1, 2, 2)
    lc = LineCollection(lc_data, colors=cs.BLUE, linewidths=2)
    ax.add_collection(lc)
    
    # clipped triangle
    polygon = [[500, 650, 750, 650], [750, 650, 675, 800], [675, 800, 500, 650]]
    segments = graphic.draw_filled_polygon(polygon, cs.BLACK)
    lc_data = segments.reshape(-1, 2, 2)
    lc = LineCollection(lc_data, colors=cs.GREEN, linewidths=2)
    ax.add_collection(lc)
     
    plt.show()

        
if __name__ == '__main__':
  test()
    
    
    
      

