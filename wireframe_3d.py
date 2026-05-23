# wireframe3d.py
# Reusable 3D wireframe renderer for Pythonista scene module
# Chris Thomas 2026
# imports wireframes for Elite Game
# could FlatLand be convertedto 3D
import math
import scene
import urllib.request
import re
import json
import ui
from random import choice, uniform
from constants import logger
# import constants as cs
import random

# ---------Colour constants
GREEN = (0, 1, 0, 1)
RED = (1, 0, 0, 1)
YELLOW = (1, 1, 0, 1)
WHITE = (1, 1, 1, 1)
CYAN = (0, 1, 1, 1)
BLUE = (0, 0, 1, 1)


class Vector3:
    __slots__ = ('x', 'y', 'z')

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def __add__(self, o): return Vector3(self.x+o.x, self.y+o.y, self.z+o.z)
    def __sub__(self, o): return Vector3(self.x-o.x, self.y-o.y, self.z-o.z)
    def __mul__(self, s): return Vector3(self.x*s,   self.y*s,   self.z*s)
    def __rmul__(self, s): return self.__mul__(s)
    def __truediv__(self, s): return Vector3(self.x/s,   self.y/s,   self.z/s)
    def __neg__(self): return Vector3(-self.x, -self.y, -self.z)
    def __repr__(self): return f'Vector3({self.x:.2f},{self.y:.2f},{self.z:.2f})'

    def dot(self, o):
        return self.x*o.x + self.y*o.y + self.z*o.z

    def cross(self, o):
        return Vector3(
            self.y*o.z - self.z*o.y,
            self.z*o.x - self.x*o.z,
            self.x*o.y - self.y*o.x
        )

    def length(self):
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalize(self):
        try:
            return self / self.length()
        except ZeroDivisionError:
            Vector3()
            
    def rotate_x(self, a):
        c, s = math.cos(a), math.sin(a)
        return Vector3(self.x, self.y*c - self.z*s, self.y*s + self.z*c)

    def rotate_y(self, a):
        c, s = math.cos(a), math.sin(a)
        return Vector3(self.x*c + self.z*s, self.y, -self.x*s + self.z*c)

    def rotate_z(self, a):
        c, s = math.cos(a), math.sin(a)
        return Vector3(self.x*c - self.y*s, self.x*s + self.y*c, self.z)

    def clone(self):
        return Vector3(self.x, self.y, self.z)
        
    @property
    def to_tuple(self):
        return (self.x, self.y, self.z)

                
class Vector2:
    __slots__ = ('x', 'y')

    def __init__(self, x=0.0, y=0.0):
        self.x = float(x)
        self.y = float(y)
        
    def __add__(self, o): return Vector3(self.x+o.x, self.y+o.y)
    def __sub__(self, o): return Vector3(self.x-o.x, self.y-o.y)
    def __mul__(self, s): return Vector3(self.x*s,   self.y*s)
    def __rmul__(self, s): return self.__mul__(s)
    def __truediv__(self, s): return Vector3(self.x/s,   self.y/s)
    def __neg__(self): return Vector3(-self.x, -self.y)
    def __repr__(self): return f'Vector3({self.x:.2f},{self.y:.2f})'

    def dot(self, o):
        return self.x*o.x + self.y*o.y

    def cross(self, o):
        return None
        """
        return Vector2(
            self.y*o.z - self.z*o.y,
            self.z*o.x - self.x*o.z,
            self.x*o.y - self.y*o.x
        )
        """

    def length(self):
        return math.sqrt(self.x**2 + self.y**2)

    def normalize(self):
        return self / self.length() if self.length() else Vector2()

    def rotate_x(self, a):
        c, _ = math.cos(a), math.sin(a)
        return Vector2(self.x, self.y*c)

    def rotate_y(self, a):
        c, _ = math.cos(a), math.sin(a)
        return Vector2(self.x*c, self.y)
    
    def clone(self):
        return Vector2(self.x, self.y)


# -------- WireframeObject  — one mesh in world space
class WireframeObject:
    """
    A single wireframe mesh.

    Attributes set by caller
    ------------------------
    original_vertices : list of Vector3   local-space vertices
    edges             : list of (int,int)  index pairs into vertices
    position          : Vector3            world position
    rotation          : Vector3            Euler angles (pitch_x, yaw_y, roll_z) radians
    scale             : float
    color             : (r,g,b,a)
    visible           : bool
    line_width        : float

    Read by renderer
    ----------------
    position_in_world          : Vector3  (copied from position by default;
                                           overwritten by composite objects)
    rotation_angles_in_world   : Vector3  (same)
    """

    def __init__(self,
                 position=None,
                 rotation=None,
                 scale=1.0,
                 color=GREEN,
                 visible=True,
                 line_width=2.0):
        self.position = position or Vector3()
        self.rotation = rotation or Vector3()
        self.scale = scale
        self.color = color
        self.visible = visible
        self.line_width = line_width

        self.original_vertices = []
        self.edges = []

        # world-space copies — kept in sync by get_world_vertices()
        self.position_in_world = self.position.clone()
        self.rotation_angles_in_world = self.rotation.clone()

    def get_world_vertices(self):
        """Transform local vertices → world space."""
        out = []
        rx = self.rotation_angles_in_world.x
        ry = self.rotation_angles_in_world.y
        rz = self.rotation_angles_in_world.z
        for v in self.original_vertices:
            v = v * self.scale
            v = v.rotate_z(rz).rotate_y(ry).rotate_x(rx)
            out.append(self.position_in_world + v)
        return out

    def wireframe_to_dict(self):
        """
        Converts a WireframeObject (and nested Vector3s) into a
        JSON-serializable dictionary.
        """
        # Helper to handle Vector3 objects if they have x, y, z attributes
        def vec_to_list(v):
            return [v.x, v.y, v.z] if v else [0, 0, 0]
    
        return {
            "name": self.name.removeprefix('SHIP_'),
            "header": self.header,
            "position": vec_to_list(self.position),
            "rotation": vec_to_list(self.rotation),
            "scale": self.scale,
            "color": list(self.color),  # Assuming color is a tuple (r,g,b,a)
            "visible": self.visible,
            "line_width": self.line_width,
            "original_vertices": [vec_to_list(v) for v in self.original_vertices],
            "edges": self.edges,
            "position_in_world": vec_to_list(self.position_in_world),
            "rotation_angles_in_world": vec_to_list(self.rotation_angles_in_world)
        }
        
    def get_world_vertices_from_transform(self, position, rotmat):
        """
        Transform local vertices using a rotation matrix (3 Vector3 rows)
        and a world position, bypassing the Euler-angle path entirely.
        
        rotmat: [right_vec, up_vec, forward_vec] — each a Vector3 or Vector
        """
        right = Vector3(rotmat[0].x, rotmat[0].y, rotmat[0].z)
        up = Vector3(rotmat[1].x, rotmat[1].y, rotmat[1].z)
        forward = Vector3(rotmat[2].x, rotmat[2].y, rotmat[2].z)
        
        out = []
        for v in self.original_vertices:
            sv = v * self.scale
            # Manual matrix multiply: local → world
            world = Vector3(
                right.x*sv.x + up.x*sv.y + forward.x*sv.z,
                right.y*sv.x + up.y*sv.y + forward.y*sv.z,
                right.z*sv.x + up.z*sv.y + forward.z*sv.z,
            )
            out.append(position + world)
        return out

                                                                                
# Built-in primitive shapes
class WireCube(WireframeObject):
    def __init__(self, size_x=1, size_y=1, size_z=1, **kw):
        super().__init__(**kw)
        hx, hy, hz = size_x/2, size_y/2, size_z/2
        self.original_vertices = [
            Vector3(-hx, -hy, hz), Vector3(hx, -hy, hz),
            Vector3(hx, -hy, -hz), Vector3(-hx, -hy, -hz),
            Vector3(-hx, hy, hz), Vector3(hx, hy, hz),
            Vector3(hx, hy, -hz), Vector3(-hx, hy, -hz),
        ]
        self.edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),   # bottom
            (4, 5), (5, 6), (6, 7), (7, 4),   # top
            (0, 4), (1, 5), (2, 6), (3, 7),   # verticals
        ]


class WirePyramid(WireframeObject):
    def __init__(self, base_size=1, height=1, **kw):
        super().__init__(**kw)
        h = base_size / 2
        self.original_vertices = [
            Vector3(-h, 0, -h), Vector3(h, 0, -h),
            Vector3(h, 0, h), Vector3(-h, 0, h),
            Vector3(0, height, 0),
        ]
        self.edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),
            (0, 4), (1, 4), (2, 4), (3, 4),
        ]


class Sun(WireframeObject):
    def __init__(self, radius=100, scale=65535, distance_scale=False, **kw):
        super().__init__(**kw)
        self.original_vertices = []
        self.is_star = True
        self.star_radius = radius
        self.scale = scale
        self.color = (1.0, 0.95, 0.6, 1.0)   # warm yellow
        self.distance_scale = distance_scale             # shrinks with distance

                
class Sprite3D(WireframeObject):
    """
    A billboard sprite that always faces the camera.
    position / position_in_world sets where it sits in 3D space.
    image_path : str   path to a Pythonista-accessible image
                 or SpriteNode
    width, height : display size in screen pixels (before distance scaling)
    distance_scale : if True, size shrinks with distance like the Sun
    """
    def __init__(self, image_path, width=64, height=64,
                 distance_scale=False, scale=100, **kw):
        super().__init__(**kw)
        self.original_vertices = []
        self.edges = []
        self.is_billboard = True
        self.image_path = image_path
        self.billboard_w = width
        self.billboard_h = height
        self.distance_scale = distance_scale
        self.scale = scale
        # Cache the loaded image so it isn't reloaded every frame
        if isinstance(image_path, str):
            self._image = scene.load_image_file(image_path)
        else:
            self._image = image_path
        # self._image = None

                
class WireSphere(WireframeObject):
    """Latitude/longitude wireframe sphere."""
    def __init__(self, radius=1, lat_lines=6, lon_lines=8, **kw):
        super().__init__(**kw)
        verts = []
        edges = []

        def idx(lat, lon):
            return lat * (lon_lines + 1) + lon

        for i in range(lat_lines + 1):
            phi = math.pi * i / lat_lines - math.pi/2
            for j in range(lon_lines + 1):
                theta = 2 * math.pi * j / lon_lines
                verts.append(Vector3(
                    radius * math.cos(phi) * math.cos(theta),
                    radius * math.sin(phi),
                    radius * math.cos(phi) * math.sin(theta)
                ))

        for i in range(lat_lines):
            for j in range(lon_lines):
                edges.append((idx(i, j), idx(i, j+1)))    # along latitude
                edges.append((idx(i, j), idx(i+1, j)))    # along longitude

        self.original_vertices = verts
        self.edges = edges


class WireCylinder(WireframeObject):
    def __init__(self, radius=1, height=1, segments=8, **kw):
        super().__init__(**kw)
        verts, edges = [], []
        hh = height / 2
        for i in range(segments):
            a = 2 * math.pi * i / segments
            x, z = radius * math.cos(a), radius * math.sin(a)
            verts += [Vector3(x, hh, z), Vector3(x, -hh, z)]
            t, b = i*2, i*2+1
            nt = ((i+1) % segments) * 2
            nb = nt + 1
            edges += [(t, nt), (b, nb), (t, b)]
        self.original_vertices = verts
        self.edges = edges


class WireAxes(WireframeObject):
    """RGB XYZ axis cross — useful for debugging orientation."""
    def __init__(self, size=50, **kw):
        kw.setdefault('color', WHITE)
        super().__init__(**kw)
        self.original_vertices = [
            Vector3(0, 0, 0), Vector3(size, 0, 0),   # X  red
            Vector3(0, 0, 0), Vector3(0, size, 0),   # Y  green
            Vector3(0, 0, 0), Vector3(0, 0, size),   # Z  blue
        ]
        # Store per-edge colours separately; renderer checks for this attribute
        self.edges = [(0, 1), (2, 3), (4, 5)]
        self.edge_colors = [RED, GREEN, BLUE]


class Camera:
    """
    Fly-cam.  Call update() each frame, then pass to Renderer.draw().

    position    : Vector3   world position of camera
    yaw         : float     left/right rotation (radians)
    pitch       : float     up/down tilt (radians)
    roll        : float     rotation around forward axis (radians)
    fov         : float     horizontal field of view (radians)
    z_near      : float     near clip distance
    z_far       : float     far clip distance
    """

    def __init__(self,
                 position=None,
                 yaw=0.0,  # move direction
                 pitch=0.0,
                 roll=0.0,
                 look_yaw=0,
                 fov=math.radians(60),
                 z_near=5.0,
                 z_far=2000.0):
        self.position = position or Vector3()
        self.yaw = yaw
        self.pitch = pitch
        self.roll = roll
        self.fov = fov
        self.z_near = z_near
        self.z_far = z_far

    @property
    def focal_length(self):
        return 1.0 / math.tan(self.fov / 2)

    def look_forward(self):
        """Unit vector the camera is pointing along."""
        return Vector3(
            math.sin(self.look_yaw) * math.cos(self.pitch),
            -math.sin(self.pitch),
            math.cos(self.look_yaw) * math.cos(self.pitch)
        )
        
    def forward(self):
        """Unit vector the camera is pointing along."""
        return Vector3(
            math.sin(self.yaw) * math.cos(self.pitch),
            -math.sin(self.pitch),
            math.cos(self.yaw) * math.cos(self.pitch)
        )
        
    def right(self):
        """
        Right vector, accounting for roll.
        Computed by rotating the world-up vector around forward,
        then crossing to get the true right.
        """
        fwd = self.forward()
        # World up, tilted by roll around the forward axis
        world_up = Vector3(
            math.sin(self.roll),
            math.cos(self.roll),
            0.0
        )
        # If forward is nearly vertical, world_up becomes degenerate —
        # fall back to a side vector instead.
        if abs(fwd.dot(world_up)) > 0.99:
            world_up = Vector3(math.cos(self.roll), 0.0, -math.sin(self.roll))
        r = fwd.cross(world_up)
        return r.normalize()

    def up(self):
        """True up vector — perpendicular to both forward and right."""
        return self.right().cross(self.forward()).normalize()

    def basis(self):
        """Return (right, up, forward) — the camera's local axes."""
        fwd = self.forward()
        r = self.right()
        u = r.cross(fwd).normalize()
        return r, u, fwd


class Renderer:
    """
    Projects and draws a list of WireframeObjects from a Camera's point of view.

    Usage (inside scene.Scene.draw):
        renderer.draw(objects, camera, screen_size)

    Optional depth sorting
    ----------------------
    depth_sort=True  : painter's algorithm, far objects first.
                       Good enough for non-intersecting meshes.
    backface_cull=True: skip edges whose midpoint faces away from camera.
                        Requires face_normals on the object (Elite ships have
                        these).  Falls back gracefully if absent.
    """

    def __init__(self,
                 depth_sort=True,
                 backface_cull=False,
                 default_line_width=2.0):
        self.depth_sort = depth_sort
        self.backface_cull = backface_cull
        self.default_line_width = default_line_width

    def draw(self, objects, camera, screen_size):
        """
        objects     : iterable of WireframeObject
        camera      : Camera
        screen_size : scene.Size  (has .w and .h)
        """
        sw, sh = screen_size.w, screen_size.h
        fl = camera.focal_length

        visible = [o for o in objects if o.visible]

        if self.depth_sort:
            visible.sort(
                key=lambda o: (o.position_in_world - camera.position).length(),
                reverse=True
            )
        for obj in visible:
            # --- Sprite billboard ---
            if getattr(obj, 'is_billboard', False):
                cam_pos = self._to_camera(obj.position_in_world, camera)
                
                if cam_pos.z > camera.z_far:
                    if isinstance(obj._image, scene.SpriteNode):
                       obj._image.alpha = 0
                    continue
                screen_pts = self._project(cam_pos, fl, camera)
                if screen_pts is None:
                    if isinstance(obj._image, scene.SpriteNode):
                       obj._image.alpha = 0
                    continue
            
                w = obj.billboard_w
                h = obj.billboard_h
                if obj.distance_scale:
                    dist = max(1.0, (obj.position_in_world - camera.position).length())
                    scale = fl / dist * obj.scale
                    w *= scale
                    h *= scale
                cx, cy = screen_pts
                if isinstance(obj._image, scene.SpriteNode):
                    obj._image.position = (cx, cy)
                    obj._image.alpha = 1
                    obj._image.scale = scale
                else:
                    # Lazy-load the image
                    if obj._image is None:
                        obj._image = scene.load_image_file(obj.image_path)
                    
                    scene.image(obj._image, cx - w/2, cy - h/2, w, h)
                    # scene.image(obj._image, 500, 500, w, h)
                continue
                 
            # --- Star billboard ---
            if getattr(obj, 'is_star', False):
                # Project the star's world position to screen space
                cam_pos = self._to_camera(obj.position_in_world, camera)
                if cam_pos is None or cam_pos.z >= camera.z_far:
                    continue  # Behind camera
                screen_pts = self._project(cam_pos, fl, camera)
                if screen_pts is None:
                    continue
            
                # Size: fixed apparent radius, optionally scaled by distance
                star_radius = getattr(obj, 'star_radius', 4.0)
                if getattr(obj, 'star_distance_scale', False):
                    dist = max(1.0, (obj.position_in_world - camera.position).length())
                    star_radius = star_radius * fl / dist * obj.scale
            
                # Draw filled circle (no stroke)
                star_color = getattr(obj, 'star_color', obj.color)
                scene.fill(*star_color)
                scene.stroke(0, 0, 0, 0)  # transparent stroke
                cx, cy = screen_pts
                # print(f'{cx=:.0f}, {cy=:.0f}, {star_radius=:.2f}')
                scene.ellipse(cx - star_radius, cy - star_radius,
                              star_radius * 2, star_radius * 2)
                scene.fill(0, 0, 0, 0)    # reset fill
                continue                   # skip edge drawing entirely
                    
            if hasattr(obj, 'rotmat_world'):
                world_verts = obj.get_world_vertices_from_transform(
                    obj.position_in_world, obj.rotmat_world
                )
            else:
                world_verts = obj.get_world_vertices()  # Euler fallback for primitive
            cam_verts = [self._to_camera(v, camera) for v in world_verts]
            screen_pts = [self._project(v, fl, camera) for v in cam_verts]

            color = obj.color
            line_width = getattr(obj, 'line_width', self.default_line_width)
            has_edge_colors = hasattr(obj, 'edge_colors')            
            scene.stroke_weight(line_width)

            # Define clip rect — defaults to full screen, override with self.viewport
            vx, vy, vw, vh = getattr(self, 'viewport', (0, 0, sw, sh))
            
            for ei, (i1, i2) in enumerate(obj.edges):
                p1, p2 = screen_pts[i1], screen_pts[i2]
                if p1 is None or p2 is None:
                    continue
                clipped = self._clip_line(p1[0], p1[1], p2[0], p2[1],
                                          vx, vy, vx + vw, vy + vh)
                if clipped is None:
                    continue
                edge_color = obj.edge_colors[ei] if has_edge_colors else color
                scene.stroke(*edge_color)
                scene.rect(0, 0, 0, 0)
                scene.line(*clipped)
                                            
    def _clip_line(self, x1, y1, x2, y2, x_min, y_min, x_max, y_max):
        """Liang-Barsky line clip. Returns clipped (x1,y1,x2,y2) or None."""
        dx, dy = x2 - x1, y2 - y1
        p = [-dx, dx, -dy, dy]
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
        return (x1 + t0*dx, y1 + t0*dy,
                x1 + t1*dx, y1 + t1*dy)

    def _to_camera(self, world_v, camera):
        """World vertex → camera space using full roll/pitch/yaw basis."""
        v = world_v - camera.position
        r, u, f = camera.basis()
        # Project onto each camera axis
        return Vector3(v.dot(r), v.dot(u), v.dot(f))

    def _project(self, cam_v, fl, camera):
        """Camera-space vertex → (screen_x, screen_y) or None if clipped."""
        if cam_v.z < camera.z_near or cam_v.z > camera.z_far:
            return None
        sx = (cam_v.x * fl / cam_v.z) * self.viewport.w + self.viewport.center().x
        sy = (cam_v.y * fl / cam_v.z) * self.viewport.h + self.viewport.center().y
        return (sx, sy)
        
    def explode(self, obj, camera, screen_size):
        # Add an explosion_time attribute to your objects (0.0 to 1.0)
        # visible = [o for o in self.objects if o.visible]
        scene.no_fill()
        fl = camera.focal_length
        if True:  # obj.visible:
            
            t = getattr(obj, 'explosion_time', 0)
            world_verts = obj.get_world_vertices()
            center = obj.position_in_world
        
            for ei, (i1, i2) in enumerate(obj.edges):
                v1, v2 = world_verts[i1], world_verts[i2]
                if t > 0:
                    # Calculate a unique direction for this specific edge
                    edge_center = (v1 + v2) / 2
                    direction = (edge_center - center).normalize()
                    
                    # Offset the vertices based on time
                    offset = direction * (t * 200)  # 50 is explosion force
                    noise = Vector3(random.uniform(-5, 5), random.uniform(-5, 5), random.uniform(-5, 5)) * t
                    v1 += offset + noise
                    v2 += offset + noise
                
                # Project modified vertices to camera space
                p1 = self._project(self._to_camera(v1, camera), fl, camera)
                p2 = self._project(self._to_camera(v2, camera), fl, camera)
        
                if p1 and p2:
                    # Fade out
                    alpha = max(0, 1.0 - t)
                    edge_color = obj.color[:3] + (alpha,)
                    scene.stroke(*edge_color)
                    scene.rect(0, 0, 0, 0)
                    scene.line(*p1, *p2)
                    
                                           
# demo.py

# from wireframe3d import (
#    Vector3, Camera, Renderer,
#    WireCube, WirePyramid, WireSphere, WireAxes,
#    GREEN, CYAN, YELLOW, WHITE
# )


class Demo(scene.Scene):
    def setup(self):
        
        self.camera = Camera(
            position=Vector3(0, 0, -500),
            fov=math.radians(60),
            z_far=10000
         )
        self.renderer = Renderer(depth_sort=True)
        self.t = 0

        self.objects = [
            WireCube(50, 50, 50,
                     position=Vector3(-80, 0, 0), color=GREEN),
            WirePyramid(60, 80,
                        position=Vector3(80, 0, 0),  color=CYAN),
            WireSphere(40, lat_lines=10, lon_lines=16,
                       position=Vector3(0, 0, 100),  color=YELLOW),
            WireAxes(60),
        ]
        
        try:
            objects = load_wireframes_from_json('files/Elite_ships.json')
        except Exception:
            ship_locs = ['missile', 'coriolis', 'escape_pod', 'plate',
                         'canister', 'Boulder', 'Asteroid', 'Splinter', 'Shuttle',
                         'Transporter', 'Cobra_Mk_3', 'Python', 'Boa', 'Anaconda',
                         'Rock_hermit', 'Viper', 'Sidewinder', 'Mamba', 'Krait', 'Adder',
                         'Gecko', 'Cobra_Mk_1', 'Worm', 'Cobra_Mk_3_p', 'Asp_Mk_2',
                         'Python_p', 'Fer_de_lance', 'Moray', 'Thargoid', 'Thargon',
                         'Constrictor', 'logo', 'Cougar', 'Dodo']
            ships = GetEliteShips('6502sp', ship_locs)
            objects = ships.ship_objects
        
        for ship in objects:
            ship.position = Vector3(
                                    uniform(-400, 400),   # spread left/right
                                    uniform(-400, 400),   # roughly eye level
                                    uniform(800, 1000)     # ahead of camera
                                    )
            ship.scale = uniform(0.5, 1.5)
            
            ship.color = choice([GREEN, RED, YELLOW, WHITE, CYAN, BLUE])
            
            self.objects.append(ship)

    def update(self):
        self.t += self.dt * .001
        looping_sine = abs(math.sin((math.pi * self.t) / 10))
    
        # Spin all
        # self.camera.position =Vector3(100*self.dt, 0, -1000-self.dt*100)
        for obj in self.objects[:]:
            # obj.rotation.x = self.t
            obj.rotation.y = self.t
            obj.rotation.z = self.t
            # Multiply by your desired amplitude (e.g., 1000 units)
            loc_change = Vector3(0, 0, 8000 * looping_sine)
            obj.position_in_world = obj.position.clone() + loc_change
            obj.rotation_angles_in_world = obj.rotation.clone()
        if self.t % 5 == 0:
           obj = choice(self.objects[4:])
           self.renderer.explode(self.camera, self.size)
           
    def draw(self):
        scene.background(0, 0, 0)
        self.renderer.viewport = (100, 100, 400, 300)  # x, y, w, h
        self.renderer.draw(self.objects, self.camera, self.size)
        

class Demo2(scene.Scene):
    def setup(self):
        
        self.camera = Camera(
            position=Vector3(0, 0, -500),
            fov=math.radians(80),
            z_far=10000
         )
        self.renderer = Renderer(depth_sort=True)
        self.t = 0

        self.objects = [
            # WireCube(50, 50, 50,
            #         position=Vector3(-80, 0, 0), color=GREEN),
            # WirePyramid(60, 80,
            #            position=Vector3(80, 0, 0),  color=CYAN),
            WireSphere(10, lat_lines=10, lon_lines=32,
                       position=Vector3(0, 0, 100),  color=YELLOW),
            # WireAxes(60),
        ]
        
        try:
            objects = load_wireframes_from_json('files/Elite_ships.json')
        except Exception:
            ship_locs = ['missile', 'coriolis', 'escape_pod', 'plate',
                         'canister', 'Boulder', 'Asteroid', 'Splinter', 'Shuttle',
                         'Transporter', 'Cobra_Mk_3', 'Python', 'Boa', 'Anaconda',
                         'Rock_hermit', 'Viper', 'Sidewinder', 'Mamba', 'Krait', 'Adder',
                         'Gecko', 'Cobra_Mk_1', 'Worm', 'Cobra_Mk_3_p', 'Asp_Mk_2',
                         'Python_p', 'Fer_de_lance', 'Moray',  'Thargoid', 'Thargon',
                         'Constrictor', 'logo', 'Cougar', 'Dodo']
            ships = GetEliteShips('6502sp', ship_locs)
            objects = ships.ship_objects
        spacing = 100
        print(len(objects))
        for i, ship in enumerate(objects):
            print(ship.name)
            ship.position = Vector3(-4 * spacing + i % 10 * spacing,  # spread left/right
                                    -2 * spacing + spacing * i / 10,  # roughly eye level
                                    500     # ahead of camera
                                    )
            ship.scale = 0.5
            ship.visible = i % 2
            ship.color = choice([GREEN, RED, YELLOW, WHITE, CYAN, BLUE])
            ship.explosion_time = random.random()
            self.objects.append(ship)
        self._exploding_obj = None   # WireframeObject currently exploding
        self._explosion_t = random.random()      # 0.0 → 1.0
         
    def _pick_new_explosion(self):
        candidates = [o for o in self.objects if hasattr(o, 'name')]
        if candidates:
            obj = random.choice(candidates)
            obj.explosion_time = 0.0
            self._exploding_obj = obj
            self._explosion_t = 0.0
            
    def update(self):
        self.t += self.dt * .001
        for obj in self.objects[:]:
            obj.rotation.y = math.radians(-45)
            obj.rotation.z = self.t
            obj.position_in_world = obj.position.clone()
            obj.rotation_angles_in_world = obj.rotation.clone()

        # Advance explosion; pick a new target once it finishes
        EXPLOSION_SPEED = 0.4   # fraction of 1.0 per second

        if self._exploding_obj is None:
            self._pick_new_explosion()
        else:
            self._explosion_t += self.dt * EXPLOSION_SPEED
            self._exploding_obj.explosion_time = self._explosion_t
            if self._explosion_t >= 1.0:
                self._exploding_obj = None   # done; next update picks a new one
           
    def draw(self):
        scene.background(0, 0, 0)
    
        # Temporary store to restore later
        exploding = self._exploding_obj
        
        # Draw all objects
        for obj in self.objects:
            if obj == exploding:
                 
                # Draw the explosion instead of the ship
                self.renderer.explode(obj, self.camera, self.size)
            else:
                # Draw normal ship (Renderer.draw checks .visible)
                self.renderer.draw([obj], self.camera, self.size)
                                                

class EliteShip(WireframeObject):
    """
    Generic Elite ship wireframe built directly from BBC Micro assembly source.
    
    Usage:
        ship = EliteShip(source_text, scale=1.0, position=Vector3(0,100,300),
                         color=COLOR_CYAN)
        scene.obstacles.append(ship)
    """
    def __init__(self, source_text, scale=1.0, **kwargs):
        super().__init__(scale=scale, **kwargs)
        parsed = self.parse_elite_ship_data(source_text)
        self.original_vertices, self.edges = self.elite_to_wireframe(parsed, scale=1.0)
        # Store face normals in case you want backface culling later
        self.face_normals = [
            Vector3(f['nx'], f['ny'], f['nz'])
            for f in parsed['faces']
        ]
                               
    def parse_elite_ship_data(self, source_text):
        """
        Parse Elite BBC Micro assembly ship data into Python dicts.
        
        Returns a dict with keys:
            'vertices': list of dicts with x, y, z, faces, visibility
            'edges':    list of dicts with v1, v2, face1, face2, visibility
            'faces':    list of dicts with nx, ny, nz, visibility
        
        Handles both:
            VERTEX   x,   y,   z, face1, face2, face3, face4, visibility
            EDGE   v1,  v2, face1, face2, visibility
            FACE   nx,  ny,  nz, visibility
        """
        
        vertices = []
        edges = []
        faces = []
        
        # Strip comments (\ to end of line in BBC BASIC/assembler)
        def strip_comment(line):
            idx = line.find('\\')
            if idx >= 0:
                return line[:idx]
            return line
        
        # Match a data line: KEYWORD followed by comma-separated integers
        vertex_re = re.compile(
            r'\bVERTEX\s+(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,'   # x, y, z
            r'\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,'     # face1-4
            r'\s*(\d+)'                                                 # visibility
        )
        edge_re = re.compile(
            r'\bEDGE\s+(\d+)\s*,\s*(\d+)\s*,'     # v1, v2
            r'\s*(\d+)\s*,\s*(\d+)\s*,'            # face1, face2
            r'\s*(\d+)'                             # visibility
        )
        face_re = re.compile(
            r'\bFACE\s+(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,'  # nx, ny, nz
            r'\s*(\d+)'                                              # visibility
        )
        
        for raw_line in source_text.splitlines():
            line = strip_comment(raw_line).strip()
            if not line:
                continue
            
            m = vertex_re.search(line)
            if m:
                x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3))
                faces_refs = [int(m.group(i)) for i in range(4, 8)]
                vis = int(m.group(8))
                vertices.append({
                    'x': x, 'y': y, 'z': z,
                    'faces': faces_refs,
                    'visibility': vis
                })
                continue
            
            m = edge_re.search(line)
            if m:
                edges.append({
                    'v1': int(m.group(1)), 'v2': int(m.group(2)),
                    'face1': int(m.group(3)), 'face2': int(m.group(4)),
                    'visibility': int(m.group(5))
                })
                continue
            
            m = face_re.search(line)
            if m:
                faces.append({
                    'nx': int(m.group(1)), 'ny': int(m.group(2)), 'nz': int(m.group(3)),
                    'visibility': int(m.group(4))
                })
        
        return {'vertices': vertices, 'edges': edges, 'faces': faces}

                
class GetEliteShips():
  
    def __init__(self, version, ship_locs):
       self.ship_objects = []
       # base url = 'https://elite.bbcelite.com/<version>/main/variable/ship_<name>.html'
       
       for name in ship_locs:
           url = f'https://elite.bbcelite.com/{version}/main/variable/ship_{name.lower()}.html'
           
           obj = self.ship_from_url(url)
           logger.debug(f'got {name}')
           self.ship_objects.append(obj)
          
    def ship_from_url(self, url, **kwargs):
        """Fetch an Elite ship page and return a ready-to-use EliteShip object."""
        parsed = self.fetch_elite_ship(url)
        verts, edges = self.elite_to_wireframe(parsed)
        obj = EliteShip.__new__(EliteShip)
        WireframeObject.__init__(obj, **kwargs)
        obj.original_vertices = verts
        obj.edges = edges
        obj.face_normals = [Vector3(f['nx'], f['ny'], f['nz']) for f in parsed['faces']]
        obj.name = parsed['name']
        obj.header = parsed['header']
        return obj
        
    def fetch_elite_ship(self, url):
        """
        Fetch and parse an Elite ship blueprint from elite.bbcelite.com.
    
        Targets the actual HTML structure:
            <div class="codeBlockWrapper">
              <pre class="codeBlock sourceCode initial">...</pre>
            </div>
    
        Falls back to grabbing any <pre class="codeBlock ..."> block if the
        wrapper div isn't present.
    
        Returns:
            {
                'name':     str,
                'header':   dict,
                'vertices': list of dicts,
                'edges':    list of dicts,
                'faces':    list of dicts,
            }
        """
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
    
        # --- Extract raw source text from the <pre> block ---
        # Primary: the specific codeBlock pre inside codeBlockWrapper
        match = re.search(
            r'<div[^>]*class="[^"]*codeBlockWrapper[^"]*"[^>]*>\s*'
            r'<pre[^>]*class="[^"]*codeBlock[^"]*"[^>]*>(.*?)</pre>',
            html, re.DOTALL
        )
        if not match:
            # Fallback: any <pre class="codeBlock ...">
            match = re.search(
                r'<pre[^>]*class="[^"]*codeBlock[^"]*"[^>]*>(.*?)</pre>',
                html, re.DOTALL
            )
        if not match:
            raise ValueError(f"No codeBlock <pre> found at {url}")
    
        raw = match.group(1)
    
        # Strip all HTML tags (spans, anchors etc. used for syntax highlighting)
        source_text = re.sub(r'<[^>]+>', '', raw)
    
        # Decode HTML entities
        source_text = (source_text
                       .replace('&amp;',  '&')
                       .replace('&lt;',   '<')
                       .replace('&gt;',   '>')
                       .replace('&#39;',  "'")
                       .replace('&quot;', '"')
                       .replace('&nbsp;', ' '))
    
        # Derive ship name from URL  e.g. ship_cougar -> SHIP_COUGAR
        name_match = re.search(r'/(ship_[^/]+)\.html', url)
        ship_name = name_match.group(1).upper() if name_match else 'UNKNOWN'
    
        parsed = self.parse_elite_ship_data(source_text)
        parsed['name'] = ship_name
        parsed['header'] = self._parse_header(source_text)
        return parsed
        
    def elite_to_wireframe(self, parsed, scale=1.0):
        """
        Convert parsed Elite ship data to WireCoriolis-style vertex/edge lists
        suitable for direct use in a WireframeObject.
        
        Returns:
            original_vertices: list of Vector3
            edges:             list of (v1_index, v2_index) tuples
        """
        original_vertices = [
            Vector3(v['x'] * scale, v['y'] * scale, v['z'] * scale)
            for v in parsed['vertices']
        ]
        edges = [
            (e['v1'], e['v2'])
            for e in parsed['edges']
        ]
        return original_vertices, edges
        
    def parse_elite_ship_data(self, source_text):
        """
        Parse Elite BBC Micro assembly ship data into Python dicts.
        
        Returns a dict with keys:
            'vertices': list of dicts with x, y, z, faces, visibility
            'edges':    list of dicts with v1, v2, face1, face2, visibility
            'faces':    list of dicts with nx, ny, nz, visibility
        
        Handles both:
            VERTEX   x,   y,   z, face1, face2, face3, face4, visibility
            EDGE   v1,  v2, face1, face2, visibility
            FACE   nx,  ny,  nz, visibility
        """
        
        vertices = []
        edges = []
        faces = []
        
        # Strip comments (\ to end of line in BBC BASIC/assembler)
        def strip_comment(line):
            idx = line.find('\\')
            if idx >= 0:
                return line[:idx]
            return line
        
        # Match a data line: KEYWORD followed by comma-separated integers
        vertex_re = re.compile(
            r'\bVERTEX\s+(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,'   # x, y, z
            r'\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,'     # face1-4
            r'\s*(\d+)'                                                 # visibility
        )
        edge_re = re.compile(
            r'\bEDGE\s+(\d+)\s*,\s*(\d+)\s*,'     # v1, v2
            r'\s*(\d+)\s*,\s*(\d+)\s*,'            # face1, face2
            r'\s*(\d+)'                             # visibility
        )
        face_re = re.compile(
            r'\bFACE\s+(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,'  # nx, ny, nz
            r'\s*(\d+)'                                              # visibility
        )
        
        for raw_line in source_text.splitlines():
            line = strip_comment(raw_line).strip()
            if not line:
                continue
            
            m = vertex_re.search(line)
            if m:
                x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3))
                faces_refs = [int(m.group(i)) for i in range(4, 8)]
                vis = int(m.group(8))
                vertices.append({
                    'x': x, 'y': y, 'z': z,
                    'faces': faces_refs,
                    'visibility': vis
                })
                continue
            
            m = edge_re.search(line)
            if m:
                edges.append({
                    'v1': int(m.group(1)), 'v2': int(m.group(2)),
                    'face1': int(m.group(3)), 'face2': int(m.group(4)),
                    'visibility': int(m.group(5))
                })
                continue
            
            m = face_re.search(line)
            if m:
                faces.append({
                    'nx': int(m.group(1)), 'ny': int(m.group(2)), 'nz': int(m.group(3)),
                    'visibility': int(m.group(4))
                })
        
        return {'vertices': vertices, 'edges': edges, 'faces': faces}
 
    def _parse_header(self, source_text):
        """
        Extract the EQUB/EQUW header fields, including binary values
        and multi-line labels.
        """
        header = {}
        last_val = None
        
        for line in source_text.splitlines():
            line = line.strip()
            
            # Stop at vertices
            if re.search(r'_VERTICES\b', line):
                break
    
            # 1. Match standard directive lines: "EQUB %00010000 \ Label = Val"
            # Adjusted regex: optional leading whitespace, matches EQUB/W, captures value and comment
            m_dir = re.match(r'EQU[BW]\s+([%\d\s\*]+)\\(.+)', line)
            
            # 2. Match continuation lines: "\ Label = Val"
            m_cont = re.match(r'^\\(.+)', line)
    
            if m_dir:
                raw_val = m_dir.group(1).strip()
                comment_part = m_dir.group(2)
                
                # Convert BBC Micro binary '%' to Python '0b'
                if raw_val.startswith('%'):
                    try:
                        value = int(raw_val[1:], 2)
                    except ValueError:
                        value = raw_val
                else:
                    try:
                        # Basic eval for "70 * 70" etc.
                        value = eval(raw_val, {"__builtins__": {}})
                    except Exception:
                        value = raw_val
                
                last_val = value  # Store in case the next line is a continuation
                self._add_header_item(header, comment_part, value)
    
            elif m_cont and last_val is not None:
                # This is a comment-only line, reuse the last numeric value
                comment_part = m_cont.group(1)
                self._add_header_item(header, comment_part, last_val)
    
        return header
    
    def _add_header_item(self, header, comment_part, value):
        """Helper to clean the label and add to dict."""
        # Split by '=' to get "Laser power" from "Laser power = 2"
        label = comment_part.strip().split('=')[0].strip()
        if label:
            header[label] = value

                
def save_wireframes_to_json(wireframe_list, filename):
    """
    Serializes a list of WireframeObjects to a JSON file.
    """
    
    serializable_list = [obj.wireframe_to_dict() for obj in wireframe_list]
    print(serializable_list)
    try:
        with open(filename, 'w') as f:
            json.dump(serializable_list, f, indent=2)
        print(f"Successfully saved {len(wireframe_list)} objects to {filename}")
    except Exception as e:
        print(f"Failed to save data: {e}")


def load_wireframes_from_json(filename):
    """
    Reads a JSON file and returns a list of WireframeObject instances.
    """
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
            
        loaded_objects = []
        
        for item in data:
            # Reconstruct the main object with basic attributes
            
            obj = WireframeObject(
                position=Vector3(*item["position"]),
                rotation=Vector3(*item["rotation"]),
                scale=item["scale"],
                color=tuple(item["color"]),
                visible=item["visible"],
                line_width=item["line_width"]
            )
            obj.name = item["name"],
            obj.header = item["header"]
            
            # Reconstruct the mesh data (vertices and edges)
            obj.original_vertices = [Vector3(*v) for v in item["original_vertices"]]
            obj.edges = [tuple(e) for e in item["edges"]]
            if 'edge_colors' in item:
                obj.edge_colors = [color for color in item["edge_colors"]]
            # Reconstruct world-space properties
            obj.position_in_world = Vector3(*item["position_in_world"])
            obj.rotation_angles_in_world = Vector3(*item["rotation_angles_in_world"])
            
            loaded_objects.append(obj)
            
        # print(f"Successfully loaded {len(loaded_objects)} objects from {filename}")
        return loaded_objects

    except FileNotFoundError:
        print(f"Error: The file {filename} was not found.")
        return []
    except Exception as e:
        print(f"An error occurred while loading: {e}")
        return []

                
def load_ships_from_json(filename):
    """
    Reads a JSON file and returns a list of WireframeObject instances.
    """
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
            
        loaded_objects = []
        
        for item in data:
            # Reconstruct the main object with basic attributes
            obj = WireframeObject(
                position=Vector3(*item["position"]),
                rotation=Vector3(*item["rotation"]),
                scale=item["scale"],
                color=tuple(item["color"]),
                visible=item["visible"],
                line_width=item["line_width"]
            )
            obj.name = item["name"],
            obj.header = item["header"],
            
            # Reconstruct the mesh data (vertices and edges)
            obj.original_vertices = [Vector3(*v) for v in item["original_vertices"]]
            obj.edges = [tuple(e) for e in item["edges"]]
            
            # Reconstruct world-space properties
            obj.position_in_world = Vector3(*item["position_in_world"])
            obj.rotation_angles_in_world = Vector3(*item["rotation_angles_in_world"])
            
            loaded_objects.append(obj)
            
        # print(f"Successfully loaded {len(loaded_objects)} objects from {filename}")
        return loaded_objects

    except FileNotFoundError:
        print(f"Error: The file {filename} was not found.")
        return []
    except Exception as e:
        print(f"An error occurred while loading: {e}")
        return []


def run_demo():
   
   g = Demo()
   g.setup()
   # [g.objects.append(ship) for ship in  ships.ship_objects]
   """
   ship_locs = ['missile', 'coriolis', 'escape_pod', 'plate',
                'canister', 'Boulder', 'Asteroid', 'Splinter', 'Shuttle',
                'Transporter', 'Cobra_Mk_3', 'Python', 'Boa', 'Anaconda',
                'Rock_hermit', 'Viper', 'Sidewinder', 'Mamba', 'Krait', 'Adder',
                'Gecko', 'Cobra_Mk_1', 'Worm', 'Cobra_Mk_3_p', 'Asp_Mk_2',
                'Python_p', 'Fer_de_lance', 'Moray', 'Thargoid', 'Thargon', 'Constrictor', 'logo', 'Cougar', 'Dodo']
   #ships = GetEliteShips('6502sp', ship_locs)
   
   #save_wireframes_to_json(ships.ship_objects, 'Elite_ships.json')
   objects = load_wireframes_from_json('files/Elite_ships.json')
   
   for ship in objects:
      # Inspect header
      print(ship.name)
      try:
         # Unpack the tuples into two separate lists/iterables
         x_values, y_values = zip(*ship.edges)
         max_x = max(x_values)
         max_y = max(y_values)
         print(f"Max X: {max_x}, Max Y: {max_y}")
      except AttributeError:
       pass
      # for k, v in ship.header[0].items():
      #    print(f"{k}")
      
   """
   # scene.run(Demo2(), show_fps=True)
   
   
# spaceflight_demo.py
# Drop this file alongside wireframe_3d.py and run it directly.
# Requires Pythonista 3 on iOS/iPadOS.
#
# Controls (6 touch squares along the bottom):
#   [ROLL L] [ROLL R] [PITCH UP] [PITCH DN] [THRUST+] [THRUST-]
#
# Camera always faces direction of travel (velocity vector).
# Space is 5000 x 4000 x 3000 units, ships wrap around at boundaries.

SPACE_X = 5000.0
SPACE_Y = 4000.0
SPACE_Z = 3000.0

MIN_SHIP_SPEED = 0.1   # units per frame
MAX_SHIP_SPEED = 1.0

ROLL_RATE = math.radians(0.2)   # radians per frame while button held
PITCH_RATE = math.radians(0.15)
THRUST_STEP = 0.5                  # units/frame per button press
MAX_THRUST = 5
MIN_THRUST = 0                # allow gentle reverse

SHIP_COLORS = [GREEN, RED, YELLOW, WHITE, CYAN, BLUE]

# Button layout constants
BTN_W = 80
BTN_H = 60
BTN_PAD = 8
BTN_Y = 20       # distance from bottom of screen


class MovingShip:
    def __init__(self, obj: WireframeObject, bounds):
        self.obj = obj
        bx, by, bz = bounds

        # Random start position inside the space
        obj.position = Vector3(
            uniform(0, bx),
            uniform(0, by),
            uniform(0, bz),
        )
        obj.position_in_world = obj.position.clone()

        # Random direction, random speed
        speed = uniform(MIN_SHIP_SPEED, MAX_SHIP_SPEED)
        dx = uniform(-1, 1)
        dy = uniform(-1, 1)
        dz = uniform(-1, 1)
        length = math.sqrt(dx*dx + dy*dy + dz*dz) or 1.0
        self.velocity = Vector3(dx/length*speed, dy/length*speed, dz/length*speed)

        # Random slow tumble
        print(obj)
        self.spin_y = 0  # uniform(-0.02, 0.02)
        self.spin_z = uniform(-0.02, 0.02)

        self._bounds = bounds

    def update(self):
        obj = self.obj
        # Move
        obj.position.x += self.velocity.x
        obj.position.y += self.velocity.y
        obj.position.z += self.velocity.z

        # Wrap around space boundaries
        bx, by, bz = self._bounds
        obj.position.x %= bx
        obj.position.y %= by
        obj.position.z %= bz

        obj.position_in_world = obj.position.clone()

        # Tumble
        obj.rotation.y += self.spin_y
        obj.rotation.z += self.spin_z
        obj.rotation_angles_in_world = obj.rotation.clone()


class TouchButton:
    def __init__(self, label, x, y, w, h, color=(0.2, 0.8, 0.4, 0.85)):
        self.label = label
        self.rect = scene.Rect(x, y, w, h)
        self.color = color
        self.pressed = False

    def contains(self, pt):
        r = self.rect
        return r.x <= pt.x <= r.x + r.w and r.y <= pt.y <= r.y + r.h

    def draw(self):
        r = self.rect
        # Fill
        if self.pressed:
            scene.fill(self.color[0]*1.4, self.color[1]*1.4,
                       self.color[2]*1.4, self.color[3])
        else:
            scene.fill(*self.color)
        scene.stroke(1, 1, 1, 0.6)
        scene.stroke_weight(1.5)
        scene.rect(r.x, r.y, r.w, r.h)

        # Label
        scene.fill(1, 1, 1, 1)
        scene.text(self.label,
                   font_name='Courier',
                   font_size=13,
                   x=r.x + r.w/2,
                   y=r.y + r.h/2,
                   alignment=5)   # centre


class SpaceFlight(scene.Scene):

    def setup(self):
        self.bounds = (SPACE_X, SPACE_Y, SPACE_Z)

        # Camera (player) -------------------------------
        # Random start position and heading
        start_pos = Vector3(
            uniform(0, SPACE_X),
            uniform(0, SPACE_Y),
            uniform(0, SPACE_Z),
        )
        self.camera = Camera(
            position=start_pos,
            yaw=uniform(0, math.tau),
            pitch=uniform(-0.4, 0.4),
            fov=math.radians(70),
            z_near=-50,
            z_far=4000.0,
        )
        self.status = scene.LabelNode('',
                                      font=('Avenir Next', 20),
                                      color='white',
                                      position=(0, self.size.h-100),
                                      anchor_point=(0, 0),
                                      parent=self)
        self.spd_status = scene.LabelNode('',
                                          font=('Avenir Next', 20),
                                          color='white',
                                          position=(0, self.size.h-120),
                                          anchor_point=(0, 0),
                                          parent=self)
        
        # Player velocity (starts at zero)
        self.thrust = 0.0          # current speed along forward vector
        self.roll_angle = 0.0           # current bank angle (radians); drives yaw rate
        
        self.renderer = Renderer(depth_sort=True)
        self.renderer.viewport =  scene.Rect(100, 100, 400, 300)

        # ---- Load / generate ships ------------------------------------------
        raw_objects = self._load_ships()[:5]

        self.moving_ships = []
        for obj in raw_objects:
            obj.scale = uniform(0.4, 1.8)
            obj.color = choice(SHIP_COLORS)
            obj.visible = True
            ms = MovingShip(obj, self.bounds)
            self.moving_ships.append(ms)
        # In SpaceFlight.setup, replace sunpos with:
        sunpos = Vector3(SPACE_X/2 + 500, SPACE_Y/2, 500)  # offset along camera's forward (X axis, yaw=π/2)
        
        # A few= decorative primitives so the scene isn't empty if no ships load
        extras = [
            # WireSphere(40, lat_lines=8, lon_lines=12, color=YELLOW),
            # WireSphere(25, lat_lines=6, lon_lines=10, color=GREEN)
            ]
        # sun = Sun(radius=200, position=sunpos, color=YELLOW)
        sun = Sprite3D('images/Fire2.png', width=100, height=100,
                       distance_scale=True)
                
        sun.position_in_world = sunpos.clone()
        self.static_objects = [sun]
        for obj in extras:
            # obj.color = choice(SHIP_COLORS)
            self.moving_ships.append(MovingShip(obj, self.bounds))
        
        self._build_buttons()
        # Track which touch uid is pressing which button
        self._touch_map = {}   # uid -> button index
        self.hud_roll_indicator()
        
    def hud_roll_indicator(self):
        # 3 components, centre circke and horixon, bank indicators, roll indicator
        # centre circle
        cx, cy = self.size.w/2, self.size.h/2
        r = 12
        path = ui.Path()
        path.move_to(-r, 0)
        path.line_to(r, 0)
        path.oval(-6, -6, 12, 12)
        scene.ShapeNode(path, stroke_color=(0.3, 1.0, 0.3, 0.7), position=(cx, cy), z_position=5, parent=self)
        
        # ---- Bank / horizon indicator ----------------------------------------
        # A short line rotated by roll_angle around the crosshair centre,
        # plus tick marks at Â±45Â° and Â±90Â° for reference.
        hr = 40   # horizon bar half-length
        # Bright when banked, dim when level
        path = ui.Path()
        path.line_width = 2
        path.move_to(-hr, 0)
        path.line_to(hr, 0)
        path.move_to(0, 0)
        path.line_to(0, 10)
        self.roll_indicator = scene.ShapeNode(path, stroke_color=(1.0, 1.0, 0.1),
                                              alpha=0.4, position=(cx, cy), z_position=5,
                                              parent=self)
        # Reference tick marks at Â±45Â°
        path = ui.Path()
        for ref in (-math.pi/4, math.pi/4):
            a = ref
            tx = math.cos(a) * (hr + 6)
            ty = math.sin(a) * (hr + 6)
            path.move_to(tx - math.cos(a)*5, ty - math.sin(a)*5,)
            path.line_to(tx, ty)
        scene.ShapeNode(path, stroke_color=(0.6, 0.6, 0.6, 0.5), position=(cx, cy), z_position=5, parent=self)
    
    def _load_ships(self):
        """Try JSON cache first, then fall back to live scrape."""
        objects = load_wireframes_from_json('files/Elite_ships.json')
        if objects:
           return objects
    
    def _build_buttons(self):
        """Create 6 evenly spaced buttons at the bottom of the screen."""
        sw = self.size.w
        labels = [
            ('ROLL\nL',   (0.3, 0.6, 1.0, 0.85)),
            ('ROLL\nR',   (0.3, 0.6, 1.0, 0.85)),
            ('PITCH\nUP', (0.2, 0.9, 0.5, 0.85)),
            ('PITCH\nDN', (0.2, 0.9, 0.5, 0.85)),
            ('THST\n+',   (1.0, 0.6, 0.1, 0.85)),
            ('THST\n-',   (1.0, 0.6, 0.1, 0.85)),
        ]
        n = len(labels)
        total_w = n * BTN_W + (n - 1) * BTN_PAD
        start_x = (sw - total_w) / 2

        self.buttons = []
        for i, (lbl, col) in enumerate(labels):
            x = start_x + i * (BTN_W + BTN_PAD)
            y = BTN_Y
            self.buttons.append(TouchButton(lbl, x, y, BTN_W, BTN_H, col))

    def touch_began(self, touch):
        pt = touch.location
        for i, btn in enumerate(self.buttons):
            if btn.contains(pt):
                btn.pressed = True
                self._touch_map[touch.touch_id] = i
                return

    def touch_moved(self, touch):
        # If a touch drifts off its original button, release it
        uid = touch.touch_id
        if uid in self._touch_map:
            i = self._touch_map[uid]
            if not self.buttons[i].contains(touch.location):
                self.buttons[i].pressed = False
                del self._touch_map[uid]

    def touch_ended(self, touch):
        uid = touch.touch_id
        if uid in self._touch_map:
            self.buttons[self._touch_map[uid]].pressed = False
            del self._touch_map[uid]

    def update(self):
        self._apply_controls()
        self._move_camera()
        for ms in self.moving_ships:
            ms.update()

    def _apply_controls(self):
        """Apply held buttons each frame
        Apple-style roll-to-turn flight model.

        ROLL L / ROLL R  : bank the ship left or right (increases roll_angle).
                           When buttons are released the bank decays back to zero.
        PITCH UP / DN    : tilt nose up / down directly.
        THRUST +/-       : accelerate / decelerate.

        Yaw is derived from the bank angle each frame:
            yaw_rate = sin(roll_angle) * YAW_SCALE
        So a shallow bank turns slowly; a steep bank turns quickly.
        Maximum bank is Â±90Â° so the yaw rate is bounded naturally by sin().
        """
        MAX_BANK = math.radians(85)
        # YAW_SCALE  = math.radians(2.2)   # yaw rate at full 90Â° bank (per frame)
        BANK_DECAY = 0.88                 # how fast bank returns to level
        pressed = [b.pressed for b in self.buttons]
        # 0=Roll L, 1=Roll R, 2=Pitch Up, 3=Pitch Down, 4=Thrust+, 5=Thrust-

        rolling = False
        if pressed[0]:
            self.roll_angle = max(-MAX_BANK, self.roll_angle - ROLL_RATE)
            rolling = True
        if pressed[1]:
            self.roll_angle = min(MAX_BANK, self.roll_angle + ROLL_RATE)
            rolling = True

        # Level out when not actively rolling
        if not rolling:
            self.roll_angle *= BANK_DECAY
        # Mirror bank angle into camera roll so the view tilts with the ship
        self.camera.roll = -self.roll_angle
        # Yaw is driven by how far we're banked â classic coordinated turn
        # self.camera.yaw += math.sin(self.roll_angle) * YAW_SCALE
        if pressed[2]:
            self.camera.pitch = min(math.radians(80),
                                    self.camera.pitch + PITCH_RATE)
        if pressed[3]:
            self.camera.pitch = max(-math.radians(80),
                                    self.camera.pitch - PITCH_RATE)
        if pressed[4]:
            self.thrust = min(MAX_THRUST, self.thrust + THRUST_STEP)
        if pressed[5]:
            self.thrust = max(MIN_THRUST,  self.thrust - THRUST_STEP)

    def _move_camera(self):
        """Move camera along its forward vector."""
        if abs(self.thrust) < 0.01:
            return
        fwd = self.camera.forward()
        cam = self.camera.position
        cam.x += fwd.x * self.thrust
        cam.y += fwd.y * self.thrust
        cam.z += fwd.z * self.thrust

        # Soft wrap — camera re-enters on the opposite side of the space
        bx, by, bz = self.bounds
        cam.x %= bx
        cam.y %= by
        cam.z %= bz

    def draw(self):
        scene.background(0, 0, 0)

        # Collect visible objects
        all_objs = [ms.obj for ms in self.moving_ships] + self.static_objects
        self.renderer.draw(all_objs, self.camera, self.size)

        self._draw_hud()

    def _draw_hud(self):
        self.roll_indicator.rotation = -self.roll_angle
        self.roll_indicator.alpha = 0.4 + 0.6 * abs(math.sin(self.roll_angle))
        
        # ---- Buttons --------------------------------------------------------
        scene.push_matrix()
        for btn in self.buttons:
            btn.draw()
        scene.pop_matrix()
        
        self.spd_status.text = f'SPD {self.thrust:+.1f}'
        c = self.camera.position
        self.status.text = f'{c.x:.0f}, {c.y:.0f}, {c.z:.0f}'

                
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    g = SpaceFlight()
    g.setup()
    g.draw()
    #scene.run(SpaceFlight(), show_fps=True, multi_touch=True)
    
   # run_demo()
