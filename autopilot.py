# Modified and reimagined autopilot code
# Autopilot acquires Planet North Pole, then
# Initial Point for station alignment, then
# Station entrance
#
# if docking computer not fitted/ enabled,
# guidance cross will show directions

# TODO needs more development to achieve entry at
# any location.

import math
from math import sin, cos, atan2
from scene import Point
from vector import Vector, unit_vector, vector_dot_product
from wireframe_3d import Vector3
import constants as cs
from constants import logger


def _cos(deg):
    return math.cos(math.radians(deg))


def sgn(x):
    if x > 0:
        return 1
    elif x < 0:
        return -1
    return 0

        
NOSEV = 2
ROOFV = 1
SIDEV = 0

# Phase constants
POLE_ALTITUDE = 10000
IP_DIST = 2000    # units ahead of station nose
IP2_DIST = 6000    # outer waypoint, used when approaching from wrong side

# Arrival thresholds
CLOSE_TO_POLE = 200
CLOSE_TO_IP = 200
CLOSE_TO_STATION = 600
DOCKED_DIST = 160
                
# Alignment thresholds (cosines)
ALIGNED_TIGHT = _cos(5)    # 0.9962 - good enough to accelerate
ALIGNED_LOOSE = _cos(15)   # 0.9659 - broadly pointing at target
ON_SLOT_AXIS = _cos(13)   # 0.9744 - dir_to_bay threshold
FACING_AWAY = _cos(160)  # -0.9397 - facing away from station


class Pilot:
    """
    The auto-pilot logic for docking and NPC navigation.
    Based on Elite - The New Kind (C.J. Pinder).
    Also contains similar logic to display flight director
    """
    
    def __init__(self, gs):
        self.universe = gs.universe
        self.auto_pilot_active = False
        self.gs = gs
        self.flight_phase = None
        self.target_loc = Vector()
        self.angle = 0
        self.distance_to_target = 0
        
        self.integral_roll = 0
        self.prev_error_roll = 0
        self.integral_climb = 0
        self.prev_error_climb = 0
        self.escape = False
   
    # Experimental functions

    def get_angles(self, target_x, target_y, target_z):
        # Calculate Yaw
        yaw = math.degrees(math.atan2(target_x, target_z))
        
        # Calculate Pitch
        dist_horizontal = math.sqrt(target_x**2 + target_z**2)
        pitch = math.degrees(math.atan2(-target_y, dist_horizontal))
        return yaw, pitch
                                                           
    def steer_to_origin(self, target, fast=False):
        """Return (roll, pitch) to steer target unit vector toward (0, 0, -1)."""
        x, y, z = unit_vector(target).to_tuple
    
        # Invert the rotation formulas for small angles:
        # x' = x*cos(a) + y*sin(a) → to zero x, we want alpha = -atan2(x, y)
        # y' = y*cos(b) - z*sin(b) → to zero y, we want beta  =  atan2(y, z)
        
        # logger.debug(f'{x=:.3f} {y=:.3f} {z=:.3f}')
        # alpha = -(x/y)
        # beta = (x*x + y*y)/ (y *z)
        if math.isclose(x, 0, abs_tol=0.01) and math.isclose(y, 0, abs_tol=0.01):
            alpha = 0
        else:
            alpha = -atan2(x, y)  # radians needed to null out x
        beta = atan2(y, z)  # radians needed to null out y
    
        # Convert back to control units: alpha = roll / 256 / 8
        if fast:
            roll = int(max(-31, min(31, -alpha * 256 * 8)))
            pitch = int(max(-8, min(8, beta * 256 * 8)))
        else:
            roll = -alpha
            pitch = beta
            
        # logger.debug(f'{roll=:.3f} {pitch=:.3f}')
        return roll, pitch
    
    # ######################################
           
    def fly_to_vector(self, ship, vec, max_velocity=22, pgain=30, smoothing=0.2):
        # navigate to a location
        
        # invert z to get correct direction
        space = self.gs.space
        nvec = unit_vector(vec) * Vector(1, 1, -1)
        dist = vec.magnitude
            
        fwd_dot = vector_dot_product(nvec, ship.rotmat[NOSEV])
        up_dot = vector_dot_product(nvec, ship.rotmat[ROOFV])
        side_dot = vector_dot_product(nvec, ship.rotmat[SIDEV])
        
        target_climb = (up_dot) * pgain  # max(min(up_dot * P_GAIN, MAX_ROT), -MAX_ROT)
        target_roll = (side_dot) * pgain * 2  # max(min(-side_dot * P_GAIN, MAX_ROT), -MAX_ROT)

        self.angle = math.degrees(math.acos(round(fwd_dot, 3)))
        cr = '\n'
        self.gs.msg_right.text = (f'Autopilot{cr}{self.flight_phase}{cr}F:{fwd_dot:+.2f} P:{up_dot:+.2f} R:{side_dot:+.2f}'
                                  f'{cr}D:{self.distance_to_target:.0f} A:{self.angle:.1f} V:{self.gs.flight_speed:.1f}')
        # SMOOTHING:
        # Simple linear interpolation (LERP) toward the target
        ship.smooth_climb += (target_climb - ship.smooth_climb) * smoothing
        ship.smooth_roll += (target_roll - ship.smooth_roll) * smoothing

        # Apply the smoothed values
        space.flight_climb = ship.smooth_climb
        space.flight_roll = ship.smooth_roll
           
        # self.gs.msg.text = f'AP control inputs {space.flight_climb:+.3f}, {space.flight_roll:+.3f}'
         
        # --- Velocity profile ---
        # Distance at which we should be down to minimum speed
        STOP_DIST = 100
        # Distance at which we start braking (half-way heuristic,
        # but clamped so we don't start braking before we've even accelerated)
        BRAKE_DIST = 10000  # hmax(dist * 0.5, STOP_DIST * 2)
        MIN_SPEED = 1
    
        if dist <= STOP_DIST:
            # Close enough — crawl in
            target_v = MIN_SPEED
        elif dist <= BRAKE_DIST:
            # Linear ramp down from max_velocity to MIN_SPEED
            t = (dist - STOP_DIST) / (BRAKE_DIST - STOP_DIST)   # 1.0 → 0.0
            target_v = MIN_SPEED + t * (max_velocity - MIN_SPEED)
        else:
            target_v = max_velocity * (1 + 4 * self.escape)
    
        # Only accelerate when reasonably aligned (avoid full thrust while turning)
        if fwd_dot >= _cos(25):
            ship.velocity = target_v * (1 + 4 * self.escape)
        else:
            ship.velocity = MIN_SPEED
            
    def fly_to_vector__(self, ship, vec):
        """
        Used for ai ship only
        Calculates the necessary rotation and acceleration for a ship
        to point toward and move to a specific vector.
        """
        rat = 3
        rat2 = _cos(80)
        # cnt2 = _cos(36)

        # Get normalized vector to target
        nvec = unit_vector(vec)
                
        # Tells us if the target is in front of or behind us
        direction = vector_dot_product(nvec, ship.rotmat[NOSEV])
        
        if direction < _cos(131):
            rat2 = 0

        dir_up = vector_dot_product(nvec, ship.rotmat[ROOFV])

        # If target is far behind, perform a hard turn
        if direction < _cos(149):
            ship.rotx = -7 * dir_up  # make roll proportional
            ship.rotz = 0
            # self.gs.msg2.text = f'Accn:{ship.acceleration} Rotx:{ship.rotx:.3f} Rotz:{ship.rotz:.3f}'
            return

        ship.rotx = 0
        # Pitch control
        if (abs(dir_up) * 2) >= rat2:
            ship.rotx = -rat * dir_up  # proportional control
            
        # Roll control
        if abs(ship.rotz) < 16:
            # dot product with ship side vector (rotmat[SIDEV])
            dir_side = vector_dot_product(nvec, ship.rotmat[SIDEV])
            ship.rotz = 0

            if (abs(dir_side) * 2) >= rat2:
                ship.rotz = -rat * dir_side  # < 0 else -rat
                if ship.rotx < 0:
                    ship.rotz = -ship.rotz

        # Acceleration control
        # if direction <= -0.167:
        #    ship.acceleration = -1
        # elif direction >= cnt2:
        #    ship.acceleration = 3
        # self.gs.msg2.text = f'Accn:{ship.acceleration} Rotx:{ship.rotx:.3f} Rotz:{ship.rotz:.3f}'

    def fly_to_planet(self, ship):
        """Points the ship toward the planet (Universe object 0)."""
        H = 25000
        planet = self.universe[0]
        
        # fly to North Pole
        north_pole = planet.location + planet.rotmat[ROOFV] * H
        vec = north_pole - ship.location
        # self.target = north_pole
        self.fly_to_vector__(ship, vec)

    def fly_to_initial_point(self, ship):
        """
        Points the ship toward a spot 768 (8*96)units in front
        of the station's docking bay.
        """
        station = self.universe[1]
        vec = station.location - ship.location
        # Offset target point using the station's forward orientation (rotmat[NOSEV])
        vec = vec + station.rotmat[NOSEV] * 768
        # self.target = station.location + station.rotmat[NOSEV] * 768
        self.fly_to_vector__(ship, vec)

    def fly_to_station(self, ship):
        """Points the ship directly toward the space station."""
        station = self.universe[1]
        vec = station.location - ship.location
        # self.control_accn(ship, station)
        # self.target = station.location
        self.fly_to_vector__(ship, vec)

    def fly_to_docking_bay(self, ship):
        """Final docking stage: Fly straight into the slot."""
        station = self.universe[1]
        diff = ship.location - station.location
        vec = unit_vector(diff)
        # self.target = station.location
        ship.rotx = 0
        
        # Logic for NPC ships or player during final approach
        if ship.is_player or ship.type < 0:
            ship.rotz = 1
            if (vec.x >= 0 and vec.y >= 0) or (vec.x < 0 and vec.y < 0):
                ship.rotz = -ship.rotz

            if abs(vec.x) >= 0.0625:
                ship.acceleration = 0
                ship.velocity = 1
                return

            if abs(vec.y) > 0.002436:
                ship.rotx = -1 if vec.y < 0 else 1

            if abs(vec.y) >= 0.0625:
                ship.acceleration = 0
                ship.velocity = 1
                return

        ship.rotz = 0
        # Check alignment with the bay's slot
        dir_align = vector_dot_product(ship.rotmat[SIDEV], station.rotmat[ROOFV])

        if abs(dir_align) >= 0.9166:
            ship.acceleration += 1
            ship.rotz = 127  # Rapid roll to match station rotation
            return

        ship.acceleration = 0
        ship.rotz = 0
        
    def auto_pilot_ship(self, ship):
        """The main decision engine for an automated ship.
        """
        # If no station exists or forced to fly to planet
        if (ship.flags & cs.FLG_FLY_TO_PLANET) or self.universe[1].type not in (cs.SHIP_CORIOLIS, cs.SHIP_DODEC):
            # logger.debug('ai flying')
            self.fly_to_planet(ship)
            return
        # station is now present
        station = self.universe[1]
        diff = ship.location - station.location
        dist_ = diff.magnitude

        # If very close, the ship has officially 'docked'
        if dist_ < 160:
            ship.flags |= cs.FLG_REMOVE
            # self.gs.msg2.text = 'Docked'
            return
        
        vec = unit_vector(diff)
        # dir_to_bay: check if we are positioned in front of the bay slot
        dir_to_bay = vector_dot_product(station.rotmat[NOSEV], vec)
        
        if dir_to_bay < _cos(13):
            self.fly_to_initial_point(ship)
            return

        # Check if ship is facing the station
        dir_facing = vector_dot_product(ship.rotmat[NOSEV], vec)

        if dir_facing < _cos(160):
            self.fly_to_docking_bay(ship)
            return
        
        self.fly_to_station(ship)
                
    def engage_auto_pilot(self):
        """Activates the docking computer and plays Blue Danube."""
        # Condition checks: not already on, not in witchspace, etc.
        self.auto_pilot_active = True
        # self.flight_phase = None
        # play_midi("BLUE_DANUBE")

    def disengage_auto_pilot(self):
        """Deactivates docking computer and stops music."""
        self.auto_pilot_active = False
        self.flight_phase = None
        cr = '\n'
        self.gs.msg_right.text = f'Autopilot{cr}Off'
        ship = self.gs.space.ship
        ship.smooth_climb = 0
        ship.smooth_roll = 0
        # stop_midi()
        
    def world_to_screen(self, loc, focal=256):
        # First apply view transform (copy the logic from switch_to_view)
        
        fl = self.gs.camera.focal_length
        world_v = Vector3(*loc.to_tuple)
        cam_pos = self.gs.parent_scene.renderer._to_camera(world_v, self.gs.camera)
        if cam_pos is None or cam_pos.z >= self.gs.camera.z_far:
            return None, None  # Behind camera
        sx_sy = self.gs.parent_scene.renderer._project(cam_pos, fl, self.gs.camera)
        if sx_sy is None:
           return None, None
        return sx_sy[0], sx_sy[1]
            
    def draw_target(self):
        # clamp cross to FLIGHT_RECT to indicate offscreen
        # indicate by only showing half the cross
        gfx = self.gs.gfx
        dest = unit_vector(self.target_loc)
        colour = cs.RED if dest.z < 0 else cs.CYAN
        # draw director target
        cx = cs.FLIGHT_RECT.center().x
        cy = cs.FLIGHT_RECT.center().y
        fw = cs.FLIGHT_RECT.w
        fh = cs.FLIGHT_RECT.h
        
        sx, sy = self.world_to_screen(self.target_loc)
        if sx is None:
            tx = cx + int(dest.x * fw / 2)
            ty = cy - int(dest.y * fh / 2)   # screen Y is inverted
        else:
            tx, ty = sx, sy
        if cs.FLIGHT_RECT.contains_point(Point(tx, ty)):
            arm = 20
            gap = 8
            gfx.draw_colour_line(tx - arm, ty, tx - gap, ty, colour, width=3)
            gfx.draw_colour_line(tx + gap, ty, tx + arm, ty, colour, width=3)
            gfx.draw_colour_line(tx, ty - arm, tx, ty - gap, colour, width=3)
            gfx.draw_colour_line(tx, ty + gap, tx, ty + arm, colour, width=3)
        else:
            # find tx, ty closest to flight_rect edge and
            # plot only T shape within rect
            # 1. Calculate the vector from the center to the target
            dx = tx - cx
            dy = ty - cy
            arm = 20
            gap = 8
            # 2. Find the intersection with the rect boundary
            # We compare the slopes to see which edge we hit first
            # Using abs() allows us to handle all four quadrants symmetrically
            scale_x = (fw / 2) / abs(dx) if dx != 0 else float('inf')
            scale_y = (fh / 2) / abs(dy) if dy != 0 else float('inf')
            
            # The scale factor is the smaller of the two, bringing us to the boundary
            scale = min(scale_x, scale_y)
            
            tx = cx + int(dx * scale)
            ty = cy + int(dy * scale)
            
            # 3. Draw the T-shape based on the edge
            # Determine orientation based on the original dx, dy vectors
            if abs(dx * (fh / 2)) > abs(dy * (fw / 2)):
                if dx > 0:  # Right
                    gfx.draw_colour_line(tx, ty - arm, tx, ty + arm, colour, width=3)
                    gfx.draw_colour_line(tx, ty, tx - arm, ty, colour, width=3)
                else:      # Left
                    gfx.draw_colour_line(tx, ty - arm, tx, ty + arm, colour, width=3)
                    gfx.draw_colour_line(tx, ty, tx + arm, ty, colour, width=3)
            else:
                if dy > 0:  # Bottom (assuming Y-down, check your coord system)
                    gfx.draw_colour_line(tx - arm, ty, tx + arm, ty, colour, width=3)
                    gfx.draw_colour_line(tx, ty, tx, ty - arm, colour, width=3)
                else:      # Top
                    gfx.draw_colour_line(tx - arm, ty, tx + arm, ty, colour, width=3)
                    gfx.draw_colour_line(tx, ty, tx, ty + arm, colour, width=3)
                return sx, sy, tx, ty
    
    # Target geometry helpers
    
    def _station_exists(self):
        station = self.gs.universe[1]
        return station.type in (cs.SHIP_CORIOLIS, cs.SHIP_DODEC)
        
    def _pole_waypoint(self):
        """Point POLE_ALTITUDE above planet north pole."""
        planet = self.universe[0]
        return planet.location + Vector(0, 1, 0) * POLE_ALTITUDE

    def ip_waypoint(self):
        """Point IP_DIST ahead of station nose."""
        if self._station_exists():
           station = self.universe[1]
           return station.location + station.rotmat[NOSEV] * IP_DIST
        return Vector(0,0,0)

    def _dist_to(self, ship, point):
        return (point - ship.location).magnitude

    def _fwd_dot_to(self, ship, point):
        """How well the ship is pointing at a world-space point."""
        vec = point - ship.location
        return vector_dot_product(unit_vector(vec), ship.rotmat[NOSEV])
        
    def _ray_blocks_sphere(self, origin, unit_dir, sphere_centre, sphere_radius):
        """Returns True if the sphere occludes the ray from origin in direction unit_dir."""
        w = sphere_centre - origin
        tc = vector_dot_product(w, unit_dir)
        if tc < 0:
            return False   # sphere is behind us
        perp_sq = w.x**2 + w.y**2 + w.z**2 - tc * tc
        return perp_sq < sphere_radius * sphere_radius

    def _has_line_of_sight(self, ship, target):
        """
        Returns (clear, blocker) where clear is True if nothing blocks
        the path, or False with blocker = 'planet' or 'station'.
        """
        # return True, ''
        origin = ship.location
        vec = target - origin
        # dist = vec.magnitude
        unit_dir = unit_vector(vec)
    
        #
        planet = self.universe[0]
        PLANET_RADIUS = cs.PLANET_RADIUS   # or a hardcoded value e.g. 6000
        if self._ray_blocks_sphere(origin, unit_dir, planet.location, PLANET_RADIUS):
            return False, planet
    
        # Station (treat as a sphere with a generous radius)
        station = self.universe[1]
        if station.type in (cs.SHIP_CORIOLIS, cs.SHIP_DODEC):
            STATION_RADIUS = 160   # roughly the docking exclusion zone
            if self._ray_blocks_sphere(origin, unit_dir, station.location, STATION_RADIUS):
                return False, station
    
        return True, None
    
    # Primitive manoeuvres

    def orient_to_target(self, ship, target, MAX_ROT=4.0, P_GAIN=2, smoothing=0.2, director_only=False, aligned=_cos(5)):
        """
        Rotate toward target with no thrust — used during orientation phase.
        Returns True when aligned within ALIGNED_TIGHT.
        """
        
        space = self.gs.space
        if not director_only:
            ship.velocity = 0
            ship.acceleration = 0
            self.gs.flight_speed = 0
        vec = target - ship.location
        nvec = unit_vector(vec) * Vector(1, 1, -1)
        target_roll, target_climb = self.steer_to_origin(nvec, fast=True)
        
        # up_dot = vector_dot_product(nvec, ship.rotmat[ROOFV])  # target above
        # side_dot = vector_dot_product(nvec, ship.rotmat[SIDEV])  # target left
        fwd_dot = vector_dot_product(nvec, ship.rotmat[NOSEV])  # target in front behind
        # Clamp fwd_dot for acos safety
        self.angle = math.degrees(math.acos(max(-1.0, min(1.0, fwd_dot))))

        # already aligned
        if fwd_dot >= aligned:
           space.flight_climb = space.flight_roll = 0
           return True
        
        if not director_only:
            # Simple linear interpolation (LERP) toward the target
            ship.smooth_climb += (target_climb - ship.smooth_climb) * smoothing
            ship.smooth_roll += (target_roll - ship.smooth_roll) * smoothing
    
            # Apply the smoothed values
            space.flight_climb = ship.smooth_climb
            space.flight_roll = ship.smooth_roll
            # space.flight_climb = target_climb  # space.gs.myship.max_climb / MAX_ROT
            # space.flight_roll = target_roll  # space.gs.myship.max_roll / MAX_ROT
            # logger.debug(f'climb {space.flight_climb:.2f} roll {space.flight_roll:.2f}')
            
            # txt = f'Angle {self.angle:.1f} Aligned:{fwd_dot}'
            # logger.debug(txt)
            return False  # fwd_dot >= ALIGNED_TIGHT

    def fly_to_target(self, ship, target, max_velocity=3, pgain=30):
        """
        Fly toward target with distance-based speed profile.
        Checks line of sight; if blocked routes via waypoint.
        """
        clear, blocker = self._has_line_of_sight(ship, target)
        if False:  # not clear:
            logger.debug('flying around')
            self._fly_around(ship, target, blocker)
            return

        vec = target - ship.location
        self.fly_to_vector(ship, vec, max_velocity, pgain=pgain)
        
    def _fly_around(self, ship, target, blocker):
        """
        Calculates a detour waypoint around a blocking object and commands
        the ship to fly toward that waypoint.
        """
        # 1. Get the vector from the blocker to the ship
        # This gives us a reliable direction to step away from the blocker's center
        blocker_to_ship = ship.location - blocker.location
        
        # Avoid division by zero if the ship is exactly at the blocker's center
        if blocker_to_ship.magnitude == 0:
            # Fallback: pick an arbitrary perpendicular or offset direction
            # Assuming 2D or 3D vectors; adjustments might be needed based on your vector class
            blocker_to_ship = Vector(1, 0, 0)  # replace with your vector initialization if needed
            
        # 2. Normalize the vector to get the direction
        avoidance_direction = unit_vector(blocker_to_ship)
        
        # 3. Calculate a safe distance to clear the obstacle
        # We add a safety buffer (e.g., 10-20% or a fixed amount) so the ship doesn't scrape the edge
        if blocker.type == cs.SHIP_PLANET:
           radius = cs.PLANET_RADIUS
        else:
           radius = cs.STATION_RADIUS
        safety_buffer = 1.2
        detour_distance = radius * safety_buffer
        
        # 4. Determine the waypoint location
        # Place the waypoint outside the blocker's perimeter, biased toward the ship's current side
        waypoint = blocker.location + (avoidance_direction * detour_distance)
        
        self.target_location = waypoint - ship.location

        logger.debug(f"Detour calculated. Heading to waypoint: {self.target_location}")
        self.change_phase(ship, 'TO_DETOUR')
        
    def roll_to_match_station(self, ship):
        """
        Roll the ship to align its SIDEV with station ROOFV.
        Returns True when roll error < 5 degrees.
        """
        station = self.universe[1]
        roll_align = vector_dot_product(ship.rotmat[SIDEV], station.rotmat[ROOFV])
        angle_err = math.acos(max(-1.0, min(1.0, roll_align)))
        
        cross_z = (ship.rotmat[SIDEV].x * station.rotmat[ROOFV].y
                   - ship.rotmat[SIDEV].y * station.rotmat[ROOFV].x)
        
        if cross_z < 0:
            angle_err = -angle_err

        MAX_ROLL = 12
        self.gs.space.flight_roll = max(min(-angle_err * 10, MAX_ROLL), -MAX_ROLL)
        
        # ship.rotz = max(min(angle_err * 5.0, MAX_ROLL), -MAX_ROLL)
        ship.rotx = 0
        ship.acceleration = 0

        return abs(angle_err) < math.radians(5)

    def change_phase(self, ship, new_phase):
        """Transition to a new flight phase, zeroing rates."""
        logger.debug(f'Autopilot phase {self.flight_phase} -> {new_phase}')
        self.gs.info_message(f"Docking Computers On {new_phase}")
        
        self.flight_phase = new_phase
        ship.acceleration = 0
        ship.velocity = 1
        # if new_phase and 'FIND' in new_phase:
        #     self.climb_av.size = self.roll_av.size = 12
        # else:
        #    self.climb_av.size = self.roll_av.size = 24
        
    def closest_visible_target(self, ship):
        # when enabling docking computer, find closest target
        targets = [self._pole_waypoint(), self.ip_waypoint()]
        logger.debug(targets)
        min_distance = 1000000
        min_phase = None
        closest = None
        phases = ['FIND_POLE', 'FIND_IP']
        if not self._station_exists():
            return self._pole_waypoint(), 'FIND_POLE'
          
        for target, phase in zip(targets, phases):
            distance = self._dist_to(ship, target)
            clear, blocker = self._has_line_of_sight(ship, target)
            clear = True  # TODO FIX THIS
            if not clear:
                logger.debug(f'Phase {phase}, has blocker {blocker.name}')
            if clear and distance < min_distance:
               min_distance = distance
               closest = target
               min_phase = phase
        logger.debug(f'closest is  {phase} {min_distance}')
        if closest is None:
            return self._pole_waypoint(), 'FIND_POLE'
        return closest, min_phase
       
    # Main state machine

    def auto_pilot_ship_(self, ship, director_only=False):
        """
        Docking state machine.

        TO_PLANET  : fly to north pole waypoint (clears planet bulk)
        AT_POLE    : arrived; orient toward IP before committing
        TO_IP      : fly to IP ahead of station nose
        TO_STATION : on slot axis, nose pointing away — close in
        TO_DOCK    : final roll + crawl into slot
       
        1. if a long distance, orient at slow speed then accelerate
           to planet north pole at altitude 25k
        2. arrive at north pole at low speed
        3. orient to initial point (IP) at slow speed the accelerate to IP
        4. arrive at low speed.
        5. orient to dock at low speed the accelerate at medium slow speed
        6. roll into dock
        7. if on far side of station, fly to initial point 2, outside of
           station. arrive at slow speed.
           jump to item 3
        8. if close to station and not orientated correctly, jump to item 3.
        9. if other side of planet, go to 1.
        
        in all cases, orientation is at slow or zero speed. arrival at target
        point is at slow or zero speed.
        
        For flight director, use same section logic by dont implement the fly_to
        
        state_machine to control flight phase
        """
        # log initial positions
        
        self.distance_to_target = self._dist_to(ship, self.target_loc)
        if self.gs.current_screen == cs.SCR_FRONT_VIEW:
            self.draw_target()
        
        match self.flight_phase:
            case None:
                # Just enabled, get closest
                self.target_loc, phase = self.closest_visible_target(ship)
                self.change_phase(ship, phase)
                
            case 'FIND_TARGET':
                # orient to arbitrary target, usually a ship
                distance = self._dist_to(ship, self.target.location)
                self.gs.msg_left.text = f'Target \n {self.target.name} {distance/1000:.1f}km {self.target.energy}'.upper()
                if not director_only:
                    self.fly_to_target(ship, self.target.location, max_velocity=8, pgain=80)
                if self.target.type == 0:
                   self.gs.msg_left.text = 'Target Lost'
                   self.disengage_auto_pilot()
                   self.change_phase(ship, None)
                    
            case 'FIND_POLE':
                self.target_loc = self._pole_waypoint()
                aligned = self.orient_to_target(ship, self.target_loc, director_only=director_only)
                if aligned:
                    logger.debug('finished align')
                    self.change_phase(ship, 'TO_PLANET_POLE')
                    
            case 'TO_PLANET_POLE':
                # PHASE:  fly to north pole waypoint
                self.target_loc = self._pole_waypoint()
                
                # divert if station visible
                if self._station_exists():
                    station = self.universe[1]
                    clear, blocker = self._has_line_of_sight(ship, self.ip_waypoint())
                    if True:
                        self.change_phase(ship, 'FIND_IP')
                        return
                                
                elif self.distance_to_target < CLOSE_TO_POLE:
                    self.change_phase(ship, 'FIND_IP')
                    return
                      
                if not director_only:
                    self.fly_to_target(ship, self.target_loc, max_velocity=50)
            
            case 'AT_POLE' | 'FIND_IP':
                # PHASE: at pole, or elsewhere,  orient to IP before flying there
                self.target_loc = self.ip_waypoint()
                clear, blocker = self._has_line_of_sight(ship, self.target_loc)
                if False:  # not clear:
                    logger.debug(f'Phase {phase}, has blocker {blocker.name}')
                    self.gs.msg_left.text = f'Phase {phase}, has blocker {blocker.name}'
                    self._fly_around(ship, self.target_loc, blocker)
                    return
                                
                aligned = self.orient_to_target(ship, self.target_loc, director_only=director_only)
                if aligned:
                    self.change_phase(ship, 'TO_IP')
            
            case 'TO_IP':
                # PHASE: fly to IP (ahead of station nose)
                self.target_loc = self.ip_waypoint()
                # self.climb_av.size = self.roll_av.size = 4
                station = self.universe[1]
    
                # Check we are on the correct side of the station
                diff = ship.location - station.location
                dir_to_bay = vector_dot_product(station.rotmat[NOSEV],
                                                unit_vector(diff))
    
                if self.distance_to_target < CLOSE_TO_IP:
                    self.change_phase(ship, 'FIND_STATION')
                if not director_only:
                    self.fly_to_target(ship, self.target_loc, max_velocity=20)
                    
            case 'TO_DETOUR':
                # the rare case when target is blocked
                # divert  to ip possible
                if self._station_exists():
                    station = self.universe[1]
                    clear, blocker = self._has_line_of_sight(ship, self.ip_waypoint())
                    if clear:
                        self.change_phase(ship, 'TO_IP')
                        return
                if not director_only:
                    vec = self.target_loc - ship.location
                    self.fly_to_vector(ship, vec, max_velocity=20)
                    # self.fly_to_target(ship, self.target_loc, max_velocity=20)
                    
            case 'FIND_STATION':
                # # At the IP orient to station
                self.target_loc = self.universe[1].location
                aligned = self.orient_to_target(ship, self.target_loc, director_only=director_only)
                if aligned:
                    self.change_phase(ship, 'TO_STATION')
                        
            case 'TO_STATION':
                # PHASE: on axis, fly toward station face
                self.target_loc = self.universe[1].location
                
                # Verify still on axis; if not, go back to IP
                diff = ship.location - self.target_loc
                dir_to_bay = vector_dot_product(self.universe[1].rotmat[NOSEV],
                                                unit_vector(diff))
                if dir_to_bay < ON_SLOT_AXIS:
                    self.change_phase(ship, 'FIND_IP')
                    return
    
                if self.distance_to_target < CLOSE_TO_STATION:
                    self.change_phase(ship, 'TO_DOCK')
                    return
                if not director_only:
                    self.fly_to_target(ship, self.target_loc, max_velocity=2)
            
            case 'TO_DOCK':
                # PHASE: final roll and crawl into slot
                self.target_loc = self.universe[1].location
                self.gs.yaw_coupling = 0
                if self.distance_to_target < DOCKED_DIST:
                    ship.flags |= cs.FLG_REMOVE
                    self.gs.break_mode = 'docking'
                    self.gs.current_screen = cs.SCR_BREAK_PATTERN
                    self.gs.space.dock_player()
                    self.change_phase(ship, None)  # reset for next time
                    self.gs.yaw_coupling = cs.YAW_COUPLING
                    return
                if not director_only:
                   rolled = self.roll_to_match_station(ship)
                   if rolled:
                       # Aligned — crawl forward
                       ship.rotz = 0
                       ship.acceleration = 1
                       ship.velocity = 1
            
    def vector_func(self, target, roll, pitch, speed=0):
        # minimised function from move universe
        # return modified target from roll, pitch and speed
        # convert control inputs to radians
        # max roll is 31, so 0.144 radians 8 degrees
        alpha = roll / 256.0 / 8
        beta = pitch / 256.0 / 8
        x, y, z = unit_vector(target).to_tuple
        x, y = x * cos(alpha) + y * sin(alpha), y * cos(alpha) - x * sin(alpha)
        y, z = y * cos(beta) - z * sin(beta), z * cos(beta) + y * sin(beta)
        z -= speed
        return x, y, z
  

if __name__ == "__main__":
         
    pass
