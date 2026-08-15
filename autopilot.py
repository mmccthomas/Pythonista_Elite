# Modified and reimagined autopilot code
# Autopilot acquires Planet North Pole, then
# Initial Point for station alignment, then
# Station entrance
#
# if docking computer not fitted/ enabled,
# guidance cross will show directions


import math
from math import sin, cos, atan2
from scene import Point
from vector import Vector, unit_vector, vector_dot_product
from wireframe_3d import Vector3
import constants as cs
import logging
logger = logging.getLogger(__name__)


def _cos(deg):
    return math.cos(math.radians(deg))


def sgn(x):
    if x > 0:
        return 1
    elif x < 0:
        return -1
    return 0


PLANET = 0
STATION = 1
SUN = 2
        
NOSEV = 2
ROOFV = 1
SIDEV = 0

# Phase constants
POLE_ALTITUDE = 15000
IP_DIST = 2000    # units ahead of station nose
IP2_DIST = 6000    # outer waypoint, used when approaching from wrong side

# Arrival thresholds
CLOSE_TO_POLE = 200
CLOSE_TO_IP = 200
CLOSE_TO_STATION = 1000
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
        self.escape = False
        self.velocity_override = None  # default, autopilot controls velocity
        
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
        MAX_PITCH = 8
        x, y, z = unit_vector(target).to_tuple
    
        # Invert the rotation formulas for small angles:
        # x' = x*cos(a) + y*sin(a) → to zero x, we want alpha = -atan2(x, y)
        # y' = y*cos(b) - z*sin(b) → to zero y, we want beta  =  atan2(y, z)

        # alpha = -(x/y)
        # beta = (x*x + y*y)/ (y *z)
        if math.isclose(x, 0, abs_tol=0.001) and math.isclose(y, 0, abs_tol=0.001):
            alpha = 0
        else:
            alpha = -atan2(x, y)  # radians needed to null out x
        beta = atan2(y, z)  # radians needed to null out y
    
        # Convert back to control units: alpha = roll / 256 / 8
        if fast:
            roll = int(max(-31, min(31, -alpha * 256 * 8)))
            pitch = int(max(-MAX_PITCH, min(MAX_PITCH, beta * 256 * 8)))
        else:
            roll = -alpha
            pitch = beta
           
        return roll, pitch
    
    # ######################################
           
    def fly_to_vector(self, ship, vec, max_velocity=22, pgain=30, smoothing=0.2):
        # navigate to a location
        
        # invert z to get correct direction
        space = self.gs.space
        nvec = unit_vector(vec)
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
         
        # --- Velocity profile
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
      
        if self.velocity_override is not None:
            ship.velocity = self.velocity_override
        else:
            if fwd_dot >= _cos(25):
                ship.velocity = target_v * (1 + 4 * self.escape)
            else:
                ship.velocity = MIN_SPEED
             
    # ------ AI ship autopilot
    def fly_to_planet(self, ship):
        """Points the ship toward the planet."""
        vec = self.universe[PLANET].location - ship.location
        if vec.magnitude < 25000:
            ship.flags &= ~cs.FLG_FLY_TO_PLANET  # clears bit
            ship.flags |= cs.FLG_FLY_TO_STATION
        else:
            ship.rotmat[NOSEV] = self.universe[STATION].rotmat[NOSEV]

    def fly_to_station(self, ship):
        """Points the ship directly toward the space station."""
        vec = self.universe[STATION].location - ship.location
        if vec.magnitude < 100:
            ship.flags |= cs.FLG_REMOVE
        else:
            ship.rotmat[NOSEV] = self.universe[STATION].rotmat[NOSEV] * -1
        
    def auto_pilot_ship(self, index):
        """Automated ship runs to planet and back to station
        """
        ship = self.universe[index]
        ship.rotx = ship.rotz = 0
        if (ship.flags & cs.FLG_FLY_TO_PLANET):
            self.fly_to_planet(ship)
        else:
            self.fly_to_station(ship)
    
    # --------  Engage/ disengage
    def engage_auto_pilot(self, target=False):
        """Activates the docking computer and plays Blue Danube."""
        # Condition os: not already on, not in witchspace, etc.
        self.auto_pilot_active = True
        name = 'Cancel Target' if target else 'Cancel Docking'
        self.gs.keypad.key_change(key_name='Docking',
                                  name=name, color=cs.ORANGE)
        # self.flight_phase = None
        # play_midi("BLUE_DANUBE")

    def disengage_auto_pilot(self):
        """Deactivates docking computer and stops music."""
        self.auto_pilot_active = False
        self.flight_phase = None
        cr = '\n'
        self.gs.msg_right.text = f'Autopilot{cr}Off'
        self.gs.keypad.key_change(key_name='Cancel Docking',
                                  name='Docking', color='lightgreen')
        self.gs.keypad.key_change(key_name='Cancel Target',
                                  name='Docking', color='lightgreen')
        self.gs.keypad.key_change('Instant Dock', enabled=False)
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
            distance = self.target_loc.magnitude
            if distance < 5000:
                distance_text = f'{distance:.0f}'
            elif distance < 10000:
                distance_text = f'{(distance / 1000):.1f}k'
            else:
                distance_text = f'{(distance // 1000):.0f}k'
            gfx.draw_text(distance_text, tx + arm, ty, font_size=15, alignment=6)
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
    
    def _pole_waypoint(self):
        """Point POLE_ALTITUDE above planet north pole."""
        planet = self.universe[PLANET]
        pole = 1 if self.universe[PLANET].location.y < self.universe[STATION].location.y else -1
        return planet.location + Vector(0, 1, 0) * POLE_ALTITUDE * pole

    def ip_waypoint(self):
        """Point IP_DIST ahead of station nose."""
        station = self.universe[STATION]
        return station.location + station.rotmat[NOSEV] * IP_DIST
        # return Vector(0, 0, 0)

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
    
        PLANET_RADIUS = cs.PLANET_RADIUS   # or a hardcoded value e.g. 6000
        if self._ray_blocks_sphere(origin, unit_dir, self.universe[PLANET].location, PLANET_RADIUS):
            return False, self.universe[PLANET]
    
        # Station (treat as a sphere with a generous radius)
        STATION_RADIUS = 160   # roughly the docking exclusion zone
        if self._ray_blocks_sphere(origin, unit_dir, self.universe[STATION].location, STATION_RADIUS):
            return False, self.universe[STATION]
    
        return True, None
    
    # Primitive manoeuvres

    def orient_to_target(self, ship, target, MAX_ROT=4.0, P_GAIN=2, smoothing=0.2, aligned=_cos(5)):
        """
        Rotate toward target with no thrust — used during orientation phase.
        Returns True when aligned within ALIGNED_TIGHT.
        """
        space = self.gs.space
        
        ship.velocity = 0
        ship.acceleration = 0
        self.gs.flight_speed = 0
        vec = target - ship.location
        nvec = unit_vector(vec)
        # target_roll, target_climb = self.steer_to_origin(nvec, fast=True)
        target_roll, target_climb = 0, 0
        # reuse fly_to_target as its much faster
        self.fly_to_target(ship, target, max_velocity=0, pgain=250)
        fwd_dot = vector_dot_product(nvec, ship.rotmat[NOSEV])  # target in front behind
        # Clamp fwd_dot for acos safety
        self.angle = math.degrees(math.acos(max(-1.0, min(1.0, fwd_dot))))
        cr = '\n'
        self.gs.msg_right.text = (f'Autopilot{cr}{self.flight_phase}{cr}'
                                  f'{cr}D:{self.distance_to_target:.0f} A:{self.angle:+.1f} V:{self.gs.flight_speed:.1f}')
        # already aligned
        if fwd_dot >= aligned:
           space.flight_climb = space.flight_roll = 0
           return True
        
        # Simple linear interpolation (LERP) toward the target
        ship.smooth_climb += (target_climb - ship.smooth_climb) * smoothing
        ship.smooth_roll += (target_roll - ship.smooth_roll) * smoothing

        # Apply the smoothed values
        # space.flight_climb = ship.smooth_climb
        # space.flight_roll = ship.smooth_roll
        
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

    def _fly_around(self, ship, blocker):
        """
        Calculates a detour waypoint perpendicular to the blocker-ship line
        to steer around the obstacle.
        """
        # 1. Vector from blocker to ship
        blocker_to_ship = ship.location - blocker.location
        
        # Avoid division by zero
        if blocker_to_ship.magnitude == 0:
            blocker_to_ship = Vector(1, 0, 0)
            
        # 2. Normalize the direction
        direction = unit_vector(blocker_to_ship)
        
        # 3. Calculate radius with safety buffer
        radius = cs.PLANET_RADIUS if blocker.type == cs.SHIP_PLANET else cs.STATION_RADIUS
        detour_distance = radius * 20
        
        # 4. Calculate a perpendicular vector (the "tangent")
        # For 2D: If direction is (x, y), a perpendicular is (-y, x) or (y, -x)
        # This steers the ship to the side instead of moving directly away
        perp_direction = Vector(0, 1, 0)
        
        # 5. Determine the waypoint
        # We place the waypoint at the edge of the radius, but offset to the side
        waypoint = blocker.location + (direction * radius * 0.5) + (perp_direction * detour_distance)
        
        target = waypoint - ship.location
    
        logger.debug(f"Detour calculated. Steering to the side of {blocker.type}")
        self.change_phase(ship, 'FIND_DETOUR')
        logger.debug(f'{target=}')
        return target
        
    def roll_to_match_station(self, ship):
        """
        Roll the ship to align its SIDEV with station ROOFV.
        Returns True when roll error < 5 degrees.
        """
        station = self.universe[STATION]
        roll_align = vector_dot_product(ship.rotmat[SIDEV], station.rotmat[ROOFV])
        angle_err = math.acos(max(-1.0, min(1.0, roll_align)))
        
        cross_z = (ship.rotmat[SIDEV].x * station.rotmat[ROOFV].y
                   - ship.rotmat[SIDEV].y * station.rotmat[ROOFV].x)
        if cross_z < 0:
            angle_err = -angle_err
        
        MAX_ROLL = 31
        self.gs.space.flight_roll = max(min(-angle_err * 10, MAX_ROLL), -MAX_ROLL)
        ship.rotx = 0
        ship.acceleration = 0

        return abs(angle_err) < math.radians(5), math.degrees(angle_err)

    def change_phase(self, ship, new_phase):
        """Transition to a new flight phase, zeroing rates."""
        logger.debug(f'Autopilot phase {self.flight_phase} -> {new_phase}')
        # self.gs.info_message(f"Docking Computers On {new_phase}")
        
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
        min_distance = 1000000
        min_phase = None
        closest = None
        phases = ['FIND_POLE', 'FIND_IP']
        if not self.gs.space.close_to_station():
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
    def auto_pilot_ship_(self, ship):
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
        
        Weakness: line of sight code is flaky. occasionaly need to cancel, move and renable 
        docking
        """
        # log initial positions
        
        self.distance_to_target = self._dist_to(ship, self.target_loc)
        if (self.gs.current_screen == cs.SCR_FRONT_VIEW
                and self.flight_phase != 'FIND_TARGET'):
            self.draw_target()
        
        match self.flight_phase:
            case None:
                # Just enabled, get closest
                self.target_loc, phase = self.closest_visible_target(ship)
                self.change_phase(ship, phase)
                
            case 'FIND_TARGET':
                # orient to arbitrary target, usually a ship
                if self.target.type in [cs.SHIP_CARGO, cs.SHIP_ALLOY]:
                    target_loc = self.target.location + Vector(0, 100, 0)
                else:
                    target_loc = self.target.location
                distance = self._dist_to(ship, target_loc)
                self.gs.msg_left.text = f'Target \n {self.target.name} {distance/1000:.1f}km {self.target.energy}'.upper()
                self.fly_to_target(ship, target_loc, max_velocity=22, pgain=250)
                if self.target.type == 0:
                   self.gs.msg_left.text = 'Target Lost'
                   self.disengage_auto_pilot()
                   self.change_phase(ship, None)
                    
            case 'FIND_POLE':
                self.target_loc = self._pole_waypoint()
                aligned = self.orient_to_target(ship, self.target_loc)
                if aligned:
                    logger.debug('finished align')
                    self.change_phase(ship, 'TO_PLANET_POLE')
                    
            case 'TO_PLANET_POLE':
                # PHASE:  fly to north pole waypoint
                self.target_loc = self._pole_waypoint()
                
                # divert if station visible
                if self.gs.space.close_to_station():
                    clear, blocker = self._has_line_of_sight(ship, self.ip_waypoint())
                    if True:
                        self.change_phase(ship, 'FIND_IP')
                        return
                                
                elif self.distance_to_target < CLOSE_TO_POLE:
                    self.change_phase(ship, 'FIND_IP')
                    return
                      
                self.fly_to_target(ship, self.target_loc, max_velocity=self.gs.myship.max_speed)
            
            case 'AT_POLE' | 'FIND_IP':
                # PHASE: at pole, or elsewhere,  orient to IP before flying there
                self.target_loc = self.ip_waypoint()
                clear, self.blocker = self._has_line_of_sight(ship, self.target_loc)
                
                clear = True
                if not clear:
                    self.gs.msg_left.text = f'IP has blocker {self.blocker.name}'
                    self.target_loc = self._fly_around(ship, self.blocker)
                                
                aligned = self.orient_to_target(ship, self.target_loc)
                
                if aligned:
                    self.change_phase(ship, 'TO_IP')
                    
            case 'FIND_DETOUR':
                # PHASE: orient to DETOUR before flying there
                self.target_loc = self._fly_around(ship, self.blocker)
                aligned = self.orient_to_target(ship, self.target_loc)
                if aligned:
                    self.change_phase(ship, 'TO_DETOUR')
                    
            case 'TO_IP':
                # PHASE: fly to IP (ahead of station nose)
                # dont deviate until within distance
                self.target_loc = self.ip_waypoint()
                if self.gs.instant_dock:
                    self.gs.keypad.key_change('Instant Dock', enabled=True)
                    logger.debug('instant dock enabled')
                if self.distance_to_target < CLOSE_TO_IP:
                    self.change_phase(ship, 'FIND_STATION')
                
                self.fly_to_target(ship, self.target_loc, max_velocity=self.gs.myship.max_speed)
                    
            case 'TO_DETOUR':
                # the rare case when target is blocked
                # divert  to ip possible
                if self.gs.close_to_station():
                    clear, blocker = self._has_line_of_sight(ship, self.ip_waypoint())
                    clear = True
                    if clear:
                        self.change_phase(ship, 'FIND_IP')
                        return
                
                vec = self.target_loc - ship.location
                self.fly_to_vector(ship, vec, max_velocity=20)
                # self.fly_to_target(ship, self.target_loc, max_velocity=20)
                    
            case 'FIND_STATION':
                # At the IP orient to station
                self.target_loc = self.universe[STATION].location
                aligned = self.orient_to_target(ship, self.target_loc)
                if aligned:
                    self.change_phase(ship, 'TO_STATION')
                        
            case 'TO_STATION':
                # PHASE: on axis, fly toward station face
                self.target_loc = self.universe[STATION].location
                
                # Verify still on axis; if not, go back to IP
                diff = ship.location - self.target_loc
                dir_to_bay = vector_dot_product(self.universe[STATION].rotmat[NOSEV],
                                                unit_vector(diff))
                if dir_to_bay < ON_SLOT_AXIS:
                    self.change_phase(ship, 'FIND_IP')
                    logger.debug('not on axis')
                    return
    
                if self.distance_to_target < CLOSE_TO_STATION:
                    self.change_phase(ship, 'TO_DOCK')
                    return
                
                self.fly_to_target(ship, self.target_loc, max_velocity=2)
            
            case 'TO_DOCK':
                # PHASE: final roll and crawl into slot
                self.target_loc = self.universe[STATION].location
      
                if self.distance_to_target < DOCKED_DIST:
                    ship.flags |= cs.FLG_REMOVE
                    self.change_phase(ship, None)  # reset for next time
                    self.gs.break_mode = 'docking'
                    self.gs.current_screen = cs.SCR_BREAK_PATTERN
                    return
                
                rolled, error = self.roll_to_match_station(ship)
                if rolled:
                    # Aligned — crawl forward
                    ship.rotz = 0
                    ship.acceleration = 1
                    ship.velocity = 2
                              
                self.gs.msg_right.text = (f'Autopilot{cs.CR}{self.flight_phase}{cs.CR}'
                                          f'{cs.CR}D:{self.distance_to_target:.0f} V:{self.gs.flight_speed:.1f}')
                       
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
