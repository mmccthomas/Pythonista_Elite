
import math
import random
import constants as cs
from vector import Vector, Matrix, unit_vector, set_init_matrix, tidy_matrix

from swat import Ship
import traceback
import logging
logger = logging.getLogger(__name__)

NOSEV = 2
ROOFV = 1
SIDEV = 0
PLANET = 0
STATION = 1
SUN = 2


class Space:
    """Flight system and universe management (space.c)."""

    def __init__(self, game_state):
        self.gs = game_state
        self.gfx = game_state.gfx
        self.snd = game_state.sound
        self.swat = game_state.swat
        self.stars = game_state.stars
        self.pilot = game_state.pilot
        self.trade = game_state.trade

        self.destination_planet = None
        self.hyper_ready = False
        self.safe_mode = False
        self.hyper_countdown = 60
        self.hyper_name = ""
        self.hyper_distance = 0
        self.hyper_galactic = False
        self.flight_roll = 0
        self.flight_climb = 0
        self.flight_yaw = 0
        self.yaw_coupling = cs.YAW_COUPLING                 
        self.low_altitude = False
        self.in_corona = False
    
        ship = Ship()
        # ship.location = Vector(0.0, 0.0, 0.0)
        ship.rotmat = set_init_matrix()
        # make nose point forward, unlike all other ships
        ship.rotmat[NOSEV].z = 1
        ship.type = -96
        ship.velocity = self.gs.flight_speed
        
        ship.is_player = True
        self.ship = ship
        self.compass_target = PLANET
        self.jump_start = 0
        
    # ------- Rotation helpers

    
    @staticmethod
    def rotate_vec_yaw(vec, gamma):
        """Rotate a vector around Y axis (yaw)."""
        x, y, z = vec.x, vec.y, vec.z
        cos_g = math.cos(gamma)
        sin_g = math.sin(gamma)
        # Y-axis rotation: affects X and Z only
        x_new = x * cos_g - z * sin_g
        z_new = z * cos_g + x * sin_g
        vec.x, vec.y, vec.z = x_new, y, z_new
        
    @staticmethod
    def rotate_vec(vec, alpha, beta):
        x, y, z = vec.x, vec.y, vec.z
        
        # Rotation around Z-axis (Roll / Alpha)
        # Note: original code used y = y - alpha*x; x = x + alpha*y
        cos_a = math.cos(alpha)
        sin_a = math.sin(alpha)
        x_new = x * cos_a + y * sin_a
        y_new = y * cos_a - x * sin_a
        x, y = x_new, y_new
    
        # Rotation around X-axis (Pitch / Beta)
        # Note: original code used y = y - beta*z; z = z + beta*y
        cos_b = math.cos(beta)
        sin_b = math.sin(beta)
        y_new = y * cos_b - z * sin_b
        z_new = z * cos_b + y * sin_b
        y, z = y_new, z_new
    
        vec.x, vec.y, vec.z = x, y, z
                    
    # ------- Universe object movement
    @staticmethod
    def rotate_pair(v1, v2, angle):
        """Rotates two vectors relative to each other using standard trig."""
        c, s = math.cos(angle), math.sin(angle)
        
        # We create new Vector objects to avoid mutating mid-calculation
        new_v1 = Vector(v1.x * c + v2.x * s, v1.y * c + v2.y * s, v1.z * c + v2.z * s)
        new_v2 = Vector(v2.x * c - v1.x * s, v2.y * c - v1.y * s, v2.z * c - v1.z * s)
        
        return new_v1, new_v2
        
    def move_univ_object(self, obj):
        gs = self.gs
        # convert control inputs to radians
        # max roll is 31, so 0.144 radians 8 degrees
        alpha = self.flight_roll / 256.0 / 8
        beta = self.flight_climb / 256.0 / 8
        x, y, z = obj.location.to_tuple
        
        if not (obj.flags & cs.FLG_DEAD):
            if obj.velocity != 0:
                # move object forward vased on its own orientation
                # rotmat[NOSEV] is forward
                speed = obj.velocity * 1.5
                x += obj.rotmat[NOSEV].x * speed
                y += obj.rotmat[NOSEV].y * speed
                z += obj.rotmat[NOSEV].z * speed

            if obj.acceleration != 0:
                obj.velocity += obj.acceleration
                obj.acceleration = 0
                max_v = gs.swat.ship_list[obj.type].velocity
                obj.velocity = max(1, min(obj.velocity, max_v))
                
        cos_a, sin_a = math.cos(alpha), math.sin(alpha)
        x, y = x * cos_a + y * sin_a, y * cos_a - x * sin_a
        
        cos_b, sin_b = math.cos(beta), math.sin(beta)
        y, z = y * cos_b - z * sin_b, z * cos_b + y * sin_b
        # bring everything forward by player speed
         
        z -= gs.flight_speed
           
        # Auto-yaw: couple roll into lateral X movement ---
        # Yaw naturally follows bank — rolling right drifts nose right
        yaw_rate = self.flight_roll * self.yaw_coupling / 256.0 / 8
        cos_y, sin_y = math.cos(yaw_rate), math.sin(yaw_rate)
        x, z = x * cos_y - z * sin_y, z * cos_y + x * sin_y
        
        obj.location.x, obj.location.y, obj.location.z = x, y, z
        obj.distance = math.sqrt(x*x + y*y + z*z)
        # Single sync call — renderer sees updated state immediately
        # obj.sync_model()
        if obj.type == cs.SHIP_PLANET:
            beta = 0.0

        for vec in obj.rotmat:
            self.rotate_vec(vec, alpha, beta)
            # Also yaw the object's own rotmat to stay consistent
            self.rotate_vec_yaw(vec, yaw_rate)

        if obj.flags & cs.FLG_DEAD:
            return
        # obj.sync_model()
        # handle internal spin rotx, rotz
        # used small fixed step 3 defrees
        STEP = 1 / (19 * 16)
        
        if obj.rotx != 0:
            angle = STEP if obj.rotx > 0 else -STEP
            # Rotate Forward (rotmat[NOSEV]) and Up (rotmat[ROOFV])
            obj.rotmat[NOSEV], obj.rotmat[ROOFV] = self.rotate_pair(obj.rotmat[NOSEV], obj.rotmat[ROOFV], angle)
            
            if abs(obj.rotx) != 127:
                obj.rotx -= 1 if obj.rotx > 0 else -1

        if obj.rotz != 0:
            angle = STEP if obj.rotz > 0 else -STEP
            # Rotate Side (rotmat[SIDEV]) and Up (rotmat[ROOFV])
            obj.rotmat[SIDEV], obj.rotmat[ROOFV] = self.rotate_pair(obj.rotmat[SIDEV], obj.rotmat[ROOFV], angle)
            
            if abs(obj.rotz) != 127:
                obj.rotz -= 1 if obj.rotz > 0 else -1
                
        # handle internal spin rotx, roty, rotz

        if hasattr(obj, 'roty') and obj.roty != 0:
            angle = STEP if obj.roty > 0 else -STEP
            # Rotate Side (rotmat[SIDEV]) and Nose (rotmat[NOSEV]) relative to each other
            obj.rotmat[SIDEV], obj.rotmat[NOSEV] = self.rotate_pair(obj.rotmat[SIDEV], obj.rotmat[NOSEV], angle)
            # Single sync call — renderer sees updated state immediately
            # obj.sync_model()
    
    # -------Docking

    def dock_player(self):
        logger.debug('dock_player')
        gs = self.gs
        self.pilot.disengage_auto_pilot()
        gs.docked = True
        gs.cmdr.ship_x = gs.present_planet.x
        gs.cmdr.ship_y = gs.present_planet.y
        gs.flight_speed = 0
        y = 2 * gs.flight_speed / gs.myship.max_speed - 1.0
        gs.parent_scene.joystick_thrust.set_position(y=y)
        self.flight_roll = 0
        self.flight_climb = 0
        gs.front_shield = 255
        gs.aft_shield = 255
        gs.energy = 255
        gs.myship.altitude = 255
        gs.myship.cabtemp = 30
        gs.on_final_approach = False
        self.hide_planet()        
        self.swat.reset_weapons()
        self.swat.clear_universe(all_others=True)
        gs._change_flight_keys(False)
        
    @staticmethod
    def _cos(deg):
        return math.cos(math.radians(deg))
        
    def is_docking(self, sn):
        gs = self.gs
        logger.debug('checking dock')
        if gs.auto_pilot:
            return True
            
        # approach angle
        fz = -gs.universe[sn].rotmat[NOSEV].z
        logger.debug(f'{fz=}')
        if fz < self._cos(26):
            return False
            
        # cone of safe approach
        vec = unit_vector(gs.universe[sn].location)
        logger.debug(f'{vec=}')
        if vec.z < self._cos(22):
            return False
            
        # rotation
        ux = abs(gs.universe[sn].rotmat[ROOFV].x)
        logger.debug(f'{ux=}')
        if ux < 0:
           ux = -ux
        if ux < self._cos(33):
            return False
        
        return True

    def check_docking(self, i):
        gs = self.gs
        self.gs.info_message('Final Docking')
        logger.debug('final docking')
        gs.on_final_approach = True
        # self.gs.pilot.fly_to_docking_bay(self.ship)
        if self.is_docking(i):
            self.snd.play_sample(cs.SND_DOCK)
            self.dock_player()
            self.gs.break_mode = 'docking'
            gs.current_screen = cs.SCR_BREAK_PATTERN
            return

        if gs.flight_speed >= 5:
            self.do_game_over('speed')
            return
        if gs.energy_status.check():
            gs.flight_speed = 1
            logger.debug('ship damage 5')
            self.damage_ship(5, gs.universe[i].location.z > 0)
            self.snd.play_sample(cs.SND_CRASH)

    def engage_docking_computer(self):       
        self.snd.play_sample(cs.SND_DOCK)
        self.dock_player()
        self.gs.break_mode = 'docking'
        # gs.current_screen = cs.SCR_BREAK_PATTERN
    
    # ------- Game over / damage
    
    def do_game_over(self, reason=''):
        # debug crashes
        traceback.print_stack()
        logger.debug(reason)
        self.snd.play_sample(cs.SND_GAMEOVER)
        self.gs.game_over = True

    def decrease_energy(self, amount):
        self.gs.energy += amount
        if self.gs.energy <= 0:
            self.do_game_over('no energy')

    def damage_ship(self, damage, front):
        if damage <= 0:
            return
        gs = self.gs
        shield = gs.front_shield if front else gs.aft_shield
        shield -= damage
        if shield < 0:
            self.decrease_energy(shield)
            shield = 0
        if front:
            gs.front_shield = shield
        else:
            gs.aft_shield = shield

    def regenerate_shields(self):
        gs = self.gs
        if gs.energy > 127:
            if gs.front_shield < 255:
                gs.front_shield += 1
                gs.energy -= 1
            if gs.aft_shield < 255:
                gs.aft_shield += 1
                gs.energy -= 1
        gs.energy += 1 + gs.cmdr.energy_unit
        gs.energy = min(gs.energy, 255)
    
    # ------- Altitude / temperature

    def update_altitude(self):
        gs = self.gs
        gs.myship.altitude = 255
        if gs.witchspace:
            return

        loc = gs.universe[PLANET].location
        x, y, z = abs(loc.x), abs(loc.y), abs(loc.z)
        if x > 65535 or y > 65535 or z > 65535:
            return

        x /= 256
        y /= 256
        z /= 256
        dist = x*x + y*y + z*z
        if dist > 65535:
            return
        # logger.debug(dist)
        if dist < 32768:
           if (self.gs.mcount & 63) == 0:
              self.gs.info_message(f"Low Altitude {dist:.0f}km")
           self.low_altitude = True
        else:
            self.low_altitude = False
        
        # dist -= 9472
        # if dist < 1:
        #    gs.myship.altitude = 0
         #   self.do_game_over()
         #   return

        dist = math.sqrt(dist)
        if dist < 1:
            gs.myship.altitude = 0
            self.do_game_over('altitude')
            return

        gs.myship.altitude = dist

    def update_cabin_temp(self):
        gs = self.gs
        gs.myship.cabtemp = 30
        if gs.witchspace:
            return
        object = self.gs.universe[SUN]                      
        loc = object.location
        x = abs(int(loc.x))
        y = abs(int(loc.y))
        z = abs(int(loc.z))
        if x > 65535 or y > 65535 or z > 65535:
            return
        
        x //= 256
        y //= 256
        z //= 256
        dist = (x*x + y*y + z*z) // 256
        if dist > 255:
            gs.myship.cabtemp = 30
            return

        dist ^= 255
        gs.myship.cabtemp = dist + 30
        if gs.myship.cabtemp > 255:
            gs.myship.cabtemp = 255
            self.do_game_over('cabin temp')
            return
            
        self.in_corona = gs.myship.cabtemp >= 224
        
        if self.in_corona and gs.cmdr.fuel_scoop:
            gs.cmdr.fuel = min(gs.cmdr.fuel + gs.flight_speed // 2,
                               gs.myship.max_fuel)
            gs.info_message("Fuel Scoop On")
                
    # --------Planet 
    def close_to_planet(self):
       return self.gs.universe[STATION].distance < 65792
       
    def hide_planet(self):
       try:
           self.gs.swat.planet_image.planet.alpha = 0
       except AttributeError:
           pass
       
    def show_planet(self):
       try:
           self.gs.swat.planet_image.planet.alpha = 1
       except AttributeError:
           pass
       
    # ------- Station
    
    def make_station_appear(self):
        gs = self.gs
        loc = gs.universe[PLANET].location
        px, py, pz = loc.x, loc.y, loc.z

        vec = Vector(
            random.randint(-16384, 16383),
            random.randint(-16384, 16383),
            random.randint(0, 32767)
        )
        vec = unit_vector(vec)

        sx = px - vec.x * 65792
        sy = py - vec.y * 65792
        sz = pz - vec.z * 65792
        d = 1
        rotmat = Matrix([Vector(1.0, 0.0, 0.0),
                        Vector(vec.x, vec.z, -vec.y),
                        Vector(vec.x, vec.y, d*vec.z)])
        
        gs.swat.add_new_station(sx, sy, sz, rotmat)
        
    def change_view(self):
        """
        Changes the yaw for the camera.
        This is the same as looking over shoulder without changing
        position vectors
        """
        gs = self.gs
        
        if gs.current_screen in (cs.SCR_REAR_VIEW, cs.SCR_GAME_OVER):
            gs.camera.yaw = math.radians(180)
        elif gs.current_screen == cs.SCR_LEFT_VIEW:
            gs.camera.yaw = math.radians(90)
        elif gs.current_screen == cs.SCR_RIGHT_VIEW:
            gs.camera.yaw = math.radians(-90)
        elif gs.current_screen == cs.SCR_FRONT_VIEW:
            gs.camera.yaw = math.radians(0)
           
    # ------- Universe update
    
    def populate_universe(self):
        # create planet, station and sun       
        gs = self.gs 
        self.stars.create_new_stars()
        gs.swat.clear_universe()        
        gs.swat.generate_landscape()                
        planet_vector, sun_vector = self.get_solar_system_vectors(gs.present_planet)
        gs.swat.add_new_ship(cs.SHIP_PLANET, *planet_vector, None, 0, 0)
        self.make_station_appear()        
        gs.swat.add_new_ship(cs.SHIP_SUN, *sun_vector, None, 0, 0)
        # check distances betweeb sun, planet and station
        logger.debug(f'station-planet {(self.gs.universe[STATION].location - self.gs.universe[PLANET].location).magnitude:.0f}') 
        logger.debug(f'sun-planet {(self.gs.universe[SUN].location - self.gs.universe[PLANET].location).magnitude:.0f}') 
        logger.debug(f'station-sun {(self.gs.universe[SUN].location - self.gs.universe[STATION].location).magnitude:.0f}') 
        
    def update_universe(self):
        gs = self.gs
        gfx = self.gfx
        # gfx.start_render()
        self.change_view()
        for i, obj in enumerate(gs.universe):
            type = obj.type
            if type == 0:
                continue
                
            intro_screens = (cs.SCR_INTRO_ONE, cs.SCR_INTRO_TWO,
                             cs.SCR_GAME_OVER, cs.SCR_ESCAPE_POD)
            if gs.current_screen not in intro_screens:
                self.swat.tactics(i)
                
            self.move_univ_object(obj)
            tidy_matrix(obj.rotmat)
            
            obj.sync_model()
            # give time for explosion
            # remove after exploded
            if obj.flags & cs.FLG_REMOVE:
                if type == cs.SHIP_VIPER:
                    gs.cmdr.legal_status |= 64
                bounty = obj.model.header['Bounty']  # gs.ship_list[type].bounty
                if bounty and not gs.witchspace:
                    gs.cmdr.credits += bounty * 10
                    gs.info_message(
                        f"Bounty {bounty} CR")
                gs.swat.remove_ship(i)
                continue

            if (gs.detonate_bomb
                and not (obj.flags & cs.FLG_DEAD)
                and i not in [SUN, PLANET, STATION]
                and type not in [cs.SHIP_CONSTRICTOR, cs.SHIP_COUGAR]):
                  self.snd.play_sample(cs.SND_EXPLODE)
                  obj.flags |= cs.FLG_DEAD                                                                                                                

            if i == SUN:
                # obj.sync_model()
                continue
            # limit speed within 2k of station
            if i == STATION and obj.distance < 2000:
                gs.myship.max_speed = 5
            else:
                gs.myship.max_speed = 50
            if obj.distance < 170:
                if i == STATION:
                    self.check_docking(i)
                elif i == PLANET:
                    continue                
                elif type == cs.SHIP_MISSILE:
                    continue
                else:
                    # this should be one time only, not every cycle
                    self.trade.scoop_item(i, gs.universe)
                    gs.universe[i].type = 0
                # continue

            if obj.distance > 57344 and i > SUN: # not sun, planet or station
                gs.swat.remove_ship(i)
                # continue
         
            # obj.flags = flip.flags
            # obj.exp_seed = flip.exp_seed
            # obj.exp_delta = flip.exp_delta
            obj.flags &= ~cs.FLG_FIRING

            if not (obj.flags & cs.FLG_DEAD):
                self.swat.check_target(i, obj)
            
            # gsupdate_model.swat.update_model(obj)
        gfx.finish_render()
        gs.detonate_bomb = False
    
    # ------- HUD elements

    def update_scanner(self):
        gs = self.gs
        gfx = self.gfx
        gfx.set_clip_region(*cs.HUD_CENTRE)
        for i in range(cs.MAX_UNIV_OBJECTS):
            obj = gs.universe[i]
            if (obj.type == 0
                    or (obj.flags & cs.FLG_DEAD)
                    or (obj.flags & cs.FLG_CLOAKED)):
                continue

            x = int(obj.location.x) // 256
            y = int(obj.location.y) // 256
            z = int(obj.location.z) // 256
            dir = 1
            x1 = x
            y1 = dir * z // 4
            y2 = y1 - y // 2

            x1 += cs.SCANNER_RECT.center().x
            y1 += cs.SCANNER_RECT.center().y
            y2 += cs.SCANNER_RECT.center().y
     
            colour = (cs.YELLOW
                      if (obj.flags & cs.FLG_HOSTILE)
                      else cs.WHITE)
            colour = {
                cs.SHIP_PLANET: cs.ORANGE,
                cs.SHIP_SUN: cs.ORANGE,
                cs.SHIP_MISSILE:  cs.MAGENTA,  # Index 137 is usually a Medium-Dark Magenta or a Deep Violet.
                cs.SHIP_DODEC:    cs.GREEN,
                cs.SHIP_CORIOLIS: cs.GREEN,
                cs.SHIP_VIPER:    cs.GREY_2,  # very light grey
            }.get(obj.type, colour)
            colours = {
             #        Dot. Stick2
             0: [cs.GREEN, cs.GREEN],  # clean
             cs.FLG_PLANET: [cs.ORANGE, cs.ORANGE],
             cs.FLG_STATION: [cs.CYAN, cs.CYAN],
             cs.FLG_POLICE: [cs.YELLOW, cs.YELLOW],  # tracked
             cs.FLG_INACTIVE: [cs.GREEN, cs.YELLOW],  # debris
             cs.FLG_MISSILE: [cs.YELLOW, cs.RED],  # missile
             cs.FLG_ALIEN: [cs.RED, cs.RED],  # thargoid
             cs.FLG_BOLD | cs.FLG_ANGRY: [cs.GREEN, cs.RED]}  # pirate/bounty hunter
             
            for k, v in colours.items():
                if obj.flags & k:
                    colour = v
                    break
            else:
               colour = colours[0]
            # use scene drawing as its every frame
            gfx.draw_colour_line(x1, y2, x1+5, y2, colour[0], width=5)  # top
            # this allows striped stalks
            dy = (y2 - y1) / 4
            for i in range(4):
                gfx.draw_colour_line(x1, y1 + i * dy, x1, y1 + (i + 1) * dy, colour[i % 2], width=3)
                
        gfx.set_clip_region(*cs.FLIGHT_RECT)
        
    def set_compass(self, mode='planet'):
        if mode == 'planet':
            self.compass_target = PLANET
        else:
            self.compass_target = SUN
            
    def update_compass(self):
        gs = self.gs
        gfx = self.gfx
        if gs.witchspace:
            return

        if self.safe_mode:
            # Point compass toward the docking approach point:
            # a position directly in front of the station along its nose vector
            station = gs.universe[STATION]
            
            # Station nose vector (rotmat[NOSEV]) points toward player when correct
            # Approach point is station position + nose * approach_distance
            approach_dist = 100  # tune this — in the same units as location
            approach = station.location + station.rotmat[NOSEV] * approach_dist
            dest = unit_vector(approach)
        else:
            
            dest = unit_vector(gs.universe[self.compass_target].location)
                    
        cx = cs.COMPASS_RECT.center().x + int(dest.x * cs.COMPASS_RECT.w/2)
        cy = cs.COMPASS_RECT.center().y + int(dest.y * cs.COMPASS_RECT.h/2)
        color = cs.RED if dest.z < 0 else cs.GREEN
        gfx.set_clip_region(*cs.COMPASS_RECT)
        gfx.plot_pixel(cx, cy, color, 10)
        gfx.set_clip_region(*cs.FLIGHT_RECT)

    def display_speed(self, sx, sy):
        gs = self.gs
        length = ((gs.flight_speed * 64) // gs.myship.max_speed) - 1
        colour = (cs.RED
                  if gs.flight_speed > gs.myship.max_speed * 2 // 3
                  else cs.GOLD)
        self.display_dial_bar(length, sx, sy, colour)        
        self.gs.gfx.draw_text(f'{gs.flight_speed:.0f}', sx+length*cs.METER_LENGTH / 64, sy, font_size=15, alignment=6)
         
    def display_dial_bar(self, length, x, y, colour=cs.YELLOW):
        # length 0-64
        if length < 0:
            return
        length = length * cs.METER_LENGTH / 64
        self.gfx.draw_colour_line(x, y, x+length, y, colour, width=cs.METER_HEIGHT)
        
    def display_shields(self, x, y):
        gs = self.gs
        self.display_dial_bar(gs.front_shield // 4, x,  y)
        self.display_dial_bar(gs.aft_shield // 4, x, y-16)

    def display_altitude(self, x, y):
        colour = (cs.RED
                  if self.low_altitude
                  else cs.GOLD)
        self.display_dial_bar(self.gs.myship.altitude // 4, x, y, colour)

    def display_cabin_temp(self, x, y):
        colour = (cs.RED
                  if self.in_corona
                  else cs.GOLD)
        self.display_dial_bar(self.gs.myship.cabtemp // 4, x, y, colour)

    def display_laser_temp(self, x, y):
        self.display_dial_bar(self.gs.laser_temp // 4, x, y)

    def display_energy(self, x, y):
        e = self.gs.energy
        if e < 0:
           return
        bands = [
            (min(e, 64), x, y),
            (min(e - 64, 64) if e > 64 else 0, x, y-16),
            (min(e - 128, 64) if e > 128 else 0, x, y-32),
            (e - 192 if e > 192 else 0, x, y-48),
        ]
        for val, x, y in bands:
            self.display_dial_bar(val, x, y)

    def display_flight_roll(self, sx, sy):
        pos = sx + cs.METER_LENGTH/2 - ((self.flight_roll * cs.METER_LENGTH/2) // self.gs.myship.max_roll)
        self.gfx.draw_colour_line(pos, sy-cs.METER_HEIGHT/2, pos, sy+cs.METER_HEIGHT/2, cs.GOLD, width=4)

    def display_flight_climb(self, sx, sy):
        pos = sx + cs.METER_LENGTH/2 - ((self.flight_climb * cs.METER_LENGTH/2) // self.gs.myship.max_climb)
        self.gfx.draw_colour_line(pos, sy-cs.METER_HEIGHT/2, pos, sy+cs.METER_HEIGHT/2, cs.GOLD, width=4)

    def display_fuel(self, x, y):
        gs = self.gs
        self.display_dial_bar((gs.cmdr.fuel * 64) // gs.myship.max_fuel, x, y)

    def display_missiles(self, sx, sy):
        gs = self.gs
        gfx = self.gfx
        if gs.cmdr.missiles == 0:
            return

        nomiss = min(gs.cmdr.missiles, 4)
        # x is position of last missile
        x = (nomiss - 1) * 22 + sx

        if gs.swat.missile_target != cs.MISSILE_UNARMED:
            # sprite = (cs.IMG_MISSILE_YELLOW
            #          if gs.swat.missile_target < 0
            #          else cs.IMG_MISSILE_RED)
            colour = (cs.YELLOW
                      if gs.swat.missile_target < 0
                      else cs.RED)
            gfx.draw_colour_line(x, sy, x+14, sy, colour, width=cs.METER_HEIGHT)
            x -= 22
            nomiss -= 1

        for _ in range(nomiss):
            gfx.draw_colour_line(x, sy, x+14, sy, cs.GREEN, width=cs.METER_HEIGHT)  # draw_sprite(cs.IMG_MISSILE_GREEN, x, sy)
            x -= 22

    def update_console(self):
        gs = self.gs
        gfx = self.gfx
        
        # This is fixed
        left_x = 189
        # This moves with screen size
        right_x = cs.FLIGHT_RECT.max_x - 217
        # y goes down to increase
        base_y = 113 + 3 * cs.BORDER
        dy = -16
        
        gfx.set_clip_region(*cs.HUD_RECT)
        self.display_shields(left_x, base_y)
        self.display_fuel(left_x, base_y + 2 * dy)
        self.display_cabin_temp(left_x, base_y + 3 * dy)
        self.display_laser_temp(left_x, base_y + 4 * dy)
        self.display_altitude(left_x, base_y + 5 * dy)
        self.display_missiles(left_x, base_y + 6 * dy)
        
        self.display_speed(right_x, base_y)
        self.display_flight_roll(right_x, base_y + dy)
        self.display_flight_climb(right_x, base_y + 2 * dy)
        self.display_energy(right_x, base_y + 3 * dy)
        
        if gs.docked:
            gfx.set_clip_region(*cs.FLIGHT_RECT)
            return

        # enable ecm and safe_mode sprites
        self.safe_mode = gs.space.close_to_planet()
        
        self.update_scanner()
        self.update_compass()
        # self.gs.pilot.draw_flight_director(self.ship)
    
        gs.hud.safe_node.alpha = self.safe_mode
        gs.hud.ecm_node.alpha = gs.swat.ecm_active
                        
        gfx.set_clip_region(*cs.FLIGHT_RECT)
    
    # -------Flight controls
        
    def roll_pitch_control(self, key):
        """ PID-based control of roll and pitch """
        attack = 0.6
        decay = 0.05
        stop_threshold = 0.05
        if key is not None and key.startswith('>'):
            # Parse inputs (Assuming these are target percentages -1.0 to 1.0)
            xy = key.removeprefix('>')
            x, y = xy.split(',')
            target_roll = float(x) * self.gs.myship.max_roll
            target_climb = float(y) * self.gs.myship.max_climb
        else:
            target_roll = 0
            target_climb = 0
        # Damp roll / climb when no key held
        
        stop_threshold = 0.1   # The "Deadzone"
        """
           if self.rolling:
               self.space.flight_roll *= damping_factor
               if abs(self.space.flight_roll) < stop_threshold:
                   self.space.flight_roll = 0
               self.rolling = bool(self.space.flight_roll)
           
           if self.climbing:
               self.space.flight_climb *= damping_factor
               if abs(self.space.flight_climb) < stop_threshold:
                   self.space.flight_climb = 0
               self.climbing = bool(self.space.flight_climb)
        """
        # Determine if we are moving away from zero (Attack)
        # or returning to zero (Release)
        speed = attack if abs(target_roll) > abs(self.flight_roll) else decay
            
        # Standard Linear Interpolation (LERP) formula
        self.flight_roll += (target_roll - self.flight_roll) * speed
        
        # Cleanup for floating point jitter
        if abs(self.flight_roll) < stop_threshold:
            self.flight_roll = 0
        
        speed = attack if abs(target_climb) > abs(self.flight_climb) else decay
            
        # Standard Linear Interpolation (LERP) formula
        self.flight_climb += (target_climb - self.flight_climb) * speed
        # Cleanup for floating point jitter
        if abs(self.flight_climb) < stop_threshold:
            self.flight_climb = 0
        
    def increase_flight_roll(self, units=1):
       # Use a smaller increment for smoother acceleration
       sensitivity = 0.5
       if self.flight_roll < self.gs.myship.max_roll:
           self.flight_roll += sensitivity * units
        
    def decrease_flight_roll(self, units=1):
        sensitivity = 0.5
        if self.flight_roll > -self.gs.myship.max_roll:
            self.flight_roll -= sensitivity * units
    
    def increase_flight_climb(self, units=1):
        if self.flight_climb < self.gs.myship.max_climb:
            self.flight_climb += units

    def decrease_flight_climb(self, units=1):
        if self.flight_climb > -self.gs.myship.max_climb:
            self.flight_climb -= units
    
    #  -------Hyperspace
    
    @staticmethod
    def rotate_byte_left(x):
        return ((x << 1) | (x >> 7)) & 0xFF

    def start_hyperspace(self):
        gs = self.gs
        logger.debug('start hyperspace')
        if self.hyper_ready:
            return
        # planet_name = gs.planet.get_planet_name(gs.hyperspace_planet)
        self.hyper_distance = gs.in_dock.calc_distance_to_planet(
            gs.present_planet, gs.hyperspace_planet)
        if self.hyper_distance == 0 or self.hyper_distance > gs.cmdr.fuel:
            return

        self.destination_planet = gs.hyperspace_planet
        self.hyper_name = gs.planet.name_planet(self.destination_planet).title()
        self.hyper_ready = True
        self.hyper_countdown = 15
        
        self.hyper_galactic = False
        self.pilot.disengage_auto_pilot()

    def start_galactic_hyperspace(self):
        gs = self.gs
        if self.hyper_ready or not gs.cmdr.galactic_hyperdrive:
            return
        self.hyper_ready = True
        self.hyper_countdown = 60
        self.hyper_galactic = True
        self.pilot.disengage_auto_pilot()

    def display_hyper_status(self):
        gs = self.gs
        gfx = self.gfx

        if gs.current_screen in cs.SCR_OUTSIDE:
            gfx.display_text(5, 5, str(self.hyper_countdown))
            if self.hyper_galactic:
                gfx.display_centre_text(358, "Galactic Hyperspace", 120,
                                        cs.WHITE)
            else:
                gfx.display_centre_text(cs.NUM_LINES-1,
                                        f"Hyperspace - {self.hyper_name}",
                                        120, cs.WHITE)
        else:
            gfx.display_text(5, 5, str(self.hyper_countdown))

    def enter_next_galaxy(self):
        gs = self.gs
        cmdr = gs.cmdr
        cmdr.galaxy_number = (cmdr.galaxy_number + 1) & 7
        for attr in ('a', 'b', 'c', 'd', 'e', 'f'):
            setattr(cmdr.galaxy_seed, attr,
                    self.rotate_byte_left(getattr(cmdr.galaxy_seed, attr)))
        gs.galaxy_seed = cmdr.galaxy_seed
        gs.present_planet = gs.planet.find_planet(0xe5, 0x9f, gs.galaxy_seed)
        gs.hyperspace_planet = gs.present_planet

    def enter_witchspace(self):
        gs = self.gs
        gs.witchspace = True
        gs.present_planet.b ^= 31
        gs.in_battle = True
        gs.flight_speed = 12
        self.flight_roll = 0
        self.flight_climb = 0
        gs.swat.planet_image.planet.alpha = 0
        self.stars.create_new_stars()
        gs.swat.clear_universe()
        for _ in range((gs.rand16bit() & 3) + 1):
            self.swat.create_thargoid()
        gs.info_message('Witch Space!!')
        gs.current_screen = cs.SCR_BREAK_PATTERN
        self.snd.play_sample(cs.SND_HYPERSPACE)
    
    @staticmethod
    def get_solar_system_vectors(seed):
        """
        Simplifies the BBC Elite .SOLAR routine to find initial
        spawn vectors for the Planet and the Sun.
        
        'seeds' is a list of 16-bit values [s0, s1, s2]
        planet is at (xsign 0 0), (ysign 0 0), (zsign 0 0)
        i.e (0 or 65536). ...
        """
        seeds = seed.raw_seed()
        # Extract the high bytes (equivalent to QQ15+1, +3, +5 in ASM)
        s0_hi = (seeds[0] >> 8) & 0xFF
        s1_hi = (seeds[1] >> 8) & 0xFF
        s2_hi = (seeds[2] >> 8) & 0xFF
    
        # Planet Vector ---
        # The game uses bits 0-2 of s0_hi (the economy type) to offset the planet
        eco_bits = s0_hi & 0x07
        
        # The ASM does: (bits + 6 + Carry) >> 1.
        z_sign = (eco_bits + 6) >> 1
        
        # x and y are derived by a further rotation (ROR)
        # making them roughly half of z_sign.
        x_sign = y_sign = z_sign >> 1
        if z_sign & 0x01:
          x_sign = y_sign = -x_sign
        
        planet_vector = (x_sign << 16, y_sign << 16, z_sign << 16)
    
        # Sun Vector ---
        # Sun Z is determined by bits 0-2 of s1_hi, forced to be negative (behind you)
        # ORA #%10000001 sets the sign bit (7) and the value bit (0)
        sun_z = (s1_hi & 0x07) | 0x81
        
        # Sun X and Y are determined by bits 0-1 of s2_hi
        sun_xy = s2_hi & 0x03
        
        # In Elite's coordinate system, bit 7 is the sign bit.
        # We convert that to standard signed integers here:
        def elite_to_signed(val):
            magnitude = val & 0x7F
            return -magnitude if (val & 0x80) else magnitude
    
        sun_vector = (
            elite_to_signed(sun_xy) << 16,
            elite_to_signed(sun_xy) << 16,
            elite_to_signed(sun_z) << 16
        )
    
        return planet_vector, sun_vector

    def complete_hyperspace(self):
        gs = self.gs
        self.hyper_ready = False
        gs.witchspace = False
        logger.debug('completed hyperspace')
        if self.hyper_galactic:
            gs.cmdr.galactic_hyperdrive = 0
            self.enter_next_galaxy()
            gs.cmdr.legal_status = 0
        else:
            gs.cmdr.fuel -= self.hyper_distance
            gs.cmdr.legal_status //= 2  # reduce legal_status
            if gs.rand255() > 253 or gs.flight_climb == gs.myship.max_climb:
                self.enter_witchspace()
                return
            gs.present_planet = self.destination_planet
            logger.debug('Completed hyperspace')
        gs.cmdr.market_rnd = gs.rand255()
        gs.current_planet_data = gs.planet.generate_planet_stats(gs.present_planet)
        gs.trade.stock_market = self.trade.generate_stock_market(gs.current_planet_data.economy)

        gs.flight_speed = 12
        self.flight_roll = 0
        self.flight_climb = 0
        self.populate_universe()
        rotmat = [Vector(1, 0, 0), Vector(0, 1, 0), Vector(0, 0, 1)]     
        gs.ship.rotmat = rotmat
        #self.stars.create_new_stars()
        #gs.swat.clear_universe()
        #gs.swat.generate_landscape()
        #planet_vector, sun_vector = self.get_solar_system_vectors(gs.present_planet)
        #gs.swat.add_new_ship(cs.SHIP_PLANET, *planet_vector, None, 0, 0)
        #gs.swat.add_new_ship(cs.SHIP_SUN, *sun_vector, None, 0, 0)

        gs.current_screen = cs.SCR_BREAK_PATTERN
        self.gs.sound.play_sample(cs.SND_HYPERSPACE)

    def countdown_hyperspace(self):
        if self.hyper_countdown == 0:
            self.complete_hyperspace()
        else:
            self.hyper_countdown -= 1
    
    # -------Warp / launch
        
    def cross_product(self, a, b):
        return Vector(a.y*b.z - a.z*b.y,
                      a.z*b.x - a.x*b.z,
                      a.x*b.y - a.y*b.x)

    def teleport(self, target, height, axis=NOSEV):
        # function to move the ship for testing
        # moves object direct in front of ship
        # moves all universe to match
        ship = self.gs.ship       
        
        safe_point = (target.rotmat[axis] * height)
        offset = target.location - safe_point                
        
        # shift all other objects by same offset
        for obj in self.gs.universe:
            if obj.type != 0 and obj != target:
                obj.location -= offset                
        target.location = safe_point
        # Reset the ship's rotation matrix
        ship.rotmat = [Vector(1, 0, 0), Vector(0, 1, 0), Vector(0, 0, 1)]
        self.update_universe()
        # target.sync_model()
        ship.acceleration = 0
        ship.velocity = 0
        self.flight_roll = 0
        self.flight_climb = 0
        self.gs.flight_speed = 0
        
    def jump_direct(self, key):
      """ A massive cheat, jump instantly to point"""
      if key == 'To Sun':
          sun = self.gs.universe[SUN]
          if sun.name == 'SUN':
              self.teleport(sun, height=60000)   
              self.update_universe()
      elif key == 'To Planet':
          # move to location outside planets  atmosphere, on vector to station
          planet = self.gs.universe[PLANET]
          # target above  North Pole
          self.teleport(planet, height=65000, axis=NOSEV)
          self.update_universe()
      elif key == 'To Station':
          # move to location outside station, on vector to entrance          
          self.teleport(self.gs.universe[STATION], height=-2000, axis=NOSEV)
          self.gs.safe_mode = True
          self.update_universe()                                        
         
                
    def jump_warp(self):
        gs = self.gs
        passable = {cs.SHIP_ASTEROID, cs.SHIP_CARGO, cs.SHIP_ALLOY,
                    cs.SHIP_ROCK, cs.SHIP_BOULDER, cs.SHIP_ESCAPE_CAPSULE}
                    
        for obj in gs.universe[:2]:
            if obj.distance < 75001:
                gs.info_message("Mass Locked planet")
                return
                
        for obj in gs.universe[3:]:
            if obj.type > 0 and obj.type not in passable:
                gs.info_message("Mass Locked")
                return
        

        jump = min(
            min(gs.universe[PLANET].distance, gs.universe[SUN].distance) - 75000,
            8192)
        
        for obj in gs.universe:
            if obj.type != 0:
                obj.location.z -= jump

        gs.warp_stars = True
        gs.mcount &= 63
        self.jump_start = gs.parent_scene.t
        gs.stars.speedup = 50
        gs.in_battle = False

    def launch_player(self):
        logger.debug('launching player')
        gs = self.gs
        gs.docked = False
        station = gs.universe[STATION]
        gs.on_final_approach = False
        gs.cmdr.legal_status |= self.trade.carrying_contraband()
        # universe already populated
        # move player onto station.
        
        #self.populate_universe()
        self.stars.create_new_stars()
        gs.swat.clear_universe(all_others=True)

        self.teleport(station, -1000, axis=NOSEV)
        self.update_universe()
        gs.flight_speed =0
        self.flight_roll = 0
        self.flight_climb = 0
        gs.current_screen = cs.SCR_FRONT_VIEW
        self.snd.play_sample(cs.SND_LAUNCH)

                
if __name__ == '__main__':
  from alg_main import MainLoop
  
  g = Space(MainLoop(None))
 
