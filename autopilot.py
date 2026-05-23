
import math
from math import sin, cos, atan2
from vector import Vector, unit_vector, vector_dot_product
from wireframe_3d import Vector3
import constants as cs
from constants import logger
import copy


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

class Averager:
    def __init__(self, size=5):
        self.size = size
        self.buffer = []

    def next(self, value):
        self.buffer.append(value)
        if len(self.buffer) > self.size:
            self.buffer.pop(0)
        return sum(self.buffer) / len(self.buffer)

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
        self.climb_av = Averager(12)
        self.roll_av = Averager(12)
        self.integral_roll = 0
        self.prev_error_roll = 0
        self.integral_climb = 0
        self.prev_error_climb = 0
        self.escape = False
   
    # Experimental functions    
            
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
            alpha = -atan2(x, y)          # radians needed to null out x        
        beta  =  atan2(y, z)          # radians needed to null out y
    
        # Convert back to control units: alpha = roll / 256 / 8
        if fast:
            roll  = int(max(-31, min(31, -alpha * 256 * 8)))
            pitch = int(max(-8, min(8, beta  * 256 * 8)))
        else:
            roll = -alpha
            pitch = beta                        
            
        # logger.debug(f'{roll=:.3f} {pitch=:.3f}')   
        return roll, pitch          
    
    # ######################################
       
    def fly_to_vector(self, ship, vec, max_velocity=22, pgain=30):                   
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
        self.gs.msg2.text = f'F:{fwd_dot:+.2f} P:{up_dot:+.2f} R:{side_dot:+.2f} D:{self.distance_to_target:.0f} A:{self.angle:.1f} V:{self.gs.flight_speed:.1f}'
        
        space.flight_climb = target_climb
        space.flight_roll = target_roll
        self.gs.msg.text = f'AP control inputs {space.flight_climb:+.3f}, {space.flight_roll:+.3f}'       
         
        # --- Velocity profile ---
        # Distance at which we should be down to minimum speed
        STOP_DIST = 100
        # Distance at which we start braking (half-way heuristic,
        # but clamped so we don't start braking before we've even accelerated)
        BRAKE_DIST = 10000 #hmax(dist * 0.5, STOP_DIST * 2)
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
        # TODO these are very bang bang , would like to smooth
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
        # self.gs.msg.text = 'Fly to planet'
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
        # self.gs.msg.text = f'Autopilot Fly to initial point {vec.magnitude:.1f}'
        # Offset target point using the station's forward orientation (rotmat[NOSEV])
        vec = vec + station.rotmat[NOSEV] * 768
        # self.target = station.location + station.rotmat[NOSEV] * 768
        self.fly_to_vector__(ship, vec)

    def fly_to_station(self, ship):
        """Points the ship directly toward the space station."""
        station = self.universe[1]
        vec = station.location - ship.location
        # self.gs.msg.text = f'Fly to station {vec.magnitude:.1f}'
        # self.control_accn(ship, station)
        # self.target = station.location
        self.fly_to_vector__(ship, vec)

    def fly_to_docking_bay(self, ship):
        """Final docking stage: Fly straight into the slot."""
        station = self.universe[1]
        diff = ship.location - station.location
        vec = unit_vector(diff)
        # self.gs.msg.text = f'Fly to docking bay {vec.magnitude:.1f}'
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
            # self.gs.msg2.text = 'To planet'
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
            self.gs.msg.text = f'To IP {dir_to_bay:.3f}'
            self.fly_to_initial_point(ship)
            return

        # Check if ship is facing the station
        dir_facing = vector_dot_product(ship.rotmat[NOSEV], vec)

        if dir_facing < _cos(160):
            self.gs.msg.text = f'To Docking {dir_facing:.2f}'
            self.fly_to_docking_bay(ship)
            return
            
        self.gs.msg.text = f'To Station {dir_facing:.2f}'
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

        arm = 20                        
        gap = 8
        gfx.draw_colour_line(tx - arm, ty, tx - gap, ty, colour, width=3)
        gfx.draw_colour_line(tx + gap, ty, tx + arm, ty, colour, width=3)
        gfx.draw_colour_line(tx, ty - arm, tx, ty - gap, colour, width=3)
        gfx.draw_colour_line(tx, ty + gap, tx, ty + arm, colour, width=3)
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
        station = self.universe[1]
        return station.location + station.rotmat[NOSEV] * IP_DIST

    def _ip2_waypoint(self):
        """Outer waypoint on the station nose axis, further out."""
        station = self.universe[1]
        return station.location + station.rotmat[NOSEV] * IP2_DIST

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
        return True, ''
        origin = ship.location
        vec = target - origin
        # dist = vec.magnitude
        unit_dir = unit_vector(vec)
    
        #
        planet = self.universe[0]
        PLANET_RADIUS = cs.PLANET_RADIUS   # or a hardcoded value e.g. 6000
        if self._ray_blocks_sphere(origin, unit_dir, planet.location, PLANET_RADIUS):
            return False, 'planet'
    
        # Station (treat as a sphere with a generous radius)
        station = self.universe[1]
        if station.type in (cs.SHIP_CORIOLIS, cs.SHIP_DODEC):
            STATION_RADIUS = 160   # roughly the docking exclusion zone
            if self._ray_blocks_sphere(origin, unit_dir, station.location, STATION_RADIUS):
                return False, 'station'
    
        return True, None
    
    # Primitive manoeuvres

    def orient_to_target(self, ship, target, MAX_ROT=4.0, P_GAIN=2, director_only=False, aligned=_cos(5)):
        """
        Rotate toward target with no thrust — used during orientation phase.
        Returns True when aligned within ALIGNED_TIGHT.
        """
        
        space = self.gs.space
        ship.velocity = 0
        ship.acceleration = 0
        self.gs.flight_speed = 0
        vec = target - ship.location
        nvec = unit_vector(vec) * Vector(1, 1, -1)
        target_roll, target_climb  = self.steer_to_origin(nvec, fast=True)
        
        up_dot = vector_dot_product(nvec, ship.rotmat[ROOFV])  # target above
        side_dot = vector_dot_product(nvec, ship.rotmat[SIDEV])  # target left
        fwd_dot = vector_dot_product(nvec, ship.rotmat[NOSEV])# target in front behind
        # Clamp fwd_dot for acos safety
        self.angle = math.degrees(math.acos(max(-1.0, min(1.0, fwd_dot))))

        #already aligned
        if fwd_dot >= aligned:           
           space.flight_climb = space.flight_roll = 0
           return True                
        
        av_climb = self.climb_av.next(target_climb)
        av_roll = self.roll_av.next(target_roll)
        if not director_only:
            space.flight_climb = av_climb #* space.gs.myship.max_climb / MAX_ROT
            space.flight_roll = av_roll #* space.gs.myship.max_roll / MAX_ROT
            # logger.debug(f'climb {space.flight_climb:.2f} roll {space.flight_roll:.2f}')
        
        #txt = f'Angle {self.angle:.1f} Aligned:{fwd_dot}'
        # self.gs.msg.text = txt
        #logger.debug(txt)
        return False # fwd_dot >= ALIGNED_TIGHT

    def fly_to_target(self, ship, target, max_velocity=3, pgain=30):
        """
        Fly toward target with distance-based speed profile.
        Checks line of sight; if blocked routes via waypoint.
        """
        clear, blocker = self._has_line_of_sight(ship, target)
        if not clear:
            logger.debug('flying around')
            self._fly_around(ship, target, blocker, max_velocity)
            return

        vec = target - ship.location        
        self.fly_to_vector(ship, vec, max_velocity, pgain=pgain)
        
    def _fly_around(self, ship, target, blocker, max_velocity=3):
        """
        Calculates a detour waypoint around a blocking object and commands
        the ship to fly toward that waypoint.
        """
        # 1. Get the vector from the blocker to the ship
        # This gives us a reliable direction to step away from the blocker's center
        blocker_to_ship = ship.location - blocker.location
        
        # Avoid division by zero if the ship is exactly at the blocker's center
        if blocker_to_ship.magnitude() == 0:
            # Fallback: pick an arbitrary perpendicular or offset direction
            # Assuming 2D or 3D vectors; adjustments might be needed based on your vector class
            blocker_to_ship = Vector(1, 0, 0) # replace with your vector initialization if needed
            
        # 2. Normalize the vector to get the direction
        avoidance_direction = blocker_to_ship.normalize()
        
        # 3. Calculate a safe distance to clear the obstacle
        # We add a safety buffer (e.g., 10-20% or a fixed amount) so the ship doesn't scrape the edge
        safety_buffer = 1.2 
        detour_distance = blocker.radius * safety_buffer
        
        # 4. Determine the waypoint location
        # Place the waypoint outside the blocker's perimeter, biased toward the ship's current side
        waypoint = blocker.location + (avoidance_direction * detour_distance)
        
        # 5. Calculate the vector from the ship to the new waypoint
        waypoint_vector = waypoint - ship.location
        
        # 6. Delegate the movement to your existing vector flight function
        logger.debug(f"Detour calculated. Heading to waypoint: {waypoint}")
        self.fly_to_vector(ship, waypoint_vector, max_velocity)
        
    def roll_to_match_station(self, ship):
        """
        Roll the ship to align its SIDEV with station ROOFV.
        Returns True when roll error < 5 degrees.
        """
        station = self.universe[1]
        roll_align = vector_dot_product(ship.rotmat[SIDEV], station.rotmat[ROOFV])
        angle_err = math.acos(max(-1.0, min(1.0, roll_align)))
        # logger.debug(angle_err)
        cross_z = (ship.rotmat[SIDEV].x * station.rotmat[ROOFV].y
                   - ship.rotmat[SIDEV].y * station.rotmat[ROOFV].x)
        # logger.debug(cross_z)          
        if cross_z < 0:
            angle_err = -angle_err

        MAX_ROLL = 12
        self.gs.space.flight_roll = max(min(angle_err * 5.0, MAX_ROLL), -MAX_ROLL)
        # logger.debug(self.gs.space.flight_roll)       
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
        if new_phase and 'FIND' in new_phase:
             self.climb_av.size = self.roll_av.size = 12 
        else: 
             self.climb_av.size = self.roll_av.size = 24
        
    def closest_visible_target(self, ship):
        # when enabling docking computer, find closest target
        targets = [self._pole_waypoint(),
                   self._pole_waypoint(),
                   self.ip_waypoint(),
                   # self._ip2_waypoint(),
                   self.gs.universe[1].location]
        logger.debug(targets)
        min_distance = 1000000           
        min_phase = None
        phases = ['FIND_POLE',
                  'TO_POLE', 
                  'FIND_IP', 
                  # 'TO_IP2', 
                  'TO_STATION'] 
        if not self._station_exists():
            return targets[0], phases[0]
           
        for target, phase in zip(targets, phases):                   
            distance = self._dist_to(ship, target)               
            clear, blocker = self._has_line_of_sight(ship, target)
            if not clear:
                 logger.debug(f'Phase {phase}, has blocker {blocker}')
            if clear and distance < min_distance:
               min_distance = distance
               closest = target
               min_phase = phase
        logger.debug(f'closest is  {phase} {min_distance}')
        return closest, min_phase
       
    # Main state machine

    def auto_pilot_ship_(self, ship, director_only=False):
        """
        Docking state machine.

        TO_PLANET  : fly to north pole waypoint (clears planet bulk)
        AT_POLE    : arrived; orient toward IP before committing
        TO_IP      : fly to IP ahead of station nose
        TO_IP2     : on wrong side — fly to outer waypoint first
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
                # orient to arbitrary target                
                aligned = self.orient_to_target(ship, self.target.location, director_only=director_only, aligned=_cos(1))                
                if aligned:                   
                    self.change_phase(ship, 'END')   
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
                    clear, blocker = self._has_line_of_sight(ship, station.location)
                    if clear:
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
                if not clear:  
                    logger.debug(f'Phase {phase}, has blocker {blocker}')                  
                    self._fly_around(ship, self.target_loc, blocker, max_velocity=4)
                    return
                                
                aligned = self.orient_to_target(ship, self.target_loc, director_only=director_only)
                if aligned:
                    self.change_phase(ship, 'TO_IP')
            
            case 'TO_IP':
                # PHASE: fly to IP (ahead of station nose)
                self.target_loc = self.ip_waypoint()
                self.climb_av.size = self.roll_av.size = 4
                station = self.universe[1]
    
                # Check we are on the correct side of the station
                diff = ship.location - station.location
                dir_to_bay = vector_dot_product(station.rotmat[NOSEV],
                                                unit_vector(diff))                
    
                if self.distance_to_target < CLOSE_TO_IP:
                    self.change_phase(ship, 'FIND_STATION')
                if not director_only:     
                    self.fly_to_target(ship, self.target_loc, max_velocity=20)
                
            case 'FIND_STATION':
                # # At the IP orient to station
                self.target_loc = self.universe[1].location                
                aligned = self.orient_to_target(ship, self.target_loc, director_only=director_only)
                if aligned:              
                    self.change_phase(ship, 'TO_STATION')                                         
                
            case 'TO_IP2':
                # PHASE: wrong side of station, fly to outer waypoint
                self.target_loc = self._ip2_waypoint()                
                if self.distance_to_target < CLOSE_TO_IP:
                    # Now in front of station — head for proper IP
                    self.change_phase(ship, 'TO_IP')
                    return
                if not director_only:      
                    self.fly_to_target(ship, self.target_loc, max_velocity=8)
            
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
    
                if self.distance_to_target < DOCKED_DIST:
                    ship.flags |= cs.FLG_REMOVE
                    self.gs.break_mode = 'docking'
                    self.gs.current_screen = cs.SCR_BREAK_PATTERN
                    self.gs.space.dock_player()
                    self.change_phase(ship, None)  # reset for next time
                    return
                if not director_only:  
                   rolled = self.roll_to_match_station(ship)
                   if rolled:
                       # Aligned — crawl forward
                       ship.rotz = 0
                       ship.acceleration = 1
                       ship.velocity = 1
                    
            case 'END':
               if not director_only:  
                    self.fly_to_target(ship, self.target.location, max_velocity=8, pgain=80)
               if self.target.type == 0:
                   self.gs.info_message('Target Lost')
                   self.disengage_auto_pilot()
                  
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
        

 
 
"""
test_autopilot.py  –  Standalone test harness for autopilot.Pilot.auto_pilot_ship_()

The real game has deep dependencies (universe, space, gfx, scene, ...).
This file stubs every one of them so auto_pilot_ship_() can run in a
tight Python loop with no Pythonista / scene imports required.

Kinematics
----------
The ship's orientation is stored as a 3×3 rotation matrix (rotmat).
Each frame the autopilot writes flight_roll and flight_climb to the
space stub; simulate() applies those using autopilot.vector_func(),
which is exactly how the real game moves the universe.

    new_nosev  = vector_func(nosev,  roll, climb, speed=velocity)
    new_roofv  = vector_func(roofv,  roll, climb, speed=0)
    new_sidev  = vector_func(sidev,  roll, climb, speed=0)

The ship's world position advances along its nose vector each tick.

Usage
-----
Run directly:
    python test_autopilot.py

Or call run_scenario() from a REPL / another test file:
    from test_autopilot import run_scenario, Scenario
    result = run_scenario(Scenario(...))
"""


from dataclasses import dataclass, field





def identity_rotmat():
    """Returns [sidev, roofv, nosev] = [x̂, ŷ, ẑ]."""
    return [Vector(1, 0, 0), Vector(0, 1, 0), Vector(0, 0, 1)]


def rotmat_from_direction(fwd: Vector):
    """
    Build a right-handed rotation matrix with nosev = normalised fwd.
    roofv is chosen to be as close to world-up (0,1,0) as possible.
    """
    nosev = unit_vector(fwd)
    world_up = Vector(0, 1, 0)
    # If fwd is nearly vertical, fall back to world-forward as up-hint
    if abs(vector_dot_product(nosev, world_up)) > 0.99:
        world_up = Vector(0, 0, 1)
    # sidev = nosev × up (cross product)
    sidev = _cross(nosev, world_up)
    sidev = unit_vector(sidev)
    roofv = _cross(sidev, nosev)
    roofv = unit_vector(roofv)
    return [sidev, roofv, nosev]   # [SIDEV, ROOFV, NOSEV]


def _cross(a, b):
    return Vector(
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x,
    )


def apply_vector_func(rotmat, roll, climb, velocity, pilot_instance):
    """
    Use autopilot.vector_func() to rotate the three orientation vectors
    and advance the ship along its nose.  Returns (new_rotmat, delta_pos).
    """
    new_rotmat = [None, None, None]
    for i in range(3):
        speed = velocity if i == NOSEV else 0.0
        x, y, z = pilot_instance.vector_func(rotmat[i], roll, climb, speed)
        new_rotmat[i] = unit_vector(Vector(x, y, z))

    # Position delta: ship advances along nose by `velocity` units
    nosev = new_rotmat[NOSEV]
    delta = nosev * velocity
    return new_rotmat, delta


# ---------------------------------------------------------------------------
# Stub classes  (minimal API surface actually touched by auto_pilot_ship_)
# ---------------------------------------------------------------------------

class StubMsg:
    """Replaces ui.Label / scene text nodes."""
    def __init__(self, name=""):
        self._name = name
        self.text = ""

    def __setattr__(self, name, value):
        if name == "text" and hasattr(self, "_name"):
            pass   # suppress; set to True below to print live
        super().__setattr__(name, value)


class StubSpace:
    flight_roll = 0.0
    flight_climb = 0.0


class StubCamera:
    focal_length = 256
    z_far = 1e9


class StubParentScene:
    dt = 1 / 60


class StubShip:
    """
    Represents either the player ship or an NPC ship being piloted.
    Mirrors every attribute that auto_pilot_ship_() touches.
    """

    def __init__(self, location: Vector, rotmat=None,
                 ship_type: int = -1, is_player: bool = False):
        self.location = location
        self.rotmat = rotmat if rotmat is not None else identity_rotmat()
        self.type = ship_type
        self.is_player = is_player
        self.velocity = 1.0
        self.acceleration = 0
        self.rotx = 0.0
        self.rotz = 0.0
        self.flags = 0


class StubPlanet:
    def __init__(self, location: Vector):
        self.location = location
        self.type = 1   # some non-station type
        # north pole = straight up
        self.rotmat = [Vector(1, 0, 0), Vector(0, 1, 0), Vector(0, 0, 1)]


class StubStation:
    """
    Coriolis / Dodec station stub.
    nose_dir determines which way the docking slot faces.
    """
    SHIP_CORIOLIS = 7

    def __init__(self, location: Vector, nose_dir: Vector = None):
        self.location = location
        self.type = StubStation.SHIP_CORIOLIS
        if nose_dir is None:
            nose_dir = Vector(0, 0, -1)   # slot faces -Z by default
        self.rotmat = rotmat_from_direction(nose_dir)


class StubGS:
    """
    Fake GameState / gs object.  Wires together every sub-object the
    pilot touches and provides the two universe slots [planet, station].
    """

    def __init__(self, planet: StubPlanet, station: StubStation,
                 ship: StubShip, verbose: bool = False):
        self.universe = [planet, station]
        self.space = StubSpace()
        self.camera = StubCamera()
        self.parent_scene = StubParentScene()
        self.flight_speed = 1.0
        self.current_screen = -1      # not SCR_FRONT_VIEW, so draw_target skipped
        self.break_mode = None
        self._ship = ship
        self._verbose = verbose

        # Text labels
        self.msg = StubMsg("msg")
        self.msg2 = StubMsg("msg2")

    def info_message(self, txt):
        if self._verbose:
            print(f"  [info] {txt}")

    # constants expected by autopilot
    @property
    def current_screen(self):
        return self._current_screen

    @current_screen.setter
    def current_screen(self, v):
        self._current_screen = v


# ---------------------------------------------------------------------------
# Fake module-level constants (what autopilot.py imports from constants)
# ---------------------------------------------------------------------------

class _FakeConstants:
    SHIP_CORIOLIS = 7
    SHIP_DODEC = 8
    FLG_FLY_TO_PLANET = 0x01
    FLG_REMOVE = 0x80
    SCR_FRONT_VIEW = 1
    SCR_BREAK_PATTERN = 99
    PLANET_RADIUS = 6000

    class FLIGHT_RECT:
        @staticmethod
        def center():
            class _P:
                x = 256
                y = 256
            return _P()
        w = 512
        h = 512

    RED = (255, 0, 0)
    CYAN = (0, 255, 255)

    class _Logger:
        def debug(self, *a, **k): pass
        def info(self, *a, **k): pass
        def warning(self, *a, **k): pass

    logger = _Logger()


# Patch sys.modules so "import constants as cs" inside autopilot.py resolves
import types, sys as _sys

_fake_cs = types.ModuleType("constants")
for _k, _v in vars(_FakeConstants).items():
    if not _k.startswith("__"):
        setattr(_fake_cs, _k, _v)
_sys.modules.setdefault("constants", _fake_cs)

# Stub out the real vector / wireframe modules too
_vec_mod = types.ModuleType("vector")
_vec_mod.Vector = Vector
_vec_mod.unit_vector = unit_vector
_vec_mod.vector_dot_product = vector_dot_product
_sys.modules.setdefault("vector", _vec_mod)

_wf_mod = types.ModuleType("wireframe_3d")
_wf_mod.Vector3 = Vector3
_sys.modules.setdefault("wireframe_3d", _wf_mod)

# NOW import autopilot (safe because all its imports are satisfied above)
import autopilot as _ap


# ---------------------------------------------------------------------------
# Scenario dataclass
# ---------------------------------------------------------------------------

@dataclass
class Scenario:
    """Describes a single test run."""
    name: str = "default"

    # Ship starting position (world units)
    ship_x: float = 0.0
    ship_y: float = 0.0
    ship_z: float = -20000.0

    # Which direction the ship is initially pointing  (world space)
    ship_fwd_x: float = 0.0
    ship_fwd_y: float = 0.0
    ship_fwd_z: float = 1.0      # pointing toward +Z (toward station by default)

    # Planet position
    planet_x: float = 0.0
    planet_y: float = 0.0
    planet_z: float = 30000.0

    # Station position
    station_x: float = 0.0
    station_y: float = 0.0
    station_z: float = 0.0

    # Station nose direction (slot faces this way)
    station_nose_x: float = 0.0
    station_nose_y: float = 0.0
    station_nose_z: float = -1.0

    # Simulation limits
    max_ticks: int = 4000
    dt: float = 1 / 60

    verbose: bool = False          # print phase transitions + per-tick summary


# ---------------------------------------------------------------------------
# Simulation result
# ---------------------------------------------------------------------------

@dataclass
class SimResult:
    scenario_name: str
    ticks: int
    outcome: str                   # 'docked', 'removed', 'timeout', 'escaped'
    final_distance: float
    phase_log: list = field(default_factory=list)
    position_log: list = field(default_factory=list)   # (tick, x, y, z, phase)


# ---------------------------------------------------------------------------
# Core simulation runner
# ---------------------------------------------------------------------------

def run_scenario(sc: Scenario) -> SimResult:
    """
    Instantiate a Pilot and StubShip for the given Scenario, then tick
    the state machine up to sc.max_ticks times.

    Each tick:
      1. Call pilot.auto_pilot_ship_(ship)
      2. Read flight_roll / flight_climb written by the pilot
      3. Apply vector_func to rotate rotmat and advance ship.location

    Returns a SimResult describing the outcome.
    """
    # Build world objects
    planet  = StubPlanet(Vector(sc.planet_x, sc.planet_y, sc.planet_z))
    station = StubStation(
        Vector(sc.station_x, sc.station_y, sc.station_z),
        nose_dir=Vector(sc.station_nose_x, sc.station_nose_y, sc.station_nose_z),
    )
    fwd = Vector(sc.ship_fwd_x, sc.ship_fwd_y, sc.ship_fwd_z)
    ship = StubShip(
        location=Vector(sc.ship_x, sc.ship_y, sc.ship_z),
        rotmat=rotmat_from_direction(fwd),
        is_player=True,
    )
    gs = StubGS(planet, station, ship, verbose=sc.verbose)
    gs.parent_scene.dt = sc.dt

    pilot = _ap.Pilot(gs)
    pilot.auto_pilot_active = True

    phase_log = []
    position_log = []
    prev_phase = None
    outcome = "timeout"

    for tick in range(sc.max_ticks):
        # Run the autopilot decision for this tick
        pilot.auto_pilot_ship_(ship)

        # Log phase changes
        if pilot.flight_phase != prev_phase:
            phase_log.append((tick, pilot.flight_phase))
            if sc.verbose:
                print(f"  tick {tick:5d}  phase → {pilot.flight_phase}")
            prev_phase = pilot.flight_phase

        # Apply kinematics: rotate orientation, then advance position
        roll  = gs.space.flight_roll
        climb = gs.space.flight_climb
        print(roll, climb)
        ship.rotmat, delta = apply_vector_func(
            ship.rotmat, roll, climb, ship.velocity, pilot
        )
        ship.location = ship.location + delta

        # Record position every 10 ticks
        if tick % 10 == 0:
            d = (ship.location - station.location).magnitude
            position_log.append((tick, ship.location.x, ship.location.y,
                                  ship.location.z, pilot.flight_phase, d))

        # Check terminal conditions
        if ship.flags & _fake_cs.FLG_REMOVE:
            outcome = "docked/removed"
            break
        if gs.break_mode == "docking":
            outcome = "docked"
            break

    final_dist = (ship.location - station.location).magnitude

    return SimResult(
        scenario_name=sc.name,
        ticks=tick + 1,
        outcome=outcome,
        final_distance=final_dist,
        phase_log=phase_log,
        position_log=position_log,
    )


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

def print_result(r: SimResult):
    print(f"\n{'='*60}")
    print(f"Scenario : {r.scenario_name}")
    print(f"Outcome  : {r.outcome}  after {r.ticks} ticks")
    print(f"Final dist to station: {r.final_distance:.1f} units")
    print("Phase log:")
    for tick, phase in r.phase_log:
        print(f"  tick {tick:5d}  →  {phase}")
    if r.position_log:
        print("Position samples (every 10 ticks):")
        print(f"  {'tick':>6}  {'x':>9}  {'y':>9}  {'z':>9}  {'dist':>9}  phase")
        for entry in r.position_log[::max(1, len(r.position_log)//15)]:
            tick, x, y, z, phase, d = entry
            print(f"  {tick:6d}  {x:9.1f}  {y:9.1f}  {z:9.1f}  {d:9.1f}  {phase}")


# ---------------------------------------------------------------------------
# Pre-built scenario library
# ---------------------------------------------------------------------------

SCENARIOS = {

    # ----- basic approach scenarios -----

    "direct_approach": Scenario(
        name="direct_approach",
        ship_x=0, ship_y=0, ship_z=-15000,
        ship_fwd_x=0, ship_fwd_y=0, ship_fwd_z=1,  # pointing straight at station
        station_x=0, station_y=0, station_z=0,
        station_nose_x=0, station_nose_y=0, station_nose_z=-1,  # slot faces -Z
        planet_x=0, planet_y=0, planet_z=40000,
        max_ticks=3000, verbose=True,
    ),

    "off_axis_approach": Scenario(
        name="off_axis_approach",
        ship_x=5000, ship_y=3000, ship_z=-12000,
        ship_fwd_x=0, ship_fwd_y=0, ship_fwd_z=1,
        station_x=0, station_y=0, station_z=0,
        station_nose_x=0, station_nose_y=0, station_nose_z=-1,
        planet_x=0, planet_y=0, planet_z=40000,
        max_ticks=5000, verbose=True,
    ),

    "behind_station": Scenario(
        name="behind_station",
        ship_x=0, ship_y=0, ship_z=8000,   # behind the station (slot faces -Z)
        ship_fwd_x=0, ship_fwd_y=0, ship_fwd_z=-1,
        station_x=0, station_y=0, station_z=0,
        station_nose_x=0, station_nose_y=0, station_nose_z=-1,
        planet_x=0, planet_y=0, planet_z=40000,
        max_ticks=6000, verbose=True,
    ),

    "far_away": Scenario(
        name="far_away",
        ship_x=0, ship_y=0, ship_z=0,
        ship_fwd_x=1, ship_fwd_y=0, ship_fwd_z=0,   # pointing wrong way
        station_x=0, station_y=60, station_z=4767,
        station_nose_x=0, station_nose_y=0, station_nose_z=-1,        
        planet_x=12, planet_y=8900, planet_z=200000,
        max_ticks=20000, verbose=False,
    ),

    "blocked_by_planet": Scenario(
        # Planet is between ship and station
        name="blocked_by_planet",
        ship_x=0, ship_y=0, ship_z=-30000,
        ship_fwd_x=0, ship_fwd_y=0, ship_fwd_z=1,
        station_x=0, station_y=0, station_z=0,
        station_nose_x=0, station_nose_y=0, station_nose_z=-1,
        planet_x=0, planet_y=0, planet_z=-15000,  # in the path!
        max_ticks=8000, verbose=False,
    ),

    "sideways_station": Scenario(
        # Station slot faces +X instead of -Z
        name="sideways_station",
        ship_x=-10000, ship_y=0, ship_z=0,
        ship_fwd_x=1, ship_fwd_y=0, ship_fwd_z=0,
        station_x=0, station_y=0, station_z=0,
        station_nose_x=1, station_nose_y=0, station_nose_z=0,
        planet_x=0, planet_y=0, planet_z=30000,
        max_ticks=5000, verbose=False,
    ),
    'custom': Scenario(
     name="my_test",
     ship_x=0, ship_y=0, ship_z=0,
     ship_fwd_x=0, ship_fwd_y=0, ship_fwd_z=1,
     planet_x=0, planet_y=0, planet_z=30000,
     max_ticks=5000, verbose=True,),
}

vectors = [
 Vector(x=12.341763297967214, y=8895.853868829396, z=61014.195867125236), #pole 
 Vector(x=-1.0362339876903823, y=96.08624366926566, z=-6767.177144016836), #ip
 Vector(x=-0.6415562296759381, y=60.67698078161314, z=-4767.490661507335)] #station
 
if __name__ == "__main__":    
         
    chosen = list(SCENARIOS.keys())[-1:]
    results = []
    for name in chosen:
        if name not in SCENARIOS:
            print(f"Unknown scenario '{name}'. Available: {list(SCENARIOS)}")
            continue
        sc = SCENARIOS[name]                    
        print(f"\nRunning '{sc.name}' ...")
        r = run_scenario(sc)
        results.append(r)
        print_result(r)

    print("\n" + "="*60)
    print("SUMMARY")
    print(f"  {'Scenario':<25}  {'Outcome':<20}  {'Ticks':>6}  {'Final dist':>10}")
    for r in results:
        print(f"  {r.scenario_name:<25}  {r.outcome:<20}  {r.ticks:>6}  {r.final_distance:>10.1f}")
 
 
