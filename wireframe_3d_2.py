# wireframe3d.py
# Reusable 3D wireframe renderer for Pythonista scene module
# Chris Thomas 2026
# imports wireframes for Elite Game
#
# Hidden line removal added 2026:
#   - EliteShip / GetEliteShips now store edges_with_faces (v1,v2,f1,f2)
#     and face_rep_verts (one vertex index per face) alongside face_normals.
#   - Renderer.draw() calls _visible_edge_set() when backface_cull=True and
#     the object has face data; edges whose BOTH adjacent faces are back-
#     facing are skipped entirely.
#   - wireframe_to_dict() / load_wireframes_from_json() serialise/restore the
#     new fields so the JSON cache works unchanged.

import math
import scene
import urllib.request
import re
import json
import ui
from random import choice, uniform
import constants as cs
import random
from change_screensize import get_screen_size
import logging
logger = logging.getLogger(__name__)

# ---------Colour constants
GREEN  = (0, 1, 0, 1)
RED    = (1, 0, 0, 1)
YELLOW = (1, 1, 0, 1)
WHITE  = (1, 1, 1, 1)
CYAN   = (0, 1, 1, 1)
BLUE   = (0, 0, 1, 1)

EXPLOSION_SPEED = 0.4


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
    def __truediv__(self, s): return Vector3(self.x/s, self.y/s, self.z/s)
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
            return Vector3()

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

    def __add__(self, o): return Vector2(self.x+o.x, self.y+o.y)
    def __sub__(self, o): return Vector2(self.x-o.x, self.y-o.y)
    def __mul__(self, s): return Vector2(self.x*s,   self.y*s)
    def __rmul__(self, s): return self.__mul__(s)
    def __truediv__(self, s): return Vector2(self.x/s, self.y/s)
    def __neg__(self): return Vector2(-self.x, -self.y)
    def __repr__(self): return f'Vector2({self.x:.2f},{self.y:.2f})'

    def dot(self, o):
        return self.x*o.x + self.y*o.y

    def length(self):
        return math.sqrt(self.x**2 + self.y**2)

    def normalize(self):
        return self / self.length() if self.length() else Vector2()

    def clone(self):
        return Vector2(self.x, self.y)


class WireframeObject:
    """
    A single wireframe mesh.

    Core attributes
    ---------------
    original_vertices : list[Vector3]      local-space vertices
    edges             : list[(int,int)]    index pairs (draw list)
    edges_with_faces  : list[(int,int,int,int)]
                        (v1, v2, face1, face2) — populated by Elite loaders;
                        used for hidden-line removal.  None if not available.
    face_normals      : list[Vector3]      local-space face normals (Elite only)
    face_rep_verts    : list[int]          one representative vertex index per
                        face — used to locate a point on the face plane for the
                        back-face dot-product test.  None if not available.
    position          : Vector3
    rotation          : Vector3            Euler angles (pitch_x, yaw_y, roll_z)
    scale             : float
    color             : (r,g,b,a)
    visible           : bool
    line_width        : float

    World-space copies (kept in sync by callers / get_world_vertices)
    ------------------------------------------------------------------
    position_in_world          : Vector3
    rotation_angles_in_world   : Vector3
    """

    def __init__(self,
                 position=None,
                 rotation=None,
                 scale=1.0,
                 color=GREEN,
                 visible=True,
                 line_width=2.0):
        self.position  = position or Vector3()
        self.rotation  = rotation or Vector3()
        self.scale     = scale
        self.color     = color
        self.visible   = visible
        self.line_width = line_width

        self.original_vertices = []
        self.edges             = []          # (v1, v2) draw list
        self.edges_with_faces  = None        # (v1, v2, f1, f2) — Elite only
        self.face_normals      = None        # list[Vector3] local space
        self.face_rep_verts    = None        # list[int] — one vert idx per face

        self.position_in_world         = self.position.clone()
        self.rotation_angles_in_world  = self.rotation.clone()

    # -------- Geometry helpers
    
    def get_world_vertices(self):
        """Transform local vertices → world space using Euler angles."""
        out = []
        rx = self.rotation_angles_in_world.x
        ry = self.rotation_angles_in_world.y
        rz = self.rotation_angles_in_world.z
        for v in self.original_vertices:
            v = v * self.scale
            v = v.rotate_z(rz).rotate_y(ry).rotate_x(rx)
            out.append(self.position_in_world + v)
        return out

    def get_world_vertices_from_transform(self, position, rotmat):
        """
        Transform local vertices using a rotation matrix (3 Vector3 rows)
        and a world position, bypassing the Euler-angle path entirely.

        rotmat: [right_vec, up_vec, forward_vec] — each a Vector3
        """
        right   = Vector3(rotmat[0].x, rotmat[0].y, rotmat[0].z)
        up      = Vector3(rotmat[1].x, rotmat[1].y, rotmat[1].z)
        forward = Vector3(rotmat[2].x, rotmat[2].y, rotmat[2].z)

        out = []
        for v in self.original_vertices:
            sv = v * self.scale
            world = Vector3(
                right.x*sv.x + up.x*sv.y + forward.x*sv.z,
                right.y*sv.x + up.y*sv.y + forward.y*sv.z,
                right.z*sv.x + up.z*sv.y + forward.z*sv.z,
            )
            out.append(position + world)
        return out

    def wireframe_to_dict(self):
        """Convert this object (and nested Vector3s) to a JSON-serialisable dict."""
        def vec_to_list(v):
            return [v.x, v.y, v.z] if v else [0, 0, 0]

        d = {
            "name":     getattr(self, 'name', 'unknown'),
            "header":   getattr(self, 'header', {}),
            "position": vec_to_list(self.position),
            "rotation": vec_to_list(self.rotation),
            "scale":    self.scale,
            "color":    list(self.color),
            "visible":  self.visible,
            "line_width": self.line_width,
            "original_vertices": [vec_to_list(v) for v in self.original_vertices],
            "edges":    self.edges,
            "position_in_world":        vec_to_list(self.position_in_world),
            "rotation_angles_in_world": vec_to_list(self.rotation_angles_in_world),
        }

        # --- Hidden-line removal fields (optional)
        if self.edges_with_faces is not None:
            d["edges_with_faces"] = [list(e) for e in self.edges_with_faces]

        if self.face_normals is not None:
            d["face_normals"] = [vec_to_list(n) for n in self.face_normals]

        if self.face_rep_verts is not None:
            d["face_rep_verts"] = self.face_rep_verts

        return d

# Built-in primitive shapes
class WireCube(WireframeObject):
    def __init__(self, size_x=1, size_y=1, size_z=1, **kw):
        super().__init__(**kw)
        hx, hy, hz = size_x/2, size_y/2, size_z/2
        self.original_vertices = [
            Vector3(-hx, -hy,  hz), Vector3( hx, -hy,  hz),
            Vector3( hx, -hy, -hz), Vector3(-hx, -hy, -hz),
            Vector3(-hx,  hy,  hz), Vector3( hx,  hy,  hz),
            Vector3( hx,  hy, -hz), Vector3(-hx,  hy, -hz),
        ]
        self.edges = [
            (0,1),(1,2),(2,3),(3,0),
            (4,5),(5,6),(6,7),(7,4),
            (0,4),(1,5),(2,6),(3,7),
        ]


class WirePyramid(WireframeObject):
    def __init__(self, base_size=1, height=1, **kw):
        super().__init__(**kw)
        h = base_size / 2
        self.original_vertices = [
            Vector3(-h, 0, -h), Vector3(h, 0, -h),
            Vector3( h, 0,  h), Vector3(-h, 0,  h),
            Vector3( 0, height, 0),
        ]
        self.edges = [
            (0,1),(1,2),(2,3),(3,0),
            (0,4),(1,4),(2,4),(3,4),
        ]


class Sun(WireframeObject):
    def __init__(self, radius=100, scale=65535, distance_scale=False, **kw):
        super().__init__(**kw)
        self.original_vertices = []
        self.is_star    = True
        self.star_radius = radius
        self.scale      = scale
        self.color      = (1.0, 0.95, 0.6, 1.0)
        self.distance_scale = distance_scale


class Sprite3D(WireframeObject):
    """Billboard sprite that always faces the camera."""
    def __init__(self, image_path, width=64, height=64,
                 distance_scale=False, scale=100, name='',**kw):
        super().__init__(**kw)
        self.original_vertices = []
        self.edges = []
        self.is_billboard    = True
        self.image_path      = image_path
        self.billboard_w     = width
        self.billboard_h     = height
        self.distance_scale  = distance_scale
        self.scale           = scale
        self.name = name
        if isinstance(image_path, str):
            self._image = scene.load_image_file(image_path)
        else:
            self._image = image_path


class WireSphere(WireframeObject):
    """Latitude/longitude wireframe sphere."""
    def __init__(self, radius=1, lat_lines=6, lon_lines=8, **kw):
        super().__init__(**kw)
        verts, edges = [], []

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
                edges.append((idx(i, j), idx(i, j+1)))
                edges.append((idx(i, j), idx(i+1, j)))

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
            Vector3(0,    0, 0), Vector3(size, 0,    0),
            Vector3(0,    0, 0), Vector3(0,    size, 0),
            Vector3(0,    0, 0), Vector3(0,    0,    size),
        ]
        self.edges       = [(0,1),(2,3),(4,5)]
        self.edge_colors = [RED, GREEN, BLUE]


class Camera:
    def __init__(self,
                 position=None,
                 yaw=0.0,
                 pitch=0.0,
                 roll=0.0,
                 look_yaw=0,
                 fov=math.radians(60),
                 z_near=5.0,
                 z_far=2000.0):
        self.position = position or Vector3()
        self.yaw      = yaw
        self.pitch    = pitch
        self.roll     = roll
        self.fov      = fov
        self.z_near   = z_near
        self.z_far    = z_far

    @property
    def focal_length(self):
        return 1.0 / math.tan(self.fov / 2)

    def forward(self):
        return Vector3(
            math.sin(self.yaw)  * math.cos(self.pitch),
            -math.sin(self.pitch),
            math.cos(self.yaw)  * math.cos(self.pitch)
        )

    def right(self):
        fwd = self.forward()
        world_up = Vector3(math.sin(self.roll), math.cos(self.roll), 0.0)
        if abs(fwd.dot(world_up)) > 0.99:
            world_up = Vector3(math.cos(self.roll), 0.0, -math.sin(self.roll))
        return fwd.cross(world_up).normalize()

    def up(self):
        return self.right().cross(self.forward()).normalize()

    def basis(self):
        fwd = self.forward()
        r   = self.right()
        u   = r.cross(fwd).normalize()
        return r, u, fwd


class Renderer:
    """
    Projects and draws a list of WireframeObjects from a Camera's POV.

    Parameters
    ----------
    depth_sort     : painter's algorithm, far objects first.
    backface_cull  : enable hidden-line removal for Elite ships.
                     Requires edges_with_faces, face_normals, face_rep_verts
                     on the object.  Falls back gracefully when absent.
    """

    def __init__(self,
                 depth_sort=True,
                 backface_cull=True,
                 default_line_width=2.0):
        self.depth_sort        = depth_sort
        self.backface_cull     = backface_cull
        self.default_line_width = default_line_width
    
    # Hidden-line removal
    
    def _rotate_normal(self, n, rx, ry, rz):
        """Rotate a local-space normal into world space using Euler angles."""
        return n.rotate_z(rz).rotate_y(ry).rotate_x(rx)

    def _visible_edge_set(self, obj, world_verts, cam_pos):
        """
        Return a set of edge indices that should be drawn.

        An edge is visible if at least one of its two adjacent faces is
        front-facing (normal points towards the camera).

        Edges stored with face1 == face2 (single-face / crease edges) are
        always included — hiding them creates ugly gaps on silhouettes.

        Falls back to returning all edge indices if the required face data
        is missing.
        """
        ewf = getattr(obj, 'edges_with_faces', None)
        fn  = getattr(obj, 'face_normals',     None)
        frv = getattr(obj, 'face_rep_verts',   None)

        if ewf is None or fn is None or frv is None:
            # No face data — draw everything
            return set(range(len(obj.edges)))

        # Rotate all face normals into world space once ---
        rx = obj.rotation_angles_in_world.x
        ry = obj.rotation_angles_in_world.y
        rz = obj.rotation_angles_in_world.z
        world_normals = [self._rotate_normal(n, rx, ry, rz) for n in fn]

        # Front-face test for each face ---
        # dot(world_normal, world_point_on_face - cam_pos) <= 0  →  front face
        num_faces = len(world_normals)
        face_front = []
        for fi in range(num_faces):
            rep_vi = frv[fi]
            if rep_vi is None or rep_vi >= len(world_verts):
                # No representative vertex; assume front-facing (safe default)
                face_front.append(True)
                continue
            n = world_normals[fi]
            p = world_verts[rep_vi]
            face_front.append(n.dot(p - cam_pos) <= 0)

        # Mark visible edges ---
        visible = set()
        for ei, e in enumerate(ewf):
            v1, v2, f1, f2 = e
            if f1 == f2:
                # Single-face edge — always draw (silhouette / crease)
                visible.add(ei)
            elif f1 < num_faces and f2 < num_faces:
                if face_front[f1] or face_front[f2]:
                    visible.add(ei)
            else:
                # Face index out of range — draw to be safe
                visible.add(ei)

        return visible
    
    # Main draw
    def draw(self, objects, camera, screen_size):
        sw, sh = screen_size.w, screen_size.h
        fl     = camera.focal_length

        visible_objs = [o for o in objects if o.visible]
        
        if self.depth_sort:
            visible_objs.sort(
                key=lambda o: (o.position_in_world - camera.position).length(),
                reverse=True
            )
        
        for obj in visible_objs:

            # Sprite billboard ---
            if getattr(obj, 'is_billboard', False):
                cam_pos = self._to_camera(obj.position_in_world, camera)
                
                if cam_pos.z > camera.z_far or cam_pos.z < camera.z_near:
                    if isinstance(obj._image, scene.SpriteNode):
                        obj._image.alpha = 0                        
                    continue
                screen_pt = self._project(cam_pos, fl, camera)
                if screen_pt is None:
                    if isinstance(obj._image, scene.SpriteNode):
                        obj._image.alpha = 0
                    continue
                w = obj.billboard_w
                h = obj.billboard_h
                if obj.distance_scale:
                    dist  = max(1.0, (obj.position_in_world - camera.position).length())
                    scale = fl / dist * obj.scale
                    w *= scale
                    h *= scale
                cx, cy = screen_pt
                if isinstance(obj._image, scene.SpriteNode):
                    obj._image.position = (cx, cy)
                    obj._image.alpha    = 1
                    obj._image.scale    = scale
                else:
                    if obj._image is None:
                        obj._image = scene.load_image_file(obj.image_path)
                    scene.image(obj._image, cx - w/2, cy - h/2, w, h)
                continue

            # Filled circle ---
            if getattr(obj, 'is_star', False):
                cam_pos   = self._to_camera(obj.position_in_world, camera)
                if cam_pos is None or cam_pos.z >= camera.z_far:
                    continue
                screen_pt = self._project(cam_pos, fl, camera)
                if screen_pt is None:
                    continue
                star_radius = getattr(obj, 'star_radius', 4.0)
                if getattr(obj, 'star_distance_scale', False):
                    dist = max(1.0, (obj.position_in_world - camera.position).length())
                    star_radius = star_radius * fl / dist * obj.scale
                star_color = getattr(obj, 'star_color', obj.color)
                scene.fill(*star_color)
                scene.stroke(0, 0, 0, 0)
                cx, cy = screen_pt
                scene.ellipse(cx - star_radius, cy - star_radius,
                              star_radius*2, star_radius*2)
                scene.fill(0, 0, 0, 0)
                continue

            # --- Wireframe mesh
            if hasattr(obj, 'rotmat_world'):
                world_verts = obj.get_world_vertices_from_transform(
                    obj.position_in_world, obj.rotmat_world
                )
            else:
                world_verts = obj.get_world_vertices()

            cam_verts  = [self._to_camera(v, camera) for v in world_verts]
            screen_pts = [self._project(v, fl, camera) for v in cam_verts]

            # Hidden-line removal — only when enabled and face data present
            if self.backface_cull:
                visible_edges = self._visible_edge_set(
                    obj, world_verts, camera.position
                )
            else:
                visible_edges = None      # draw all edges

            color          = obj.color
            line_width     = getattr(obj, 'line_width', self.default_line_width)
            has_edge_colors = hasattr(obj, 'edge_colors')
            scene.stroke_weight(line_width)

            vx, vy, vw, vh = getattr(self, 'viewport',
                                      scene.Rect(0, 0, sw, sh))

            for ei, (i1, i2) in enumerate(obj.edges):
                if visible_edges is not None and ei not in visible_edges:
                    continue          # hidden-line removal culled this edge

                p1, p2 = screen_pts[i1], screen_pts[i2]
                if p1 is None or p2 is None:
                    continue

                clipped = self._clip_line(
                    p1[0], p1[1], p2[0], p2[1],
                    vx, vy, vx + vw, vy + vh
                )
                if clipped is None:
                    continue

                edge_color = obj.edge_colors[ei] if has_edge_colors else color
                scene.stroke(*edge_color)
                scene.rect(0, 0, 0, 0)
                scene.line(*clipped)
            
    def explode(self, obj, camera, screen_size):
        """ Explosion helper """
        scene.no_fill()
        fl = camera.focal_length
        t  = getattr(obj, 'explosion_time', 1.0)
        world_verts = obj.get_world_vertices()
        center = obj.position_in_world

        for ei, (i1, i2) in enumerate(obj.edges):
            v1, v2 = world_verts[i1], world_verts[i2]
            if t > 0:
                edge_center = (v1 + v2) / 2
                direction   = (edge_center - center).normalize()
                offset      = direction * (t * 200)
                noise       = Vector3(
                    random.uniform(-5, 5),
                    random.uniform(-5, 5),
                    random.uniform(-5, 5)
                ) * t
                v1 += offset + noise
                v2 += offset + noise

            p1 = self._project(self._to_camera(v1, camera), fl, camera)
            p2 = self._project(self._to_camera(v2, camera), fl, camera)

            if p1 and p2:
                alpha      = max(0, 1.0 - t)
                edge_color = obj.color[:3] + (alpha,)
                scene.stroke(*edge_color)
                scene.rect(0, 0, 0, 0)
                scene.line(*p1, *p2)

    
    # -----Private geometry helpers
    
    def _clip_line(self, x1, y1, x2, y2, x_min, y_min, x_max, y_max):
        """Liang-Barsky line clip. Returns clipped (x1,y1,x2,y2) or None."""
        dx, dy = x2 - x1, y2 - y1
        p = [-dx, dx, -dy, dy]
        q = [x1 - x_min, x_max - x1, y1 - y_min, y_max - y1]
        t0, t1 = 0.0, 1.0
        for pi, qi in zip(p, q):
            if pi == 0:
                if qi < 0:
                    return None
            elif pi < 0:
                t0 = max(t0, qi / pi)
            else:
                t1 = min(t1, qi / pi)
        if t0 > t1:
            return None
        return (x1 + t0*dx, y1 + t0*dy, x1 + t1*dx, y1 + t1*dy)

    def _to_camera(self, world_v, camera):
        """World vertex → camera space using full roll/pitch/yaw basis."""
        v    = world_v - camera.position
        r, u, f = camera.basis()
        return Vector3(v.dot(r), v.dot(u), v.dot(f))

    def _project(self, cam_v, fl, camera):
        """Camera-space vertex → (screen_x, screen_y) or None if clipped."""
        if cam_v.z < camera.z_near or cam_v.z > camera.z_far:
            return None
        vp = getattr(self, 'viewport', None)
        if vp is None:
            return None
        sx = (cam_v.x * fl / cam_v.z) * vp.w + vp.center().x
        sy = (cam_v.y * fl / cam_v.z) * vp.h + vp.center().y
        return (sx, sy)


class EliteShip(WireframeObject):
    """
    Generic Elite ship wireframe built directly from BBC Micro assembly source.
    """
    def __init__(self, source_text, scale=1.0, **kwargs):
        super().__init__(scale=scale, **kwargs)
        parsed = self.parse_elite_ship_data(source_text)
        self._apply_parsed(parsed, scale=1.0)

    def _apply_parsed(self, parsed, scale=1.0):
        """Populate all mesh and face data from a parsed dict."""
        self.original_vertices = [
            Vector3(v['x']*scale, v['y']*scale, v['z']*scale)
            for v in parsed['vertices']
        ]
        # Simple (v1, v2) draw list — kept for compatibility
        self.edges = [(e['v1'], e['v2']) for e in parsed['edges']]

        # Extended edge list with face adjacency for hidden-line removal
        self.edges_with_faces = [
            (e['v1'], e['v2'], e['face1'], e['face2'])
            for e in parsed['edges']
        ]

        # Face normals in local space
        self.face_normals = [
            Vector3(f['nx'], f['ny'], f['nz'])
            for f in parsed['faces']
        ]

        # One representative vertex index per face — first vertex that
        # lists this face in its face membership list.
        num_faces = len(parsed['faces'])
        rep = [None] * num_faces
        for vi, v in enumerate(parsed['vertices']):
            for fi in v.get('faces', []):
                if fi < num_faces and rep[fi] is None:
                    rep[fi] = vi
        self.face_rep_verts = rep

    def parse_elite_ship_data(self, source_text):
        return _parse_elite_source(source_text)


def _parse_elite_source(source_text):
    """
    Parse Elite BBC Micro assembly ship data into Python dicts.

    Returns {'vertices': [...], 'edges': [...], 'faces': [...]}
    """
    vertices, edges, faces = [], [], []

    def strip_comment(line):
        idx = line.find('\\')
        return line[:idx] if idx >= 0 else line

    vertex_re = re.compile(
        r'\bVERTEX\s+(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,'
        r'\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,'
        r'\s*(\d+)'
    )
    edge_re = re.compile(
        r'\bEDGE\s+(\d+)\s*,\s*(\d+)\s*,'
        r'\s*(\d+)\s*,\s*(\d+)\s*,'
        r'\s*(\d+)'
    )
    face_re = re.compile(
        r'\bFACE\s+(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,'
        r'\s*(\d+)'
    )

    for raw_line in source_text.splitlines():
        line = strip_comment(raw_line).strip()
        if not line:
            continue

        m = vertex_re.search(line)
        if m:
            vertices.append({
                'x': int(m.group(1)), 'y': int(m.group(2)), 'z': int(m.group(3)),
                'faces':      [int(m.group(i)) for i in range(4, 8)],
                'visibility': int(m.group(8))
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


class GetEliteShips:
    """scrapes elite.bbcelite.com """
    def __init__(self, version, ship_locs):
        self.ship_objects = []
        for name in ship_locs:
            url = (f'https://elite.bbcelite.com/{version}/main/variable/'
                   f'ship_{name.lower()}.html')
            obj = self.ship_from_url(url)
            logger.debug(f'got {name}')
            self.ship_objects.append(obj)
        save_wireframes_to_json(self.ship_objects, 'files/Elite_ships.json')
        
    def ship_from_url(self, url, **kwargs):
        parsed = self.fetch_elite_ship(url)
        obj    = EliteShip.__new__(EliteShip)
        WireframeObject.__init__(obj, **kwargs)
        obj._apply_parsed(parsed)
        obj.name   = parsed['name']
        obj.header = parsed['header']
        return obj

    def fetch_elite_ship(self, url):
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')

        match = re.search(
            r'<div[^>]*class="[^"]*codeBlockWrapper[^"]*"[^>]*>\s*'
            r'<pre[^>]*class="[^"]*codeBlock[^"]*"[^>]*>(.*?)</pre>',
            html, re.DOTALL
        )
        if not match:
            match = re.search(
                r'<pre[^>]*class="[^"]*codeBlock[^"]*"[^>]*>(.*?)</pre>',
                html, re.DOTALL
            )
        if not match:
            raise ValueError(f"No codeBlock <pre> found at {url}")

        raw         = match.group(1)
        source_text = re.sub(r'<[^>]+>', '', raw)
        source_text = (source_text
                       .replace('&amp;',  '&')
                       .replace('&lt;',   '<')
                       .replace('&gt;',   '>')
                       .replace('&#39;',  "'")
                       .replace('&quot;', '"')
                       .replace('&nbsp;', ' '))

        name_match = re.search(r'/(ship_[^/]+)\.html', url)
        ship_name  = name_match.group(1).upper() if name_match else 'UNKNOWN'

        parsed           = _parse_elite_source(source_text)
        parsed['name']   = ship_name
        parsed['header'] = self._parse_header(source_text)
        return parsed

    def _parse_header(self, source_text):
        header   = {}
        last_val = None

        for line in source_text.splitlines():
            line = line.strip()
            if re.search(r'_VERTICES\b', line):
                break

            m_dir  = re.match(r'EQU[BW]\s+([%\d\s\*]+)\\(.+)', line)
            m_cont = re.match(r'^\\(.+)', line)

            if m_dir:
                raw_val      = m_dir.group(1).strip()
                comment_part = m_dir.group(2)
                if raw_val.startswith('%'):
                    try:    value = int(raw_val[1:], 2)
                    except: value = raw_val
                else:
                    try:    value = eval(raw_val, {"__builtins__": {}})
                    except: value = raw_val
                last_val = value
                self._add_header_item(header, comment_part, value)
            elif m_cont and last_val is not None:
                self._add_header_item(header, m_cont.group(1), last_val)

        return header

    def _add_header_item(self, header, comment_part, value):
        label = comment_part.strip().split('=')[0].strip()
        if label:
            header[label] = value


def save_wireframes_to_json(wireframe_list, filename):
    serializable_list = [obj.wireframe_to_dict() for obj in wireframe_list]
    try:
        with open(filename, 'w') as f:
            json.dump(serializable_list, f, indent=2)
        print(f"Successfully saved {len(wireframe_list)} objects to {filename}")
    except Exception as e:
        print(f"Failed to save data: {e}")


def _obj_from_dict(item):
    """Reconstruct a WireframeObject (with optional face data) from a dict."""
    obj = WireframeObject(
        position=Vector3(*item["position"]),
        rotation=Vector3(*item["rotation"]),
        scale=item["scale"],
        color=tuple(item["color"]),
        visible=item["visible"],
        line_width=item["line_width"]
    )
    obj.name   = item.get("name", "unknown")
    obj.header = item.get("header", {})

    obj.original_vertices = [Vector3(*v) for v in item["original_vertices"]]
    obj.edges             = [tuple(e) for e in item["edges"]]

    if 'edge_colors' in item:
        obj.edge_colors = list(item["edge_colors"])

    obj.position_in_world        = Vector3(*item["position_in_world"])
    obj.rotation_angles_in_world = Vector3(*item["rotation_angles_in_world"])

    # --- Hidden-line removal fields ---
    if "edges_with_faces" in item:
        obj.edges_with_faces = [tuple(e) for e in item["edges_with_faces"]]

    if "face_normals" in item:
        obj.face_normals = [Vector3(*n) for n in item["face_normals"]]

    if "face_rep_verts" in item:
        obj.face_rep_verts = item["face_rep_verts"]

    return obj


def load_wireframes_from_json(filename):
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        return [_obj_from_dict(item) for item in data]
    except FileNotFoundError:
        print(f"Error: The file {filename} was not found.")
        raise FileNotFoundError
    except Exception as e:
        print(f"An error occurred while loading: {e}")
        return []


def load_ships_from_json(filename):
    """Alias kept for backward compatibility."""
    return load_wireframes_from_json(filename)


class Demo(scene.Scene):
    def setup(self):                
        self.camera = Camera(
            position=Vector3(0, 0, -500),
            fov=math.radians(60),
            z_far=10000
        )
        self.renderer = Renderer(depth_sort=True, backface_cull=1)
        self.t = 0

        self.objects = [
            WireCube(50, 50, 50,     position=Vector3(-80, 0, 0),   color=GREEN),
            WirePyramid(60, 80,      position=Vector3( 80, 0, 0),   color=CYAN),
            WireSphere(40, lat_lines=10, lon_lines=16,
                       position=Vector3(0, 0, 100),                 color=YELLOW),
            WireAxes(60),
        ]

        try:
            objects = load_wireframes_from_json('files/Elite_ships.json')
        except Exception:
            ship_locs = [
                'missile','coriolis','escape_pod','plate','canister',
                'Boulder','Asteroid','Splinter','Shuttle','Transporter',
                'Cobra_Mk_3','Python','Boa','Anaconda','Rock_hermit',
                'Viper','Sidewinder','Mamba','Krait','Adder','Gecko',
                'Cobra_Mk_1','Worm','Cobra_Mk_3_p','Asp_Mk_2','Python_p',
                'Fer_de_lance','Moray','Thargoid','Thargon','Constrictor',
                'logo','Cougar','Dodo'
            ]
            ships = GetEliteShips('6502sp', ship_locs)
            objects = ships.ship_objects
            
        for ship in objects:
            ship.position = Vector3(
                uniform(-400, 400),
                uniform(-400, 400),
                uniform(800, 1000)
            )
            ship.scale = uniform(0.5, 1.5)
            ship.color = choice([GREEN, RED, YELLOW, WHITE, CYAN, BLUE])
            ship.explosion_time = random.random()
            self.objects.append(ship)
        self._exploding_obj = None
        self._explosion_t   = random.random()
        
    def _pick_new_explosion(self):
        candidates = [o for o in self.objects if hasattr(o, 'name')]
        if candidates:
            obj = random.choice(candidates)
            obj.explosion_time  = 0.0
            self._exploding_obj = obj
            self._explosion_t   = 0.0
                 
    def update(self):
        # make all object spin and move forward and backward
        # periodically explode on object
        self.t += self.dt * .0005
        looping_sine = abs(math.sin((math.pi * self.t) / 10))
        for obj in self.objects[:]:
            obj.rotation.y = self.t
            obj.rotation.z = self.t
            obj.position_in_world = obj.position.clone() + Vector3(0, 0, 1000 * looping_sine)
            obj.rotation_angles_in_world = obj.rotation.clone()
        
        if self._exploding_obj is None:
            self._pick_new_explosion()
        else:
            self._explosion_t += self.dt * EXPLOSION_SPEED
            self._exploding_obj.explosion_time = self._explosion_t
            if self._explosion_t >= 1.0:                
                self.objects.remove(self._exploding_obj)
                self._exploding_obj = None
                
    def draw(self):
        scene.background(0, 0, 0)        
        self.renderer.viewport = scene.Rect(0, 0, *get_screen_size())

        for obj in self.objects:
            if obj == self._exploding_obj:
                self.renderer.explode(obj, self.camera, self.size)
            else:
                self.renderer.draw([obj], self.camera, self.size)        


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    # g = Demo()
    # g.setup()
    #g.draw()
    scene.run(Demo(), show_fps=True, multi_touch=True)
