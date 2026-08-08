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
# Filled polygons added July 2026:
# compute triangle_strip for each face to produce coloured dynamic face
# face coordinates are extracted from face_with_edges data.
# face_colors can be applied per face.
# if not specified, shading is apolied depending on angle

import math
import scene
import urllib.request
import re
import json
from collections import defaultdict
import random
import colorsys
import matplotlib.colors as mcolors
from change_screensize import get_screen_size
import constants as cs
import traceback
from joystick import Joystick
import logging
logger = logging.getLogger(__name__)

# ---------Colour constants
GREEN = (0, 1, 0, 1)
RED = (1, 0, 0, 1)
YELLOW = (1, 1, 0, 1)
WHITE = (1, 1, 1, 1)
CYAN = (0, 1, 1, 1)
BLUE = (0, 0, 1, 1)

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


def normal_for_face(pts):
    """Newell's method: robust polygon normal for a planar quad/n-gon."""
    
    n = [0, 0, 0]
    cnt = len(pts)
    for i in range(cnt):
        cur = pts[i]
        nxt = pts[(i + 1) % cnt]
        n[0] += (cur[1] - nxt[1]) * (cur[2] + nxt[2])
        n[1] += (cur[2] - nxt[2]) * (cur[0] + nxt[0])
        n[2] += (cur[0] - nxt[0]) * (cur[1] + nxt[1])
    length = math.sqrt(n[0]**2 + n[1]**2 + n[2]**2)
    if length == 0:
        return n
    return [round(n[0] / length, 3), round(n[1] / length, 3), round(n[2] / length, 3)]

                  
def get_face_vertex_indices(edges_with_faces):
    """
    Reconstructs the ordered vertex sequence for each face in a mesh given edge-face connections.
    
    Parameters:
        edges_with_faces (list of lists): List where each item is [v1, v2, f1, f2]
        
    Returns:
        dict: A mapping of {face_index: [ordered_vertex_indices]}
    """
    # Step 1: Collect all undirected edges belonging to each face
    face_edges = defaultdict(list)
    for v1, v2, f1, f2 in edges_with_faces:
        face_edges[f1].append((v1, v2))
        
        # Avoid duplicating self-referencing boundary edges (where f1 == f2)
        if f1 != f2:
            face_edges[f2].append((v1, v2))

    face_vertices = {}

    # Step 2: Assemble the edges into a continuous, ordered vertex loop for each face
    for face_id, edges in face_edges.items():
        if not edges:
            continue
            
        # Build an adjacency lookup for this specific face's perimeter
        adj = defaultdict(list)
        for u, v in edges:
            adj[u].append(v)
            adj[v].append(u)

        # Traverse the adjacency graph to form a continuous closed loop
        start_vert = edges[0][0]
        loop = [start_vert]
        visited_verts = {start_vert}
        curr = edges[0][1]

        while curr != start_vert and curr not in visited_verts:
            loop.append(curr)
            visited_verts.add(curr)
            
            # Move to the next connected neighbor not yet visited
            neighbors = adj[curr]
            next_vert = None
            for n in neighbors:
                if n not in visited_verts or (len(loop) > 2 and n == start_vert):
                    next_vert = n
                    break
            
            if next_vert is None:
                break  # Prevents infinite loops on non-manifold or malformed faces
                
            curr = next_vert

        face_vertices[face_id] = loop

    # Return sorted by face index (0, 1, 2, ...)
    return dict(sorted(face_vertices.items()))

        
def polygon_centroid(vertices, eps=1e-7):
    """
    Calculates the (x, y) centroid of a simple 2D polygon.
    
    Parameters:
        vertices (list of tuples/lists): Polygon coordinates [(x0, y0), (x1, y1), ...]
        eps (float): Epsilon threshold for zero-area check.
        
    Returns:
        tuple: (cx, cy) centroid coordinates, or None if the polygon is degenerate/collapsed.
    """
    n = len(vertices)
    if n < 3:
        return None  # Cannot form a 2D polygon with < 3 vertices

    signed_area = 0.0
    cx = 0.0
    cy = 0.0

    for i in range(n):
        x0, y0 = vertices[i]
        x1, y1 = vertices[(i + 1) % n]  # Wraps around to the first vertex

        # Common cross-product term: (x_i * y_{i+1} - x_{i+1} * y_i)
        cross = (x0 * y1) - (x1 * y0)

        signed_area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross

    signed_area *= 0.5

    # Guard against zero-area / collapsed line polygons
    if abs(signed_area) < eps:
        return None

    # Final centroid coordinates
    factor = 1.0 / (6.0 * signed_area)
    cx *= factor
    cy *= factor

    return (cx, cy)


def is_ccw(polygon):
    """Check if the polygon vertices are ordered counter-clockwise."""
    area = 0.0
    n = len(polygon)
    for i in range(n):
        j = (i + 1) % n
        area += polygon[i][0] * polygon[j][1]
        area -= polygon[j][0] * polygon[i][1]
    return area > 0


def cross_product_2d(a, b, c):
    """Calculates the 2D cross product of vectors (b - a) and (c - a)."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def point_in_triangle(p, a, b, c):
    """Determines if point p lies strictly inside triangle abc."""
    cp1 = cross_product_2d(a, b, p)
    cp2 = cross_product_2d(b, c, p)
    cp3 = cross_product_2d(c, a, p)
    
    has_neg = (cp1 < 0) or (cp2 < 0) or (cp3 < 0)
    has_pos = (cp1 > 0) or (cp2 > 0) or (cp3 > 0)
    
    return not (has_neg and has_pos)


def is_collinear_or_zero_area(vertices, eps=1e-7):
    """
    Checks if a polygon has collapsed into a line segment or point
    by calculating its total signed Area via the Shoelace formula.
    """
    if len(vertices) < 3:
        return True

    total_area = 0.0
    n = len(vertices)
    for i in range(n):
        j = (i + 1) % n
        total_area += vertices[i][0] * vertices[j][1]
        total_area -= vertices[j][0] * vertices[i][1]

    # If the signed area is virtually zero, all points are collinear or degenerate
    return abs(total_area * 0.5) < eps


def triangulate_ear_clipping(vertices, eps=1e-7):
    """
    Triangulates a simple polygon using Ear Clipping.
    Guarded against collapsed/collinear/degenerate polygons, returning [] if invalid.
    """
    # Guard 1: Must have at least 3 vertices
    if not vertices or len(vertices) < 3:
        return []

    # Guard 2: Check if vertices collapse to a straight line or zero-area polygon
    if is_collinear_or_zero_area(vertices, eps=eps):
        return []

    n = len(vertices)
    indices = list(range(n))

    # Determine winding order using shoelace sum
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += vertices[i][0] * vertices[j][1]
        area -= vertices[j][0] * vertices[i][1]

    if area < 0:
        indices.reverse()

    triangles = []
    
    # Track unclipped vertices to prevent infinite loops on non-simple geometry
    max_attempts = len(indices) * len(indices)
    attempts = 0

    while len(indices) > 3:
        ear_found = False
        num_verts = len(indices)

        for i in range(num_verts):
            prev_idx = indices[(i - 1) % num_verts]
            curr_idx = indices[i]
            next_idx = indices[(i + 1) % num_verts]

            a, b, c = vertices[prev_idx], vertices[curr_idx], vertices[next_idx]

            # 2D cross product check for convexity
            cp = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cp <= eps:  # Ignore collinear or reflex ears
                continue

            # Check if any remaining vertex lies inside the candidate ear triangle
            is_valid_ear = True
            for j in range(num_verts):
                if j in ((i - 1) % num_verts, i, (i + 1) % num_verts):
                    continue
                p = vertices[indices[j]]
                
                # Point-in-triangle test via cross products
                cp1 = (a[0] - p[0]) * (b[1] - p[1]) - (a[1] - p[1]) * (b[0] - p[0])
                cp2 = (b[0] - p[0]) * (c[1] - p[1]) - (b[1] - p[1]) * (c[0] - p[0])
                cp3 = (c[0] - p[0]) * (a[1] - p[1]) - (c[1] - p[1]) * (a[0] - p[0])

                if (cp1 >= -eps and cp2 >= -eps and cp3 >= -eps) or \
                   (cp1 <= eps and cp2 <= eps and cp3 <= eps):
                    is_valid_ear = False
                    break

            if is_valid_ear:
                triangles.append((prev_idx, curr_idx, next_idx))
                indices.pop(i)
                ear_found = True
                break

        attempts += 1
        # Guard 3: Fallback safety net for invalid/self-crossing loops
        if not ear_found or attempts > max_attempts:
            return []

    triangles.append((indices[0], indices[1], indices[2]))
    return triangles

        
def in_frame(points):
    # points is a list of tuples
    # check if all in frame_rect
    for p in points:
       if not cs.FLIGHT_RECT.contains_point(scene.Point(*p)):
          return False
    return True
    
    
def triangles_to_strip(triangles):
    """
    Converts an unsorted list of triangles into a single continuous triangle strip
    using degenerate triangles to bridge discontinuities.
    """
    if not triangles:
        return []

    strip = list(triangles[0])

    for t in triangles[1:]:
        # Bridge the last vertex of the previous triangle to the first vertex
        # of the new triangle using degenerate (zero-area) triangles.
        last_vert = strip[-1]
        first_vert = t[0]

        # Double the boundary vertices to create zero-area triangles
        strip.extend([last_vert, first_vert])
        
        # Enforce consistent winding order if needed by checking strip parity
        if len(strip) % 2 != 0:
            strip.extend([t[0], t[1], t[2]])
        else:
            strip.extend([t[1], t[0], t[2]])

    return strip


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
        self.position = position or Vector3()
        self.rotation = rotation or Vector3()
        self.scale = scale
        self.color = color
        self.visible = visible
        self.line_width = line_width

        self.original_vertices = []
        self.edges = []          # (v1, v2) draw list
        self.edges_with_faces = None        # (v1, v2, f1, f2) — Elite only
        self.face_normals = None        # list[Vector3] local space
        self.face_rep_verts = None        # list[int] — one vert idx per face

        self.position_in_world = self.position.clone()
        self.rotation_angles_in_world = self.rotation.clone()

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
        right = Vector3(rotmat[0].x, rotmat[0].y, rotmat[0].z)
        up = Vector3(rotmat[1].x, rotmat[1].y, rotmat[1].z)
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
            Vector3(-hx, -hy,  hz), Vector3(hx, -hy,  hz),
            Vector3(hx, -hy, -hz), Vector3(-hx, -hy, -hz),
            Vector3(-hx, hy,  hz), Vector3(hx, hy,  hz),
            Vector3(hx, hy, -hz), Vector3(-hx, hy, -hz),
        ]
        self.edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),
            (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7),
        ]


class WirePyramid(WireframeObject):
    def __init__(self, base_size=1, height=1, **kw):
        super().__init__(**kw)
        h = base_size / 2
        self.original_vertices = [
            Vector3(-h, 0, -h), Vector3(h, 0, -h),
            Vector3(h, 0, h), Vector3(-h, 0,  h),
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
        self.color = (1.0, 0.95, 0.6, 1.0)
        self.distance_scale = distance_scale


class Sprite3D(WireframeObject):
    """Billboard sprite that always faces the camera."""
    def __init__(self, image_path, width=64, height=64,
                 distance_scale=False, scale=100, name='', **kw):
        super().__init__(**kw)
        self.original_vertices = []
        self.edges = []
        self.is_billboard = True
        self.image_path = image_path
        self.billboard_w = width
        self.billboard_h = height
        self.distance_scale = distance_scale
        self.scale = scale
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
            Vector3(0, 0, 0), Vector3(0, 0, size),
        ]
        self.edges = [(0, 1), (2, 3), (4, 5)]
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
        self.yaw = yaw
        self.pitch = pitch
        self.roll = roll
        self.fov = fov
        self.z_near = z_near
        self.z_far = z_far

    @property
    def focal_length(self):
        return 1.0 / math.tan(self.fov / 2)

    def forward(self):
        return Vector3(
            math.sin(self.yaw) * math.cos(self.pitch),
            -math.sin(self.pitch),
            math.cos(self.yaw) * math.cos(self.pitch)
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
        r = self.right()
        u = r.cross(fwd).normalize()
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
                 default_line_width=3.0,
                 fill=True):
        self.depth_sort = depth_sort
        self.backface_cull = backface_cull
        self.default_line_width = default_line_width
        self.fill = fill
        self.show_index = False
        self.get_normals = False
        self.hue_shift = 0.0
    
    # Hidden-line removal
    
    def _rotate_normal(self, n, rx, ry, rz):
        """Rotate a local-space normal into world space using Euler angles."""
        return n.rotate_z(rz).rotate_y(ry).rotate_x(rx)
        
    def _rotate_normal_matrix(self, n, rotmat):
        """Rotate a local-space normal into world space using a rotation matrix."""
        right = Vector3(rotmat[0].x, rotmat[0].y, rotmat[0].z)
        up = Vector3(rotmat[1].x, rotmat[1].y, rotmat[1].z)
        forward = Vector3(rotmat[2].x, rotmat[2].y, rotmat[2].z)
        return Vector3(
            right.x*n.x + up.x*n.y + forward.x*n.z,
            right.y*n.x + up.y*n.y + forward.y*n.z,
            right.z*n.x + up.z*n.y + forward.z*n.z,
        )
        
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
        def get_frv(ewf, fn):
           # choose a vertex index which is linked to face
           if fn is None:
             return None
           no_faces = len(fn)
           frv = []
           for f_no in range(no_faces):
             
             for edge_face in ewf:
               if f_no in edge_face[2:]:
                  frv.append(edge_face[0])
                  break
             else:
                frv.append(None)
           return frv
        ewf = getattr(obj, 'edges_with_faces', None)
        fn = getattr(obj, 'face_normals', None)
        frv = get_frv(ewf, fn)
        if ewf is None or fn is None or frv is None:
            # No face data — draw everything
            return set(range(len(obj.edges)))

         # Rotate all face normals into world space once ---
        if hasattr(obj, 'rotmat_world'):
            world_normals = [self._rotate_normal_matrix(n, obj.rotmat_world) for n in fn]
        else:
            rx = obj.rotation_angles_in_world.x
            ry = obj.rotation_angles_in_world.y
            rz = obj.rotation_angles_in_world.z
            world_normals = [self._rotate_normal(n, rx, ry, rz) for n in fn]

        # Front-face test for each face ---
        # dot(world_normal, world_point_on_face - cam_pos) <= 0  →  front face
        # face_rep_verts are list of world_vertices associated with each face.
        # face_rep_verts can be duplicated or none
        num_faces = len(world_normals)
        face_front = []
        self.face_angles = []
        single = True
        for fi in range(num_faces):
            rep_vi = frv[fi]
            if rep_vi is None or rep_vi >= len(world_verts):
                # No representative vertex; assume front-facing (safe default)
                face_front.append(True)
                self.face_angles.append(0)
                continue
            n = world_normals[fi]
            p = world_verts[rep_vi]
            p = p - cam_pos
            n1 = n.normalize()
            p1 = p.normalize()
            angle = n1.dot(p1)
            self.face_angles.append(angle)
            face_front.append(angle <= 0)

        # Mark visible edges ---
        visible = set()
        for ei, e in enumerate(ewf):
            v1, v2, f1, f2 = e
            if f1 == f2 and single:
                # Single-face edge — always draw (silhouette / crease)
                visible.add(ei)
            elif f1 < num_faces and f2 < num_faces:
                if face_front[f1] or face_front[f2]:
                    visible.add(ei)
            else:
                # Face index out of range — draw to be safe
                visible.add(ei)

        return visible
        
    def get_line_color(self, obj, ei):
       # colour of a segment is defined by
       # list of colour for each segment
       # colour of single line from a dictionary with default
       # colour from edge_color attribute
       # colour from color attribute
       #
       try:
           if hasattr(obj, 'edge_color'):
               default = obj.edge_color
           else:
               default = obj.color
           if hasattr(obj, 'edge_colors'):
               if isinstance(obj.edge_colors, list):
                   color = mcolors.to_rgb(obj.edge_colors[ei])
               elif isinstance(obj.edge_colors, dict):
                   color = mcolors.to_rgb(obj.edge_colors.get(str(ei), default))
           else:
               color = mcolors.to_rgb(default)
           color = self.shift_hue(color, self.hue_shift)    
           scene.stroke(*color)
       except ValueError:
           raise ValueError("Color name not found")
           
    def get_face_color(self, obj, face_id):
        if hasattr(obj, 'face_colors'):
            if isinstance(obj.face_colors, list):
                color = mcolors.to_rgb(obj.face_colors[face_id])
            elif isinstance(obj.face_colors, dict):
                color = mcolors.to_rgb(obj.face_colors.get(str(face_id), obj.color))
        else:
            color = mcolors.to_rgb(obj.color)
        color = self.shift_hue(color, self.hue_shift)    
        # shade the fill
        # directly normal is brightest
        shade = -self.face_angles[face_id]
        color = Vector3(*color) * shade
        color = color.to_tuple
        scene.fill(color)
        
    def shift_hue(self, rgb, hue_shift):
        """rgb: (r,g,b) in 0-1 floats. hue_shift: 0-1 boosts red"""
        r, g, b = rgb[:3]
        r = min(1.0, r + hue_shift)
        g = g * (1.0 - hue_shift)
        b = b * (1.0 - hue_shift)
        return (r, g, b)
        # if we want hue shift
        h, l, s = colorsys.rgb_to_hls(*rgb[:3])
        h = (h + hue_shift) % 1.0
        return colorsys.hls_to_rgb(h, l, s)
                
    # Main draw
    def draw(self, objects, camera, screen_size):
        sw, sh = screen_size.w, screen_size.h
        fl = camera.focal_length

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
                    dist = max(1.0, (obj.position_in_world - camera.position).length())
                    scale = fl / dist * obj.scale
                    w *= scale
                    h *= scale
                cx, cy = screen_pt
                tint_color = self.shift_hue((1, 1, 1), self.hue_shift)  + (1,)  
                
                if isinstance(obj._image, scene.SpriteNode):
                    obj._image.position = (cx, cy)
                    obj._image.alpha = 1
                    if obj._image.shader is not None:
                        r, g, b = self.shift_hue((1, 1, 1), self.hue_shift) 
                        obj._image.shader.set_uniform('u_tint_color', (r, g, b, 1.0))
                    else:
                         obj._image.color = self.shift_hue((1, 1, 1), self.hue_shift)                     
                    obj._image.scale = scale
                else:
                    if obj._image is None:
                        obj._image = scene.load_image_file(obj.image_path)
                    scene.tint(*tint_color)
                    scene.image(obj._image, cx - w/2, cy - h/2, w, h)
                    scene.tint(1, 1, 1, 1) # reset,tint
                continue

            # Filled circle ---
            if getattr(obj, 'is_star', False):
                cam_pos = self._to_camera(obj.position_in_world, camera)
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
            
            self.cam_verts = [self._to_camera(v, camera) for v in world_verts]
            screen_pts = [self._project(v, fl, camera) for v in self.cam_verts]

            # Hidden-line removal — only when enabled and face data present
            
            visible_edges = self._visible_edge_set(
                    obj, world_verts, camera.position
                )
            if not self.backface_cull:
                visible_edges = None      # draw all edges
                                               
            if obj.edges_with_faces is not None:
                edges = [ewf[:2] for ewf in obj.edges_with_faces]
                
                if self.fill:
                   # draw faces first to allowlines to overlay
                   self.apply_triangle_strips(obj, screen_pts)
            else:
                edges = obj.edges
            
            line_width = getattr(obj, 'line_width', self.default_line_width)
            scene.stroke_weight(line_width)

            vx, vy, vw, vh = getattr(self, 'viewport',
                                     scene.Rect(0, 0, sw, sh))
            lines = 0
            points= []
            for ei, (i1, i2) in enumerate(edges):
                if visible_edges is not None and ei not in visible_edges:                    
                    continue          # hidden-line removal culled this edge
                    
                p1, p2 = screen_pts[i1], screen_pts[i2]
                points.append((p1, p2))
                if p1 is None or p2 is None:
                    
                    continue

                clipped = self._clip_line(
                    p1[0], p1[1], p2[0], p2[1],
                    vx, vy, vx + vw, vy + vh
                )
                if clipped is None:
                    continue
                
                self.get_line_color(obj, ei)
                if self.show_index:
                   # display index number at centre
                   x1, y1, x2, y2 = clipped
                   midx, midy = (x1+x2)/2, (y1+y2)/2 + 5
                   scene.tint(1, 1, 1, 1)
                   scene.text(str(ei), font_name='Copperplate', font_size=15, x=midx, y=midy,        alignment=5)
                   
                scene.rect(0, 0, 0, 0)
                scene.line(*clipped)
                lines += 1                
                           
                                       
    def explode(self, obj, camera, screen_size):
        """ Explosion helper """
        scene.no_fill()
        fl = camera.focal_length
        t = getattr(obj, 'explosion_time', 1.0)
        world_verts = obj.get_world_vertices()
        center = obj.position_in_world
        if obj.edges_with_faces is not None:
            edges = [ewf[:2] for ewf in obj.edges_with_faces]
        else:
            edges = obj.edges
        for ei, (i1, i2) in enumerate(edges):
            v1, v2 = world_verts[i1], world_verts[i2]
            if t > 0:
                edge_center = (v1 + v2) / 2
                direction = (edge_center - center).normalize()
                offset = direction * (t * 200)
                noise = Vector3(
                    random.uniform(-5, 5),
                    random.uniform(-5, 5),
                    random.uniform(-5, 5)
                ) * t
                v1 += offset + noise
                v2 += offset + noise

            p1 = self._project(self._to_camera(v1, camera), fl, camera)
            p2 = self._project(self._to_camera(v2, camera), fl, camera)

            if p1 and p2:
                alpha = max(0, 1.0 - t)
                if isinstance(obj.color, (list, tuple)):
                    edge_color = obj.color[:3]
                else:
                  if obj.color in mcolors.CSS4_COLORS:
                      edge_color = mcolors.to_rgb(obj.color)
                  else:
                     raise ValueError("Color name not found")
                edge_color = edge_color + (alpha,)
                scene.stroke(*edge_color)
                scene.rect(0, 0, 0, 0)
                scene.line(*p1, *p2)
                
    def sort_faces(self, faces):
        coords = self.cam_verts
        
        def get_avg_z(indices, point_list):
            """Calculates the average z value for a set of list indices."""
            return sum(point_list[idx].z for idx in indices) / len(indices)
        
        # Sort dictionary by descending average z-value
        sorted_data = dict(
            sorted(
                faces.items(),
                key=lambda item: get_avg_z(item[1], coords),
                reverse=True  # Set to False if you want ascending order
            )
        )
        return sorted_data
 
    def apply_triangle_strips(self, obj, screen_pts):
     
        """This converts the 2d  polygon faces of the 3d object into
          triangle_strips for solid filled display
          
          3d world coordinates need to be converted to 2d screen coordinates
          They need to be clipoed to the screen viewport, possibly adding
          more vertices.
          Polygons are then converted to triangles, and finally assembled
          to triangle strips for display
        """
          
        bounds = (self.viewport.min_x, self.viewport.min_y,
                  self.viewport.max_x, self.viewport.max_y)
        faces = get_face_vertex_indices(obj.edges_with_faces)
        
        # TODO sort faces by z to draw furthest first
        # faces = self.sort_faces(faces)
        for face_id, verts in faces.items():
            try:
                if self.get_normals:
                    points = [obj.original_vertices[v].to_tuple for v in verts]
                    normal = normal_for_face(points[::-1])
                    print(face_id, verts, normal)
                if self.face_angles[face_id] >= 0:
                   continue
                self.get_face_color(obj, face_id)
                
                polygon = [screen_pts[vert] for vert in verts if screen_pts[vert]]
                
                # check all points in FRAME_RECT
                polygon = self.clip_polygon_to_rect(polygon, bounds)
                tri_indices = triangulate_ear_clipping(polygon)
                strip_indices = triangles_to_strip(tri_indices)
                
                points = [polygon[index] for index in strip_indices]
                scene.triangle_strip(points)
                       
                # plot face number at centre of face
                centroid = polygon_centroid(polygon)
                if self.show_index and centroid:
                    # display index number at centre
                    midx, midy = centroid
                    scene.tint(0, 0, 0, 1)
                    scene.text(str(face_id), font_name='Copperplate', font_size=15, x=midx, y=midy, alignment=5)
            except (TypeError, AttributeError, IndexError):
                logger.debug(f'{traceback.format_exc()}')
                logger.debug(f'{obj.name} {face_id} {self.face_angles}')
               
    # -----Private geometry helpers
    def clip_polygon_to_rect(self, polygon, bounds):
        """
        Clips a 2D polygon to an axis-aligned rectangle using the
        Sutherland-Hodgman algorithm.
    
        Parameters:
            polygon (list of tuples/lists): Polygon vertices [(x0, y0), (x1, y1), ...]
            
        Returns:
            list of tuples: Vertices of the clipped polygon [(x0, y0), ...],
                            or [] if completely outside.
        """
        
        def is_inside(p, stage):
            if p is None:
               return False
            x, y = p
            x_min, y_min, x_max, y_max = bounds
            match stage:
                case 0:
                    return x >= x_min
                case 1:
                    return x <= x_max
                case 2:
                    return y >= y_min
                case 3:
                    return y <= y_max
           
        def intersect(p1, p2, stage):
           """Calculates the intersection of line segment p1-p2 with boundary stage."""
           if p1 is None:
              raise ValueError
           x1, y1 = p1
           x2, y2 = p2
           
           x_min, y_min, x_max, y_max = bounds
           match stage:
               case 0:    # Left boundary (x = x_min)
                  y = y1 + (y2 - y1) * (x_min - x1) / (x2 - x1)
                  return (x_min, y)
               case 1:  # Right boundary (x = x_max)
                  y = y1 + (y2 - y1) * (x_max - x1) / (x2 - x1)
                  return (x_max, y)
               case 2:  # Top boundary (y = y_min)
                   x = x1 + (x2 - x1) * (y_min - y1) / (y2 - y1)
                   return (x, y_min)
               case 3:  # Bottom boundary (y = y_max)
                  x = x1 + (x2 - x1) * (y_max - y1) / (y2 - y1)
                  return (x, y_max)
        
        output_verts = polygon[:]
        # Process all four boundary clipping stages sequentially
        for stage in range(4):
            if not output_verts:
                break
    
            input_verts = output_verts
            output_verts = []
    
            s = input_verts[-1]  # Start with the last vertex to close loop
    
            for e in input_verts:
                e_inside = is_inside(e, stage)
                s_inside = is_inside(s, stage)
    
                if e_inside:
                    if s_inside:
                        output_verts.append(e)
                    else:
                        output_verts.append(intersect(s, e, stage))
                        output_verts.append(e)
                elif s_inside:
                    output_verts.append(intersect(s, e, stage))
    
                s = e

        return output_verts

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
        v = world_v - camera.position
        r, u, f = camera.basis()
        return Vector3(v.dot(r), v.dot(u), v.dot(f))        

    def _project(self, cam_v, fl, camera, clip_to_screen=True):
        """Camera-space vertex → (screen_x, screen_y) or None if clipped.
        
        Args:
            cam_v: Vector3 in camera space.
            fl: Focal length.
            camera: Camera object containing z_near and z_far.
            clip_to_screen (bool): If True, returns None when (sx, sy) 
                                   fall outside the viewport bounds.
        """
        # 1. Near/Far plane clipping (depth check)
        if clip_to_screen:
            if cam_v.z < camera.z_near or cam_v.z > camera.z_far:
                return None
            
        vp = getattr(self, 'viewport', None)
        if vp is None:
            return None
        
        # Guard against points behind or directly on the near plane
        if cam_v.z > camera.z_near:
            # Safety clamp for unclipped fallback to avoid division by zero/sign flips
            z = 0.0001 if cam_v.z <= 0 else cam_v.z
        else:
            z = cam_v.z
        # 2. Project to screen space   
        sx = (cam_v.x * fl / cam_v.z) * vp.w + vp.center().x
        sy = (cam_v.y * fl / cam_v.z) * vp.h + vp.center().y
        return (int(sx), int(sy))
        
    def _project_line(self, p1_cam, p2_cam, fl, camera):
        """Projects a 3D line segment in camera space to 2D screen coordinates,
        automatically clipping against the near plane if it crosses behind the camera.
        """
        z_near = camera.z_near
        
        # Case 1: Both points are entirely behind the near plane
        if p1_cam.z < z_near and p2_cam.z < z_near:
            return None
            
        # Case 2: Point 1 is behind the near plane, clip it to z_near
        if p1_cam.z < z_near:
            t = (z_near - p1_cam.z) / (p2_cam.z - p1_cam.z)
            p1_cam = Vector3(
                p1_cam.x + t * (p2_cam.x - p1_cam.x),
                p1_cam.y + t * (p2_cam.y - p1_cam.y),
                z_near
            )
        # Case 3: Point 2 is behind the near plane, clip it to z_near
        elif p2_cam.z < z_near:
            t = (z_near - p2_cam.z) / (p1_cam.z - p2_cam.z)
            p2_cam = Vector3(
                p2_cam.x + t * (p1_cam.x - p2_cam.x),
                p2_cam.y + t * (p1_cam.y - p2_cam.y),
                z_near
            )
            
        # Both points are now safely in front of / on the near plane
        screen_pt1 = self._project(p1_cam, fl, camera, clip_to_screen=False)
        screen_pt2 = self._project(p2_cam, fl, camera, clip_to_screen=False)
        
        return screen_pt1, screen_pt2
        
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
        save_wireframes_to_json(self.ship_objects, 'files/Elite_ships_.json')
        
    def ship_from_url(self, url, **kwargs):
        parsed = self.fetch_elite_ship(url)
        obj = EliteShip.__new__(EliteShip)
        WireframeObject.__init__(obj, **kwargs)
        obj._apply_parsed(parsed)
        obj.name = parsed['name']
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

        raw = match.group(1)
        source_text = re.sub(r'<[^>]+>', '', raw)
        source_text = (source_text
                       .replace('&amp;',  '&')
                       .replace('&lt;',   '<')
                       .replace('&gt;',   '>')
                       .replace('&#39;',  "'")
                       .replace('&quot;', '"')
                       .replace('&nbsp;', ' '))

        name_match = re.search(r'/(ship_[^/]+)\.html', url)
        ship_name = name_match.group(1).upper() if name_match else 'UNKNOWN'

        parsed = _parse_elite_source(source_text)
        parsed['name'] = ship_name
        parsed['header'] = self._parse_header(source_text)
        return parsed

    def _parse_header(self, source_text):
        header = {}
        last_val = None

        for line in source_text.splitlines():
            line = line.strip()
            if re.search(r'_VERTICES\b', line):
                break

            m_dir = re.match(r'EQU[BW]\s+([%\d\s\*]+)\\(.+)', line)
            m_cont = re.match(r'^\\(.+)', line)

            if m_dir:
                raw_val = m_dir.group(1).strip()
                comment_part = m_dir.group(2)
                if raw_val.startswith('%'):
                    try:
                        value = int(raw_val[1:], 2)
                    except Exception:
                        value = raw_val
                else:
                    try:
                        value = eval(raw_val, {"__builtins__": {}})
                    except Exception:
                        value = raw_val
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
        visible=item["visible"],
        line_width=item["line_width"]
    )
    obj.name = item.get("name", "unknown")
    obj.header = item.get("header", {})

    obj.original_vertices = [Vector3(*v) for v in item["original_vertices"]]
    if 'edges' in item:
       obj.edges = [tuple(e) for e in item["edges"]]
    if isinstance(item["color"], str):
        obj.color = item["color"]
    else:
        obj.color = tuple(item["color"])
    if 'edge_color' in item:
        obj.edge_color = item["edge_color"]
    if 'edge_colors' in item:
        obj.edge_colors = item["edge_colors"]
    # list or dict
    if 'face_colors' in item:
        obj.face_colors = item["face_colors"]

    obj.position_in_world = Vector3(*item["position_in_world"])
    obj.rotation_angles_in_world = Vector3(*item["rotation_angles_in_world"])

    # --- Hidden-line removal fields ---
    if "edges_with_faces" in item:
        obj.edges_with_faces = [tuple(e) for e in item["edges_with_faces"]]

    if "face_normals" in item:
        obj.face_normals = [Vector3(*n) for n in item["face_normals"]]

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
        self.select = 4
        W, H = get_screen_size()
        self.up = scene.LabelNode('Up', position=(W-100, 800), parent=self)
        self.down = scene.LabelNode('Down', position=(W-100, 750), parent=self)
        self.text = scene.LabelNode(str(self.select), position=(W-100, 850), parent=self)
        self.fill_mode = scene.LabelNode('Fill', position=(W-100, 650), parent=self)
        self.numbers_mode = scene.LabelNode('Show Numbers', position=(W-100, 600), parent=self)
        self.zoom_value = scene.LabelNode('Distance 100', position=(W-100, 350), parent=self)
        self.zoom_in = scene.LabelNode('Zoom In', position=(W-100, 250), parent=self)
        self.zoom_out = scene.LabelNode('Zoom Out', position=(W-100, 200), parent=self)
        
        self.camera = Camera(
            position=Vector3(0, 0, -500),
            fov=math.radians(60),
            z_far=10000
        )
        self.joystick = Joystick(position=cs.JOYSTICK_1_POSITION,
                                 color='white',
                                 show_xy=False,
                                 msg='',
                                 radius=cs.JOYSTICK_1_RADIUS)
        self.add_child(self.joystick)
        
        self.zoom = 1
        self.show_numbers = True
        self.renderer = Renderer(depth_sort=True, backface_cull=True, fill=True)
        self.t = 0
        self.renderer.show_index = True
        self.x = self.y = 0.0

        self.objects = [
            WireCube(50, 50, 50, position=Vector3(-80, 0, 0), color=GREEN),
            WirePyramid(60, 80, position=Vector3(80, 0, 0), color=CYAN),
            WireSphere(40, lat_lines=10, lon_lines=16,
                       position=Vector3(0, 0, 100),                 color=YELLOW),
            WireAxes(60),
        ]

        try:
            objects = load_wireframes_from_json('files/Elite_ships.json')
            objects1 = load_wireframes_from_json('stationv.json')
            objects = objects + objects1
            pass
        except Exception:
            ship_locs = [
                'missile', 'coriolis', 'escape_pod', 'plate', 'canister',
                'Boulder', 'Asteroid', 'Splinter', 'Shuttle', 'Transporter',
                'Cobra_Mk_3', 'Python', 'Boa', 'Anaconda', 'Rock_hermit',
                'Viper', 'Sidewinder', 'Mamba', 'Krait', 'Adder', 'Gecko',
                'Cobra_Mk_1', 'Worm', 'Cobra_Mk_3_p', 'Asp_Mk_2', 'Python_p',
                'Fer_de_lance', 'Moray', 'Thargoid', 'Thargon', 'Constrictor',
                'logo', 'Cougar', 'Dodo'
            ]
            ships = GetEliteShips('6502sp', ship_locs)
            objects = ships.ship_objects
            
        for ship in objects[:]:
            ship.position = Vector3(0, 0, 200)
            # print(ship.position)
            ship.scale = 1.0
            # ship.color = choice([GREEN, RED, YELLOW, WHITE, CYAN, BLUE])
            ship.explosion_time = random.random()
            self.objects.append(ship)
        self._exploding_obj = None
        for i, ship in enumerate(self.objects):
           if hasattr(ship, 'name'):
               print(i, ship.name)
        self._explosion_t = random.random()
        
    def _pick_new_explosion(self):
        candidates = [o for o in self.objects if hasattr(o, 'name')]
        if candidates:
            obj = random.choice(candidates)
            obj.explosion_time = 0.0
            self._exploding_obj = obj
            self._explosion_t = 0.0
            
    def touch_began(self, touch):
        if self.joystick.bbox.contains_point(touch.location):
            self.joystick.touch_began(touch)
            self.is_joystick_active = True
            
    def touch_moved(self, touch):
        """Processes movement independently for each active touch ID."""
        self.moved = True
        if self.joystick.bbox.contains_point(touch.location):
            self.joystick.touch_moved(touch)
            self.x = self.joystick.x
            self.y = self.joystick.y
                     
    def touch_ended(self, touch):
       if self.up.bbox.contains_point(touch.location):
           self.select = min(self.select + 1, len(self.objects) - 1)
       elif self.down.bbox.contains_point(touch.location):
           self.select = max(self.select - 1, 0)
       elif self.fill_mode.bbox.contains_point(touch.location):
           self.renderer.fill = not self.renderer.fill
       elif self.numbers_mode.bbox.contains_point(touch.location):
           self.renderer.show_index = not self.renderer.show_index
       elif self.zoom_in.bbox.contains_point(touch.location):
           self.zoom -= 1
           self.zoom_value.text = f'Distance {self.zoom *100}'
       elif self.zoom_out.bbox.contains_point(touch.location):
           self.zoom += 1
           self.zoom_value.text = f'Distance {self.zoom *100}'
       
       self.joystick.touch_ended(touch)
       self.is_joystick_active = False
           
    def update(self):
        # make all object spin and move forward and backward
        # periodically explode on object
        
        try:
           self.text.text = f'{self.select} {self.objects[self.select].name}'
        except AttributeError:
           self.text.text = f'{self.select}'
        self.t += self.dt * .0001
        self.joystick.update()
        if self.joystick.x == 0.0 and self.joystick.y == 0.0:
            looping_sine = abs(math.sin((math.pi * self.t) / 10))
            for obj in self.objects[self.select: self.select+1]:
                obj.rotation.y = self.t / 10
                obj.rotation.x = self.t / 5
                # obj.position.z = looping_sine
                obj.position_in_world = obj.position.clone() + Vector3(0, 0, 1000 * looping_sine)
                obj.rotation_angles_in_world = obj.rotation.clone()
        else:
            for obj in self.objects[self.select: self.select+1]:
                obj.rotation.x = self.joystick.y * math.pi
                obj.rotation.y = self.joystick.x * math.pi

                obj.position_in_world = obj.position.clone() + Vector3(0, 0, self.zoom*100)
                obj.rotation_angles_in_world = obj.rotation.clone()
        """
        if self._exploding_obj is None:
            self._pick_new_explosion()
        else:
            self._explosion_t += self.dt * EXPLOSION_SPEED
            self._exploding_obj.explosion_time = self._explosion_t
            if self._explosion_t >= 1.0:
                self.objects.remove(self._exploding_obj)
                self._exploding_obj = None
        """
    def draw(self):
        scene.background(0, 0, 0)
        self.renderer.viewport = scene.Rect(0, 0, *get_screen_size())

        for obj in self.objects[self.select:self.select+1]:
            if obj == self._exploding_obj:
                self.renderer.explode(obj, self.camera, self.size)
            else:
                self.renderer.draw([obj], self.camera, self.size)

      
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    from time import time
    g = Demo()
    g.setup()
    g.renderer.get_normals = False
    g.update()
    #
    t = time()
    g.draw()
    print(time()-t)
    scene.run(Demo(), show_fps=True, multi_touch=True)
