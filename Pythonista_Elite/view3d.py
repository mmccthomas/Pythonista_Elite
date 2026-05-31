from scene import Point, stroke, stroke_weight, fill, line, no_stroke,ellipse
import math
from swat import UnivObject
import constants as cs
class IsometricCloud():
    def __init__(self, loc=Point(0,0)):
    
        # Configuration
        self.background_color = '#1a1a1a'
        self.scale = 0.001  # Adjust this to zoom in/out
        self.dot_size = 4
        self.loc = loc
        # Sample Data: List of (x, y, z) within range +/- 65535
        self.points = [
            (0, 0, 0), (65535, 0, 0), (0, 65535, 0), (0, 0, 65535),
            (65535, 65535, 65535), (32000, -32000, 10000), (-50000, 20000, -10000)
        ]
        self.objects = [UnivObject] * cs.MAX_UNIV_OBJECTS
        
        # Bounding Box corners for the wireframe
        high = 65535
        low = -65535
        self.box_edges = [
            ((low, low, low), (high, low, low)),
            ((high, low, low), (high, high, low)),
            ((high, high, low), (low, high, low)),
            ((low, high, low), (low, low, low)),
            ((low, low, high), (high, low, high)),
            ((high, low, high), (high, high, high)),
            ((high, high, high), (low, high, high)),
            ((low, high, high), (low, low, high)),
            ((low, low, low), (low, low, high)),
            ((high, low, low), (high, low, high)),
            ((high, high, low), (high, high, high)),
            ((low, high, low), (low, high, high))
        ]

    def project(self, x, y, z):
        """Converts 3D coordinates to 2D isometric screen coordinates."""
        # Standard isometric angles
        cos_20 = 0.93969 #0.866
        sin_20 = 0.342 # 0.5
        
        # Apply scale
        sx, sy, sz = x * self.scale, y * self.scale, z * self.scale
        
        # Isometric transform
        u = (sx - sz) * cos_20
        v = (sx + sz) * sin_20 - sy
        
        # position in screen
        return Point(self.loc.x + u, self.loc.y + v)

    def draw(self):
        # 1. Draw the Bounding Box (Lines)
        stroke('#666')
        stroke_weight(1)
        for start_node, end_node in self.box_edges:
            p1 = self.project(*start_node)
            p2 = self.project(*end_node)
            line(p1.x, p1.y, p2.x, p2.y)
            
        # 2. Draw the Points (Filled Ovals)
        
        for obj in self.objects:
            self.dot_size = size = math.sqrt(obj.header['Targetable area'])/ 10
            fill(obj.color)
            no_stroke()
            screen_pt = self.project(*obj.position.to_tuple())
            ellipse(screen_pt.x - self.dot_size/2, 
                    screen_pt.y - self.dot_size/2, 
                    self.dot_size, self.dot_size)

