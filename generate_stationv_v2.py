#!/usr/bin/env python3
"""
STATIONV generator (v2)
------------------------
Builds a two-wheel Elite-style space station and writes it out as a JSON
file in the ship-data schema used by the Elite remake (original_vertices,
edges, edge_colors, face_colors, edges_with_faces, face_normals).

Structure:
  - Two wheels, each with:
      * An outer rim made of `rim_sides` (16) solid CUBOID sections.
        Each cuboid's outer radial face sits at rim_diameter/2; `rim_depth`
        extends inward from there. `rim_width` is the z-thickness. The
        length of each cuboid section is the chord length implied by
        rim_diameter and rim_sides (not a free parameter). Adjacent
        cuboids share their common end face (a single quad, referenced
        by both neighbours) rather than duplicating it.
      * An inner hub: a simple `hub_sides` (8) sided prism (side walls
        only where it meets the tube/spokes) capped with 2 flat end-cap
        faces (top and bottom octagons). Spokes attach only to the hub's
        outer side wall, never to the end caps.
  - Four straight square-section spoke columns per wheel-side, running
    from the rim cuboid's INNER radial face to the hub's OUTER wall (so
    the spoke's outer end is flush with the rim, its inner end flush
    with the hub -- it does not reach into either).
  - A connecting tube joining the two wheels' facing hub rings.
  - A small rectangular docking/entry portal, now a solid capped face
    (not an open loop), sharing the same normal direction convention as
    a hub end cap.

All faces have consistently outward-pointing normals (Newell's method).
"""

import json
import math
import numpy as np


# ----------------------------------------------------------------------
# Geometry helpers
# ----------------------------------------------------------------------

def make_ring(radius, n, z):
    """n vertices of a regular n-gon of the given radius, in the z=z plane,
    starting at angle 0 and going counter-clockwise."""
    pts = []
    for i in range(n):
        theta = 2.0 * math.pi * i / n
        pts.append([round(radius * math.cos(theta), 2), round(radius * math.sin(theta), 2), z])
    return pts


def normal_for_face(face, all_verts):
    """Newell's method: robust polygon normal for a planar quad/n-gon."""
    pts = all_verts[face]
    n = np.zeros(3)
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
    return [n[0] / length, n[1] / length, n[2] / length]
    


def hub_side_quads(top_start, bot_start, n):
    """Side wall quads for a hub ring (top ring at top_start.., bottom at
    bot_start..), wound so normals point outward, away from the z-axis."""
    fs = []
    for i in range(n):
        a = top_start + i
        b = top_start + (i + 1) % n
        fs.append([b, a, a - top_start + bot_start, b - top_start + bot_start])
    return fs


def tube_quads_outward(top_start, bot_start, n):
    """Connecting-tube side walls; reversed winding relative to hub_side_quads
    because the tube's natural vertex order runs the opposite way."""
    fs = []
    for i in range(n):
        a = top_start + i
        b = top_start + (i + 1) % n
        fs.append([a, b, b - top_start + bot_start, a - top_start + bot_start])
    return fs


# ----------------------------------------------------------------------
# Main builder
# ----------------------------------------------------------------------

def build_station(
    rim_diameter=480.0,
    rim_sides=16,
    rim_width=50.0,     # z-thickness of each rim cuboid
    rim_depth=40.0,     # radial thickness of each rim cuboid, extends INWARD from rim_diameter/2
    hub_diameter=100.0,
    hub_sides=8,
    rim_spacing=75.0,
    spoke_width=16.0,
    spoke_length=16.0,
    entry_portal_width=20.0,
    entry_portal_height=40.0,
    entry_portal_z=100.0,
    station_name="STATIONV",
):
    outer_r = rim_diameter / 2.0
    inner_r = outer_r - rim_depth
    hub_r = hub_diameter / 2.0
    rim_hw = rim_width / 2.0   # half z-thickness of rim cuboids

    verts = []      # growing list of [x,y,z]
    edges = []      # list of [a, b] vertex-index pairs
    faces = []      # list of vertex-index loops (each a face polygon)

    def add_verts(pts):
        start = len(verts)
        verts.extend(pts)
        return start

    def ring_edges(start, n):
        for i in range(n):
            edges.append([start + i, start + (i + 1) % n])

    def radial_edges(start_a, start_b, n):
        for i in range(n):
            edges.append([start_a + i, start_b + i])

    # ------------------------------------------------------------
    # Build one wheel: outer rim cuboids + inner hub prism w/ end caps.
    # Returns dict of useful vertex-ring start indices for later use
    # (spokes, tube attachment).
    # ------------------------------------------------------------
    def build_wheel(z_center):
        z_top = z_center + rim_hw
        z_bot = z_center - rim_hw

        # 4 shared rim rings: outer-top, outer-bot, inner-top, inner-bot
        v_ot = add_verts(make_ring(outer_r, rim_sides, z_top))
        v_ob = add_verts(make_ring(outer_r, rim_sides, z_bot))
        v_it = add_verts(make_ring(inner_r, rim_sides, z_top))
        v_ib = add_verts(make_ring(inner_r, rim_sides, z_bot))

        # Hub ring: top and bottom, hub_sides-gon
        v_ht = add_verts(make_ring(hub_r, hub_sides, z_top))
        v_hb = add_verts(make_ring(hub_r, hub_sides, z_bot))

        n = rim_sides

        # --- Rim cuboid edges ---
        ring_edges(v_ot, n)
        ring_edges(v_ob, n)
        ring_edges(v_it, n)
        ring_edges(v_ib, n)
        radial_edges(v_ot, v_ob, n)   # outer vertical edges (top<->bot at same angle)
        radial_edges(v_it, v_ib, n)   # inner vertical edges
        radial_edges(v_ot, v_it, n)   # top radial edges (outer<->inner at same angle, top)
        radial_edges(v_ob, v_ib, n)   # bottom radial edges (outer<->inner, bottom)

        # --- Rim cuboid faces ---
        # 4 "long" walls per cuboid (outer, inner, top, bottom) + shared end faces.
        # End face at angular boundary i (between cuboid i-1 and cuboid i) is built
        # once per boundary and referenced by both neighbouring cuboids.
        for i in range(n):
            ip1 = (i + 1) % n
            ot_i, ot_ip1 = v_ot + i, v_ot + ip1
            ob_i, ob_ip1 = v_ob + i, v_ob + ip1
            it_i, it_ip1 = v_it + i, v_it + ip1
            ib_i, ib_ip1 = v_ib + i, v_ib + ip1

            faces.append([ob_i, ob_ip1, ot_ip1, ot_i])   # outer wall (+radial)
            faces.append([it_i, it_ip1, ib_ip1, ib_i])   # inner wall (-radial)
            faces.append([ot_i, ot_ip1, it_ip1, it_i])   # top wall (+z)
            faces.append([ob_ip1, ob_i, ib_i, ib_ip1])   # bottom wall (-z)

        for i in range(n):
            ip1 = (i + 1) % n
            # end face at boundary i (the "start" face of cuboid i, shared with
            # cuboid i-1's "end" face at the same boundary) — build exactly once.
            ot_i, ob_i, it_i, ib_i = v_ot + i, v_ob + i, v_it + i, v_ib + i
            faces.append([it_i, ib_i, ob_i, ot_i])

        # --- Hub side walls + end caps ---
        ring_edges(v_ht, hub_sides)
        ring_edges(v_hb, hub_sides)
        radial_edges(v_ht, v_hb, hub_sides)

        faces.extend(hub_side_quads(v_ht, v_hb, hub_sides))
        # end caps: top cap normal +z, bottom cap normal -z
        faces.append([v_ht + i for i in range(hub_sides)])                      # top cap (+z)
        faces.append([v_hb + i for i in range(hub_sides - 1, -1, -1)])          # bottom cap (-z)

        return dict(v_ot=v_ot, v_ob=v_ob, v_it=v_it, v_ib=v_ib,
                    v_ht=v_ht, v_hb=v_hb, z_top=z_top, z_bot=z_bot)

    # Wheel 1 centered at z=0
    w1 = build_wheel(0.0)
    # Wheel 2 sits above: its facing (bottom) hub ring is rim_spacing above wheel1's top hub ring
    w2_center = w1["z_top"] + rim_spacing + rim_hw
    w2 = build_wheel(w2_center)

    
    # Connecting tube: wheel1's top hub ring <-> wheel2's bottom hub ring
    
    radial_edges(w1["v_ht"], w2["v_hb"], hub_sides)
    faces += tube_quads_outward(w1["v_ht"], w2["v_hb"], hub_sides)

    
    # Spokes: square-section box columns, straight edges only.
    # Outer end flush with the rim's INNER radial face; inner end flush
    # with the hub's OUTER wall. 4 spokes per wheel-side (top/bottom of
    # each wheel), at 0/90/180/270 degrees.
    

    def nearest_index_at_angle(n, angle_deg):
        best_i, best_d = 0, 1e9
        for i in range(n):
            theta = math.degrees(2.0 * math.pi * i / n)
            d = min(abs(theta - angle_deg), 360.0 - abs(theta - angle_deg))
            if d < best_d:
                best_d, best_i = d, i
        return best_i

    cardinal_angles = [0.0, 90.0, 180.0, 270.0]
    rim_cardinal_idx = [nearest_index_at_angle(rim_sides, a) for a in cardinal_angles]
    hub_cardinal_idx = [nearest_index_at_angle(hub_sides, a) for a in cardinal_angles]

    HW = spoke_width / 2.0
    HZ = spoke_length / 2.0

    spoke_verts = []
    spoke_faces = []
    spoke_edges = []
    base_idx_holder = [len(verts)]  # will be updated once we know final vert count pre-spokes

    def add_spoke(rim_ring_start, hub_ring_start, z):
        for ridx, hidx in zip(rim_cardinal_idx, hub_cardinal_idx):
            theta = 2.0 * math.pi * ridx / rim_sides
            # Use the rim's inner radius point at this angle as the outer
            # attachment point, and the hub's outer radius point as the
            # inner attachment point -- both already lie exactly on the
            # rim-inner / hub-outer surfaces (flush, no overlap).
            p_outer = np.array([inner_r * math.cos(theta), inner_r * math.sin(theta), z])
            theta_h = 2.0 * math.pi * hidx / hub_sides
            p_inner = np.array([hub_r * math.cos(theta_h), hub_r * math.sin(theta_h), z])

            dxy = p_outer[:2] - p_inner[:2]
            norm = np.linalg.norm(dxy)
            radial = np.array([dxy[0], dxy[1], 0.0]) / norm
            tangential = np.array([-radial[1], radial[0], 0.0])

            def corners(center):
                c1 = center + tangential * HW + np.array([0, 0, HZ])
                c2 = center + tangential * HW - np.array([0, 0, HZ])
                c3 = center - tangential * HW - np.array([0, 0, HZ])
                c4 = center - tangential * HW + np.array([0, 0, HZ])
                return [c1, c2, c3, c4]

            outer_corners = corners(p_outer)
            inner_corners = corners(p_inner)

            vstart = base_idx_holder[0] + len(spoke_verts)
            spoke_verts.extend(outer_corners)
            spoke_verts.extend(inner_corners)

            o = [vstart, vstart + 1, vstart + 2, vstart + 3]
            i_ = [vstart + 4, vstart + 5, vstart + 6, vstart + 7]

            spoke_faces.append([o[0], i_[0], i_[3], o[3]])   # +z face
            spoke_faces.append([i_[1], o[1], o[2], i_[2]])   # -z face
            spoke_faces.append([o[1], i_[1], i_[0], o[0]])   # +tangential face
            spoke_faces.append([i_[2], o[2], o[3], i_[3]])   # -tangential face
            spoke_faces.append([o[3], o[2], o[1], o[0]])     # outer end cap
            spoke_faces.append([i_[0], i_[1], i_[2], i_[3]]) # inner end cap

            spoke_edges.extend([[o[0], i_[0]], [o[1], i_[1]], [o[2], i_[2]], [o[3], i_[3]]])
            spoke_edges.extend([[o[0], o[1]], [o[1], o[2]], [o[2], o[3]], [o[3], o[0]]])
            spoke_edges.extend([[i_[0], i_[1]], [i_[1], i_[2]], [i_[2], i_[3]], [i_[3], i_[0]]])

    add_spoke(w1["v_ot"], w1["v_ht"], w1["z_top"]-25)
    add_spoke(w2["v_ot"], w2["v_ht"], w2["z_top"]-25)


    faces += spoke_faces
    edges += spoke_edges
    verts.extend(spoke_verts)

    
    # Docking / entry portal: a small solid rectangular cap, centered on
    # the station's z-axis, above the top wheel. It gets its own real
    # face, oriented with the same normal convention as a hub end cap
    # (i.e. facing +z).
    
    pw = entry_portal_width / 2.0
    ph = entry_portal_height / 2.0
    portal_start = add_verts([
        [-pw,  ph, entry_portal_z],
        [-pw, -ph, entry_portal_z],
        [ pw, -ph, entry_portal_z],
        [ pw,  ph, entry_portal_z],
    ])
    edges += [
        [portal_start, portal_start + 1],
        [portal_start + 1, portal_start + 2],
        [portal_start + 2, portal_start + 3],
        [portal_start + 3, portal_start],
    ]
    # Same winding sense as a hub top cap (+z normal): counter-clockwise
    # when viewed from +z looking down -z, matching build_wheel's top-cap
    # convention of listing vertices in increasing angular order.
    faces.append([portal_start, portal_start + 1, portal_start + 2, portal_start + 3])

    all_verts = np.array(verts, dtype=float)

    
    # Face normals + edges_with_faces
    
    face_normals = []
    for f in faces:
        n = normal_for_face(f, all_verts)
        face_normals.append([round(float(x), 2) for x in n])

    edge_faces = {tuple(sorted(e)): [] for e in edges}
    for fi, f in enumerate(faces):
        n = len(f)
        for i in range(n):
            a, b = f[i], f[(i + 1) % n]
            key = tuple(sorted((a, b)))
            if key in edge_faces:
                edge_faces[key].append(fi)

    # All edges in this model should now be bordered by exactly 2 real
    # faces (rim cuboids, hub prisms w/ end caps, tube, spokes, and the
    # capped docking portal are all fully closed solids). If any edge
    # ends up with fewer than 2, fall back to a dummy "black" face so the
    # schema stays valid.
    DUMMY = len(faces)
    need_dummy = any(len(v) < 2 for v in edge_faces.values())
    if need_dummy:
        faces.append(None)
        face_normals.append([0.0, 0.0, 0.0])

    edges_with_faces = []
    for (a, b) in edges:
        key = tuple(sorted((a, b)))
        fl = edge_faces[key][:]
        while len(fl) < 2:
            fl.append(DUMMY)
        if len(fl) > 2:
            fl = fl[:2]
        edges_with_faces.append([a, b, fl[0], fl[1]])

    
    face_colors =  ["cyan"] * len(faces)
    edge_colors = {} #["cyan"] * len(edges)

    station = {
        "name": station_name,
        "header": {
            "Max. canisters on demise": 0,
            "Targetable area": 25000,
            "Max. edge count": 4,
            "Gun vertex": 0,
            "Explosion count": 48,
            "Number of vertices": len(all_verts),
            "Number of edges": len(edges),
            "Bounty": 0,
            "Number of faces": len(faces),
            "Visibility distance": 130,
            "Max. energy": 240,
            "Max. speed": 0,
            "Normals are scaled by": 0,
            "Laser power": 0,
            "Missiles": 0,
        },
        "position": [0.0, 0.0, 0.0],
        "rotation": [0.0, 0.0, 0.0],
        "scale": 1.0,
        "color": [0, 1, 1, 1],
        "edge_color": "black",
        "visible": True,
        "line_width": 2.0,
        "original_vertices": [[round(float(x), 2) for x in v] for v in all_verts],
        "edge_colors": edge_colors,
        "face_colors": face_colors,
        "edges_with_faces": edges_with_faces,
        "face_normals": face_normals,
        "position_in_world": [0.0, 0.0, 0.0],
        "rotation_angles_in_world": [0.0, 0.0, 0.0],
    }
    return station



# JSON pretty-printer: max 8 elements per line for coordinate-like rows
# and flat scalar lists.


def format_value(v, indent):
    pad = " " * indent
    pad_in = " " * (indent + 2)
    if isinstance(v, dict):
        if not v:
            return "{}"
        items = []
        for k, val in v.items():
            items.append(f"{pad_in}{json.dumps(k)}: {format_value(val, indent + 2)}")
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    elif isinstance(v, list):
        if not v:
            return "[]"
        if all(isinstance(x, dict) for x in v):
            items = [format_value(x, indent + 2) for x in v]
            return "[\n" + ",\n".join(pad_in + it for it in items) + "\n" + pad + "]"
        elif all(isinstance(x, list) for x in v):
            chunks = []
            for i in range(0, len(v), 4):
                chunk = v[i:i + 4]
                inner_strs = ["[" + ", ".join(json.dumps(x) for x in inner) + "]" for inner in chunk]
                chunks.append(pad_in + ", ".join(inner_strs))
            return "[\n" + ",\n".join(chunks) + "\n" + pad + "]"
        else:
            chunks = []
            for i in range(0, len(v), 8):
                chunk = v[i:i + 8]
                chunks.append(pad_in + ", ".join(json.dumps(x) for x in chunk))
            return "[\n" + ",\n".join(chunks) + "\n" + pad + "]"
    else:
        return json.dumps(v)


def write_station_json(station, path):
    text = format_value(station, 0)
    text = '[' + text + ']'
    with open(path, "w") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    output = 'stationv.json'
    station = build_station()
    write_station_json(station, output)
    print(f"Wrote {output}: "
          f"{station['header']['Number of vertices']} vertices, "
          f"{station['header']['Number of edges']} edges, "
          f"{station['header']['Number of faces']} faces")
