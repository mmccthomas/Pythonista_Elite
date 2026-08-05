# Author: Darron Vanaria
# Filesize: 24409 bytes
# LOC: 538
from scene import Rect,  Node, ShapeNode, Scene, run
import constants as cs
import ui
# from constants import logger
from image_helpers import set_colorkey, new_sprite
from change_screensize import get_screen_size

# scanner coordinates (120 x 90 pixels covers 3 x 3 sectors)
# scene.rect(0,0,0,0)SCANNER_SCALE = FLIGHT_WINDOW * 3 / SCANNER_SIZE
# COMPASS_SCALE = SYSTEM_SIZE / COMPASS_SIZE


class Scanner(Node):
 
   def __init__(self, width=400, height=300):
       super().__init__()
       try:
           width, height = cs.SCANNER_RECT.size
       except NameError:
           pass
       w, h = width, height
       self.width = width
       self.height = height
       # ratios for line placement
       x1 = 0.38
       x2, y2 = 0.3, 0.38
       x3, y3 = 0.15, 0.46
       
       # Center coordinates for placing major components
       self.center_x, self.center_y = w / 2, h / 2
       # 1. Main Black Background Panel (creates a mask effect)
       bg_panel = ShapeNode(ui.Path.rect(-w/2, -h/2, w, h),
                            fill_color="clear",
                            position=(0, 0),
                            z_position=-1)
       self.add_child(bg_panel)
       
       path = ui.Path()
       path.line_width = 2
       # 2. Main Radar Oval (large dashed green line)
       path.append_path(ui.Path.oval(-w/2, -h/2, w, h))
       # Use line_dash for the dotted look
       path.set_line_dash([5, 5])
       # 3. Horizontal lines

       path.move_to(-w/2, 0)
       path.line_to(w/2, 0)
       
       path.move_to(-x1 * w, h/3)
       path.line_to(x1 * w, h/3)

       path.move_to(-x1 * w, -h/3)
       path.line_to(x1 * w, -h/3)

       # Center Vertical Line
       path.move_to(0, -h/2)
       path.line_to(0, h/2)

       # slanted Vertical lines
       path.move_to(-x2 * w, y2 * h)
       path.line_to(-x3 * w, -y3 * h)

       path.move_to(x2 * w, y2 * h)
       path.line_to(x3 * w, -y3 * h)

       path.move_to(0, 0)
       path.line_to(-x3 * w, -y3 * h)

       path.move_to(0, 0)
       path.line_to(x3 * w, -y3 * h)
       
       outline = ShapeNode(path, stroke_color="#c0c0c0", fill_color='clear')
       outline.anchor_point = (0.5, 0.5)
       outline.z_position = 0
       self.add_child(outline)
       self.blips = []
      

class Compass(Node):
    # compasss should show position of planet.
    # yellow if in front, cyan if behind
    # when within suitable distance from planet, switches to
    # lock to station
    def __init__(self, width=70):
        # 6. Compass (The top-right 'L' shaped bracket and inset dots)
        # Compass Black Inset
        s = width
        self.width = width
        self.blips = []
        l1 = 0.1
        l2 = 0.2
        path = ui.Path()
        path.append_path(ui.Path.rect(0, 0, s, s))
        path.append_path(ui.Path.oval(0, 0, s, s))
        cx1, cy1 = s/2, s/2
        # cx1, cy1 = 0, 0
        path.move_to(cx1 - l2*s, cy1)
        path.line_to(cx1 - l1*s, cy1)
        path.move_to(cx1 + l2*s, cy1)
        path.line_to(cx1 + l1*s, cy1)
        
        path.move_to(cx1, cy1 - l2*s)
        path.line_to(cx1, cy1 - l1*s)
        path.move_to(cx1, cy1 + l2*s)
        path.line_to(cx1, cy1 + l1*s)
        outline = ShapeNode(path, stroke_color="#1aff1a", fill_color='clear')
        self.add_child(outline)
        self.z_position = 3

                        
class EliteScannerView(Scene):
 
    def setup(self):
        super().__init__()
        # Set a pure black background
        # self.background_color = "#000000"
        self.radar_node = Scanner(width=cs.SCANNER_RECT.w, height=cs.SCANNER_RECT.h)
        self.radar_node.z_position = 1
        self.theta = 0
        self.phi = 90
        # Adjust position slightly down from center
        self.radar_node.position = self.size.w/2, self.size.h/2
        self.add_child(self.radar_node)
        
        self.compass_node = Compass(width=cs.COMPASS_W)
        self.compass_node.z_position = 3
        self.compass_node.position = cs.COMPASS_X, cs.COMPASS_Y
        
        self.add_child(self.compass_node)
                              
    def update(self):
        pass


# parent of all items
class HudPanel(Node):

    def __init__(self):
        W, H = get_screen_size()
        hud_image = set_colorkey('hud_left_1.png')
        r = Rect(*cs.HUD_LEFT)
        left = new_sprite(hud_image,
                          # size=r.size,
                          position=r.origin,
                          anchor_point=(0, 0),
                          z_position=1,
                          scale=cs.HUD_SCALE,
                          parent=self)
        hud_image = set_colorkey('hud_right_1.png')
        r = Rect(*cs.HUD_RIGHT)
        right = new_sprite(hud_image,
                           # size=r.size,
                           position=(r.origin),
                           anchor_point=(0, 0),
                           z_posiition=1,
                           scale=cs.HUD_SCALE,
                           parent=self)
                                   
        self.name = 'hud_node'
        
        hud_image = set_colorkey('safe.bmp')
        self.safe_node = new_sprite(hud_image,
                                    # size=r.size,
                                    position=right.frame.origin - (10, -10),
                                    anchor_point=(1, 0),
                                    z_posiition=1,
                                    parent=self)
        self.name = 'safe'
        self.safe_node.alpha = 0
        
        hud_image = set_colorkey('ecm.bmp')
        self.ecm_node = new_sprite(hud_image,
                                   # size=r.size,
                                   position=(left.frame.max_x+10, left.frame.min_y+10),
                                   anchor_point=(0, 0),
                                   z_posiition=1,
                                   parent=self)
        self.name = 'ecm'
        self.color = cs.BLUE
        self.scanner = Scanner(*cs.SCANNER_RECT.size)
        self.scanner.position = cs.SCANNER_RECT.center()
        self.add_child(self.scanner)
        self.compass = Compass(width=cs.COMPASS_RECT.w)
        self.compass.position = cs.COMPASS_RECT.center()
        self.add_child(self.compass)



                
if __name__ == '__main__':
   # Start the scene
   g = EliteScannerView()
   # g.setup()
   #
   run(g, show_fps=False, multi_touch=False)
