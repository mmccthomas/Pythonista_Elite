
import math
import random
import constants as cs
from vector import Vector, Matrix, unit_vector
from copy import copy


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
        self.hyper_countdown = 0
        self.hyper_name = ""
        self.hyper_distance = 0
        self.hyper_galactic = False
        self.flight_roll = 0
        self.flight_pitch = 0
        self.current_roll = 0
        self.current_climb = 0
        self.integral_roll = 0
        self.integral_climb = 0
        self.prev_error_roll = 0
        self.prev_error_climb = 0
    
    # ------- Rotation helpers
    @staticmethod
    def rotate_x_first(a, b, angle_rad):
        """
        Standard rotation for two components.
        a: first component (e.g., Forward vector)
        b: second component (e.g., Up vector)
        angle_rad: The amount to rotate in radians
        """
        cos_theta = math.cos(angle_rad)
        sin_theta = math.sin(angle_rad)
        
        new_a = a * cos_theta + b * sin_theta
        new_b = b * cos_theta - a * sin_theta
        
        return new_a, new_b
    
    @staticmethod
    def rotate_x_first_(a, b, direction):
        """Rotate two components; returns updated (a, b)."""
        fx, ux = a, b
        if direction < 0:
            a = fx - (fx / 512) + (ux / 19)
            b = ux - (ux / 512) - (fx / 19)
        else:
            a = fx - (fx / 512) - (ux / 19)
            b = ux - (ux / 512) + (fx / 19)
        return a, b
        
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

    @staticmethod
    def rotate_vec_(vec, alpha, beta):
        x, y, z = vec.x, vec.y, vec.z
        y = y - alpha * x
        x = x + alpha * y
        y = y - beta * z
        z = z + beta * y
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
        alpha = self.flight_roll / 256.0
        beta = self.flight_climb / 256.0

        x, y, z = obj.location.x, obj.location.y, obj.location.z
        

        if not (obj.flags & cs.FLG_DEAD):
            if obj.velocity != 0:
                # move object forward vased on its own orientation
                # rotmat[2] is forward
                speed = obj.velocity * 1.5
                x += obj.rotmat[2].x * speed
                y += obj.rotmat[2].y * speed
                z += obj.rotmat[2].z * speed

            if obj.acceleration != 0:
                obj.velocity += obj.acceleration
                obj.acceleration = 0
                max_v = gs.swat.ship_list[obj.type].velocity
                obj.velocity = max(1, min(obj.velocity, max_v))
                
        cos_a, sin_a = math.cos(alpha), math.sin(alpha)
        x, y  = x * cos_a + y * sin_a, y * cos_a - x * sin_a
        
        cos_b, sin_b = math.cos(beta), math.sin(beta)        
        y, z = y * cos_b - z * sin_b, z * cos_b + y * sin_b        
        
        z -= gs.flight_speed

        obj.location.x, obj.location.y, obj.location.z = x, y, z
        obj.distance = math.sqrt(x*x + y*y + z*z)

        if obj.type == cs.SHIP_PLANET:
            beta = 0.0

        for vec in obj.rotmat:
            self.rotate_vec(vec, alpha, beta)

        if obj.flags & cs.FLG_DEAD:
            return
        gs.swat.update_model(obj)
        # handle internal spin rotx, rotz
        # used small fixed step 3 defrees
        STEP = 1 / 19
        
        if obj.rotx != 0:
            angle = STEP if obj.rotx > 0 else -STEP
            # Rotate Forward (rotmat[2]) and Up (rotmat[1])
            obj.rotmat[2], obj.rotmat[1] = self.rotate_pair(obj.rotmat[2], obj.rotmat[1], angle)
            
            if abs(obj.rotx) != 127:
                obj.rotx -= 1 if obj.rotx > 0 else -1

        if obj.rotz != 0:
            angle = STEP if obj.rotz > 0 else -STEP
            # Rotate Side (rotmat[0]) and Up (rotmat[1])
            obj.rotmat[0], obj.rotmat[1] = self.rotate_pair(obj.rotmat[0], obj.rotmat[1], angle)
            
            if abs(obj.rotz) != 127:
                obj.rotz -= 1 if obj.rotz > 0 else -1                        
                
        gs.swat.update_model(obj)
    
    # -------Docking

    def dock_player(self):
        gs = self.gs
        self.pilot.disengage_auto_pilot()
        gs.docked = True
        gs.flight_speed = 0
        self.flight_roll = 0
        self.flight_climb = 0
        gs.front_shield = 255
        gs.aft_shield = 255
        gs.energy = 255
        gs.myship.altitude = 255
        gs.myship.cabtemp = 30
        self.swat.reset_weapons()

    def is_docking(self, sn):
        gs = self.gs
        if gs.auto_pilot:
            return True

        fz = gs.universe[sn].rotmat[2].z
        if fz > -0.90:
            return False

        vec = unit_vector(gs.universe[sn].location)
        if vec.z < 0.927:
            return False

        ux = abs(gs.universe[sn].rotmat[1].x)
        return ux >= 0.84

    def check_docking(self, i):
        gs = self.gs
        if self.is_docking(i):
            self.snd.play_sample(cs.SND_DOCK)
            self.dock_player()
            gs.current_screen = cs.SCR_BREAK_PATTERN
            return

        if gs.flight_speed >= 5:
            self.do_game_over()
            return

        gs.flight_speed = 1
        self.damage_ship(5, gs.universe[i].location.z > 0)
        self.snd.play_sample(cs.SND_CRASH)

    def engage_docking_computer(self):
        gs = self.gs
        if gs.swat.ship_count[cs.SHIP_CORIOLIS] or gs.swat.ship_count[cs.SHIP_DODEC]:
            self.snd.play_sample(cs.SND_DOCK)
            self.dock_player()
            gs.current_screen = cs.SCR_BREAK_PATTERN
    
    # ------- Game over / damage
    
    def do_game_over(self):
        self.snd.play_sample(cs.SND_GAMEOVER)
        self.gs.game_over = True

    def decrease_energy(self, amount):
        self.gs.energy += amount
        if self.gs.energy <= 0:
            self.do_game_over()

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

        loc = gs.universe[0].location
        x, y, z = abs(loc.x), abs(loc.y), abs(loc.z)
        if x > 65535 or y > 65535 or z > 65535:
            return

        x /= 256
        y /= 256
        z /= 256
        dist = x*x + y*y + z*z
        if dist > 65535:
            return

        dist -= 9472
        if dist < 1:
            gs.myship.altitude = 0
            self.do_game_over()
            return

        dist = math.sqrt(dist)
        if dist < 1:
            gs.myship.altitude = 0
            self.do_game_over()
            return

        gs.myship.altitude = dist

    def update_cabin_temp(self):
        gs = self.gs
        gs.myship.cabtemp = 30
        if gs.witchspace:
            return
        if gs.swat.ship_count[cs.SHIP_CORIOLIS] or gs.swat.ship_count[cs.SHIP_DODEC]:
            return

        loc = gs.universe[1].location
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
            return

        dist ^= 255
        gs.myship.cabtemp = dist + 30
        if gs.myship.cabtemp > 255:
            gs.myship.cabtemp = 255
            self.do_game_over()
            return

        if gs.myship.cabtemp >= 224 and gs.cmdr.fuel_scoop:
            gs.cmdr.fuel = min(gs.cmdr.fuel + gs.flight_speed // 2,
                               gs.myship.max_fuel)
            gs.info_message("Fuel Scoop On")
    
    # ------- Station
    
    def make_station_appear(self):
        gs = self.gs
        loc = gs.universe[0].location
        px, py, pz = loc.x, loc.y, loc.z

        vec = Vector(
            (random.randint(0, 32767)) - 16384,
            (random.randint(0, 32767)) - 16384,
            random.randint(0, 32767)
        )
        vec = unit_vector(vec)

        sx = px - vec.x * 65792
        sy = py - vec.y * 65792
        sz = pz - vec.z * 65792

        rotmat = Matrix()
        rotmat[0].x = 1.0
        rotmat[0].y = 0.0
        rotmat[0].z = 0.0
        rotmat[1].x = vec.x
        rotmat[1].y = vec.z
        rotmat[1].z = -vec.y
        rotmat[2].x = vec.x
        rotmat[2].y = vec.y
        rotmat[2].z = vec.z
        # tidy_matrix(rotmat)

        gs.swat.add_new_station(sx, sy, sz, rotmat)
    
    # ------- View transforms
    
    def switch_to_view(self, flip):
        gs = self.gs

        if gs.current_screen in (cs.SCR_REAR_VIEW, cs.SCR_GAME_OVER):
            flip.location.x *= -1
            flip.location.z *= -1
            for row in flip.rotmat:
                row.x *= -1
                row.z *= -1
            return

        if gs.current_screen == cs.SCR_LEFT_VIEW:
            flip.location.x, flip.location.z = flip.location.z, -flip.location.x
            if flip.type < 0:
                return
            for row in flip.rotmat:
                row.x, row.z = row.z, -row.x
            return

        if gs.current_screen == cs.SCR_RIGHT_VIEW:
            flip.location.x, flip.location.z = -flip.location.z, flip.location.x
            if flip.type < 0:
                return
            for row in flip.rotmat:
                row.x, row.z = -row.z, row.x
    
    # ------- Universe update

    def update_universe(self):
        gs = self.gs
        gfx = self.gfx
        #gfx.start_render()

        for i in range(cs.MAX_UNIV_OBJECTS):
            obj = gs.universe[i]
            type = obj.type
            if type == 0:
                continue

            if obj.flags & cs.FLG_REMOVE:
                if type == cs.SHIP_VIPER:
                    gs.cmdr.legal_status |= 64
                bounty = obj.model.header['Bounty']  # gs.ship_list[type].bounty
                if bounty and not gs.witchspace:
                    gs.cmdr.credits += bounty
                    gs.info_message(
                        f"{gs.cmdr.credits // 10}.{gs.cmdr.credits % 10} CR")
                gs.swat.remove_ship(i)
                continue

            if (gs.detonate_bomb
                and not (obj.flags & cs.FLG_DEAD)
                and type not in (cs.SHIP_PLANET, cs.SHIP_SUN,
                                 cs.SHIP_CONSTRICTOR, cs.SHIP_COUGAR,
                                 cs.SHIP_CORIOLIS, cs.SHIP_DODEC)):
                self.snd.play_sample(cs.SND_EXPLODE)
                obj.flags |= cs.FLG_DEAD

            intro_screens = (cs.SCR_INTRO_ONE, cs.SCR_INTRO_TWO,
                             cs.SCR_GAME_OVER, cs.SCR_ESCAPE_POD)
            if gs.current_screen not in intro_screens:
                self.swat.tactics(i)

            self.move_univ_object(obj)

            flip = copy(obj)
            self.switch_to_view(flip)

            if type == cs.SHIP_PLANET:
                if (not gs.swat.ship_count[cs.SHIP_CORIOLIS]
                        and not gs.swat.ship_count[cs.SHIP_DODEC]
                        and obj.distance < 65792):
                    self.make_station_appear()

                continue

            if type == cs.SHIP_SUN:
                continue

            if obj.distance < 170:
                if type in (cs.SHIP_CORIOLIS, cs.SHIP_DODEC):
                    self.check_docking(i)
                else:
                    self.trade.scoop_item(i)
                continue

            if obj.distance > 57344:
                gs.swat.remove_ship(i)
                continue
         
            obj.flags = flip.flags
            # obj.exp_seed = flip.exp_seed
            # obj.exp_delta = flip.exp_delta
            obj.flags &= ~cs.FLG_FIRING

            if not (obj.flags & cs.FLG_DEAD):
                self.swat.check_target(i, flip)

        gfx.finish_render()
        gs.detonate_bomb = False
    
    # ------- HUD elements

    def update_scanner(self):
        gs = self.gs
        gfx = self.gfx
        #gfx.set_clip_region(*cs.HUD_CENTRE)
        for i in range(cs.MAX_UNIV_OBJECTS):
            obj = gs.universe[i]
            if (obj.type <= 0
                    or (obj.flags & cs.FLG_DEAD)
                    or (obj.flags & cs.FLG_CLOAKED)):
                continue

            x = int(obj.location.x) // 256
            y = int(obj.location.y) // 256
            z = int(obj.location.z) // 256

            x1 = x
            y1 = -z // 4
            y2 = y1 - y // 2
            # TODO should apply scaling here
            # assumes y +-28, x +-50
            #if y2 < -28 or y2 > 28 or x1 < -50 or x1 > 50:
            #    continue

            x1 += cs.SCANNER_RECT.center().x
            y1 += cs.SCANNER_RECT.center().y
            y2 += cs.SCANNER_RECT.center().y

            colour = (cs.YELLOW
                      if (obj.flags & cs.FLG_HOSTILE)
                      else cs.WHITE)

            colour = {
                cs.SHIP_MISSILE:  cs.MAGENTA,  # Index 137 is usually a Medium-Dark Magenta or a Deep Violet.
                cs.SHIP_DODEC:    cs.GREEN,
                cs.SHIP_CORIOLIS: cs.GREEN,
                cs.SHIP_VIPER:    cs.GREY_2,  # very light grey
            }.get(obj.type, colour)
            # use scene drawing as its every frame
            for dy in range(4):
                gfx.draw_colour_line(x1+2, y2+dy, x1-3, y2+dy, colour)
            for dx in range(3):
                gfx.draw_colour_line(x1+dx, y1, x1+dx, y2, colour)
                
        #gfx.set_clip_region(*cs.FLIGHT_RECT)
        
    def update_compass(self):
        gs = self.gs
        gfx = self.gfx
        if gs.witchspace:
            return

        un = 1 if (gs.swat.ship_count[cs.SHIP_CORIOLIS]
                   or gs.swat.ship_count[cs.SHIP_DODEC]) else 0
        dest = unit_vector(gs.universe[un].location)

        cx = cs.COMPASS_RECT.center().x + int(dest.x * cs.COMPASS_RECT.w/2)
        cy = cs.COMPASS_RECT.center().y + int(dest.y * cs.COMPASS_RECT.h/2)        
        color = cs.RED if dest.z < 0 else cs.GREEN
        gfx.plot_pixel(cx, cy, color, 10 )   

    def display_speed(self, sx, sy):
        gs = self.gs
        length = ((gs.flight_speed * 64) // gs.myship.max_speed) - 1
        colour = (cs.RED
                  if gs.flight_speed > gs.myship.max_speed * 2 // 3
                  else cs.GOLD)
        self.display_dial_bar(length, sx, sy, colour)

    def display_dial_bar(self, length, x, y, colour=cs.YELLOW):
        # length 0-64
        gfx = self.gfx
        length = length * cs.METER_LENGTH / 64         
        #gfx.draw_colour_line(x, y,   x+length, y, cs.GOLD, width=2)                
        gfx.draw_colour_line(x, y, x+length, y, colour, width=cs.METER_HEIGHT)
        #gfx.draw_colour_line(x, y, x+length, y, cs.DARK_RED)

    def display_shields(self, x, y):
        gs = self.gs        
        self.display_dial_bar(gs.front_shield // 4, x,  y)        
        self.display_dial_bar(gs.aft_shield // 4, x, y-16)

    def display_altitude(self, x, y):        
        self.display_dial_bar(self.gs.myship.altitude // 4, x, y)

    def display_cabin_temp(self, x, y):
        self.display_dial_bar(self.gs.myship.cabtemp // 4, x, y)

    def display_laser_temp(self, x, y):
        self.display_dial_bar(self.gs.laser_temp // 4, x, y)

    def display_energy(self, x, y):
        e = self.gs.energy
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
        x = (nomiss-1)* 22 + sx   

        if gs.swat.missile_target != cs.MISSILE_UNARMED:
            #sprite = (cs.IMG_MISSILE_YELLOW
            #          if gs.swat.missile_target < 0
            #          else cs.IMG_MISSILE_RED)
            colour = (cs.YELLOW
                      if gs.swat.missile_target < 0
                      else cs.RED)          
            gfx.draw_colour_line(x, sy, x+14, sy, colour, width=cs.METER_HEIGHT)
            x -= 22
            nomiss -= 1

        for _ in range(nomiss):
            gfx.draw_colour_line(x, sy, x+14, sy, cs.GREEN, width=cs.METER_HEIGHT) #draw_sprite(cs.IMG_MISSILE_GREEN, x, sy)
            x -= 22

    def update_console(self):
        gs = self.gs
        gfx = self.gfx   
        gfx.set_clip_region(*cs.HUD_RECT)
        self.update_scanner()
        self.update_compass()
        # This is fixed
        left_x = 189
        # This moves with screen size
        right_x =  cs.FLIGHT_RECT.max_x - 217
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
        safe_mode = gs.swat.ship_count[cs.SHIP_CORIOLIS] or gs.swat.ship_count[cs.SHIP_DODEC]

        gs.hud.safe_node.alpha = safe_mode
        gs.hud.ecm_node.alpha = gs.swat.ecm_active
                        
        gfx.set_clip_region(*cs.FLIGHT_RECT)
    
    # -------Flight controls    
        
    def roll_pitch_control(self, key):
        """ PID-based control of roll and pitch """
        if not key.startswith('>'):
            return
        
        # Parse inputs (Assuming these are target percentages -1.0 to 1.0)
        xy = key.removeprefix('>')
        x, y = xy.split(',')
        target_roll = float(x) * self.gs.myship.max_roll
        target_climb = float(y) * self.gs.myship.max_climb
    
        # PID Constants (Tweak these to feel "right")
        # Kp = Responsiveness, Ki = Drift correction, Kd = Damping
        Kp, Ki, Kd = 0.6, 0.05, 0.001
        dt = max(self.gs.parent_scene.dt, 0.015)  # Time since last frame in seconds
    
        # Roll PID Calculation
        error_roll = target_roll - self.current_roll
        self.integral_roll += error_roll * dt
        derivative_roll = (error_roll - self.prev_error_roll) / dt
        
        self.flight_roll = (Kp * error_roll) + (Ki * self.integral_roll) + (Kd * derivative_roll)
        self.prev_error_roll = error_roll
    
        # Pitch/Climb PID Calculation
        error_climb = target_climb - self.current_climb
        self.integral_climb += error_climb * dt
        derivative_climb = (error_climb - self.prev_error_climb) / dt
        
        self.flight_climb = (Kp * error_climb) + (Ki * self.integral_climb) + (Kd * derivative_climb)
        self.prev_error_climb = error_climb
        
    def increase_flight_roll(self):
       # Use a smaller increment for smoother acceleration
       sensitivity = 0.5 
       self.gs.msg.text = f'{self.flight_roll=}'
       if self.flight_roll < self.gs.myship.max_roll:
           self.flight_roll += sensitivity
        
    def decrease_flight_roll(self):
        sensitivity = 0.5
        self.gs.msg.text = f'{self.flight_roll=}'
        if self.flight_roll > -self.gs.myship.max_roll:
            self.flight_roll -= sensitivity
    

    def increase_flight_climb(self):
        #if self.flight_climb > 0:
        #   self.flight_climb = 0
        #else:
        self.gs.msg.text = f'{self.flight_climb=}'   
        if self.flight_climb < self.gs.myship.max_climb:
            self.flight_climb += 1

    def decrease_flight_climb(self):
        #if self.flight_climb < 0:
        #    self.flight_climb = 0
        #else
        self.gs.msg.text = f'{self.flight_climb=}'   
        if self.flight_climb > -self.gs.myship.max_climb:
            self.flight_climb -= 1
    
    #  -------Hyperspace
    
    @staticmethod
    def rotate_byte_left(x):
        return ((x << 1) | (x >> 7)) & 0xFF

    def start_hyperspace(self):
        gs = self.gs
        if self.hyper_ready:
            return
        # planet_name = gs.planet.get_planet_name(gs.hyperspace_planet)
        self.hyper_distance = gs.in_dock.calc_distance_to_planet(
            gs.docked_planet, gs.hyperspace_planet)
        if self.hyper_distance == 0 or self.hyper_distance > gs.cmdr.fuel:
            return

        self.destination_planet = gs.hyperspace_planet
        self.hyper_name = gs.planet.name_planet(self.destination_planet).title()
        self.hyper_ready = True
        self.hyper_countdown =  15
        self.hyper_galactic = False
        self.pilot.disengage_auto_pilot()

    def start_galactic_hyperspace(self):
        gs = self.gs
        if self.hyper_ready or not gs.cmdr.galactic_hyperdrive:
            return
        self.hyper_ready = True
        self.hyper_countdown = 2
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
            setattr(cmdr.galaxy, attr,
                    self.rotate_byte_left(getattr(cmdr.galaxy, attr)))
        gs.docked_planet = gs.find_planet(0x60, 0x60)
        gs.hyperspace_planet = gs.docked_planet

    def enter_witchspace(self):
        gs = self.gs
        gs.witchspace = True
        gs.docked_planet.b ^= 31
        gs.in_battle = True
        gs.flight_speed = 12
        self.flight_roll = 0
        self.flight_climb = 0
        self.stars.create_new_stars()
        gs.swat.clear_universe()
        for _ in range((gs.randint() & 3) + 1):
            self.swat.create_thargoid()
        gs.current_screen = cs.SCR_BREAK_PATTERN
        self.snd.play_sample(cs.SND_HYPERSPACE)
        
    def get_solar_system_vectors(self, seed):
        """
        Simplifies the BBC Elite .SOLAR routine to find initial 
        spawn vectors for the Planet and the Sun.
        
        'seeds' is a list of 16-bit values [s0, s1, s2]
        """
        seeds = seed.raw_seed()
        # Extract the high bytes (equivalent to QQ15+1, +3, +5 in ASM)
        s0_hi = (seeds[0] >> 8) & 0xFF
        s1_hi = (seeds[1] >> 8) & 0xFF
        s2_hi = (seeds[2] >> 8) & 0xFF
    
        # --- 1. Planet Vector ---
        # The game uses bits 0-2 of s0_hi (the economy type) to offset the planet
        eco_bits = s0_hi & 0x07
        
        # The ASM does: (bits + 6 + Carry) >> 1. 
        # Let's assume Carry is 0 for simplicity.
        z_sign = (eco_bits + 6) >> 1 
        
        # x and y are derived by a further rotation (ROR), 
        # making them roughly half of z_sign.
        x_sign = y_sign = z_sign >> 1
        
        planet_vector = (x_sign, y_sign, z_sign)
    
        # --- 2. Sun Vector ---
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
            elite_to_signed(sun_xy),
            elite_to_signed(sun_xy),
            elite_to_signed(sun_z)
        )
    
        return planet_vector, sun_vector


    def complete_hyperspace(self):
        gs = self.gs
        self.hyper_ready = False
        gs.witchspace = False

        if self.hyper_galactic:
            gs.cmdr.galactic_hyperdrive = 0
            self.enter_next_galaxy()
            gs.cmdr.legal_status = 0
        else:
            gs.cmdr.fuel -= self.hyper_distance
            gs.cmdr.legal_status //= 2 # reduce legal_status
            if gs.rand255() > 253 or gs.flight_climb == gs.myship.max_climb:
                self.enter_witchspace()
                return
            gs.docked_planet = self.destination_planet

        gs.cmdr.market_rnd = gs.rand255()
        gs.current_planet_data = gs.planet.generate_planet_stats(gs.docked_planet)
        self.trade.generate_stock_market(gs.current_planet_data.economy)

        gs.flight_speed = 12
        self.flight_roll = 0
        self.flight_climb = 0
        self.stars.create_new_stars()
        gs.swat.clear_universe()
        # gs.generate_landscape(gs.docked_planet.a * 251 + gs.docked_planet.b)
        planet_vector, sun_vector = self.get_solar_system_vectors(gs.docked_planet)
        
        FIST = gs.cmdr.legal_status
        a = gs.docked_planet.a
        pz = ((a & 7) + 6 + FIST & 1) // 2
        px = py = pz // 2
        px <<= 16
        py <<= 16
        pz <<= 16
        if (a & 1) == 0:
            px = -px
            py = -py
        
        gs.swat.add_new_ship(cs.SHIP_PLANET, *planet_vector, None, 0, 0)

        pz = -(((gs.docked_planet.d & 7) | 1) << 16)
        px = ((gs.docked_planet.f & 3) << 16) | ((gs.docked_planet.f & 3) << 8)
        gs.swat.add_new_ship(cs.SHIP_SUN, *sun_vector, None, 0, 0)

        gs.current_screen = cs.SCR_BREAK_PATTERN
        self.gs.sound.play_sample(cs.SND_HYPERSPACE)

    def countdown_hyperspace(self):
        if self.hyper_countdown == 0:
            self.complete_hyperspace()
        else:
            self.hyper_countdown -= 1
    
    # -------Warp / launch
    
    def jump_warp(self):
        gs = self.gs
        passable = {cs.SHIP_ASTEROID, cs.SHIP_CARGO, cs.SHIP_ALLOY,
                    cs.SHIP_ROCK, cs.SHIP_BOULDER, cs.SHIP_ESCAPE_CAPSULE}

        for obj in gs.universe:
            if obj.type > 0 and obj.type not in passable:
                gs.info_message("Mass Locked")
                return

        if gs.universe[0].distance < 75001 or gs.universe[1].distance < 75001:
            gs.info_message("Mass Locked")
            return

        jump = min(
            min(gs.universe[0].distance, gs.universe[1].distance) - 75000,
            1024)

        for obj in gs.universe:
            if obj.type != 0:
                obj.location.z -= jump

        gs.warp_stars = True
        gs.mcount &= 63
        gs.in_battle = False

    def launch_player(self):
        gs = self.gs
        gs.docked = False
        gs.flight_speed = 12
        self.flight_roll = -15
        self.flight_climb = 0
        gs.cmdr.legal_status |= self.trade.carrying_contraband()
        self.stars.create_new_stars()
        gs.swat.clear_universe()
        # gs.generate_landscape(gs.docked_planet.a * 251 + gs.docked_planet.b)

        gs.swat.add_new_ship(cs.SHIP_PLANET, 0, 0, 65536, None, 0, 0)
        rotmat = [Vector(1, 0, 0), Vector(0, 1, 0), Vector(0, 0, 1)]
        rotmat[2].x *= -1
        rotmat[2].y *= -1
        rotmat[2].z *= -1
        gs.swat.add_new_station(0, 0, -256, rotmat)

        gs.current_screen = cs.SCR_FRONT_VIEW
        self.snd.play_sample(cs.SND_LAUNCH)
