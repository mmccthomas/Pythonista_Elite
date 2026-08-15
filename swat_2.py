import math
import random
from copy import deepcopy, copy
from types import SimpleNamespace
import colorsys
import constants as cs
from vector import Vector, unit_vector, vector_dot_product, cross_product
from wireframe_3d import load_wireframes_from_json, WireframeObject, WireSphere
from wireframe_3d import Vector3, Sprite3D, WireAxes
from dataclasses import dataclass, field
from planet_generator import Planet, AlienPlanet
# import vdb
# import pdb ; pdb.set_trace()
import logging
logger = logging.getLogger(__name__)
NOSEV = 2
ROOFV = 1
SIDEV = 0
PLANET = 0
STATION = 1
MIN_FIRING_DISTANCE = 8192
HOMING_HIT_DISTANCE = 256   # matches missile_tactics' player-hit threshold
GRACE_TICKS = 32

def rand255():
   return random.randint(0, 255)

      
def rand_no(max):
   return random.randint(0, max)

            
def angle(theta):
   return math.degrees(math.acos(theta))


@dataclass
class UnivObject:
    type: int = 0
    name: str = ''
    model: WireframeObject = field(default_factory=WireframeObject)
    location: Vector = field(default_factory=Vector)
    rotmat: list = field(default_factory=lambda: [Vector(), Vector(), Vector()])
    rotx: int = 0
    roty: int = 0
    rotz: int = 0
    velocity: float = 0
    acceleration: float = 0
    bravery: int = 0
    target: int = 0
    flags: int = 0
    energy: int = 0
    missiles: int = 0
    distance: float = 0.0
    exploding: bool = False
    smooth_climb: float = 0.0
    smooth_roll: float = 0.0
    has_fired: bool = False
    explosion_time: float = 0.0
    invuln_until : int = 0
    
    
    def is_visible(self):
        # within 20 degrees in from and 0 < distance < 20000
        distance = int(self.location.magnitude)
        vec = unit_vector(self.location)
        # Horizontal angle (Azimuth)
        azimuth = math.degrees(math.atan2(vec.x, vec.z))
        elevation = math.degrees(math.atan2(vec.y, math.sqrt(vec.x**2 + vec.z**2)))
        dist_ok = False
        angle_ok = False
        if distance < 0:
          pos = f'behind {distance}'
        elif distance > 30000:
           pos = f'too far {distance}'
        else:
          pos = f'distance ok {distance}'
          dist_ok = True
                
        if (-10 < azimuth < 10) and (-10 < elevation < 10):
           direction = f'angle ok {azimuth:.1f} {elevation:.1f}'
           angle_ok = True
        else:
            direction = f'angle {azimuth:.1f} {elevation:.1f}'
        
        return dist_ok and angle_ok, f'{pos} {direction} {self.direction}'
                  
    @property
    def direction(self):
        nvec = unit_vector(self.location)
        return vector_dot_product(nvec, self.rotmat[NOSEV])        
            
    def sync_model(self):
        """
        Push UnivObject state into the WireframeObject for rendering.
        Uses rotmat as the authoritative rotation source.
        """
        m = self.model
    
        m.rotation.x = self.rotx / 16  # pitch 1/16 radian
        m.rotation.y = self.roty / 8  # yaw 1/16 radian
        m.rotation.z = self.rotz / 16  # roll
        m.rotation_angles_in_world = m.rotation.clone()
     
        # Position sync
        m.position_in_world = Vector3(*self.location.to_tuple)
        
        # Rotation: store rotmat on the model so the renderer can use it
        m.rotmat_world = [Vector3(*row.to_tuple) for row in self.rotmat]
        
    def get_render_vertices(self):
        """Vertices ready for the renderer, using current UnivObject state."""
        return self.model.get_world_vertices_from_transform(
            Vector3(self.location.x, self.location.y, self.location.z),
            self.rotmat
        )


Ship = UnivObject


class Swat:
    """Special Weapons And Tactics — space combat manager """
    @staticmethod
    def _cos(deg):
        return math.cos(math.radians(deg))
        
    def __init__(self, game_state):
        self.gs = game_state          # holds cmdr, ship_list, gfx, snd, etc.

        self.universe: list[UnivObject] = [UnivObject() for _ in range(cs.MAX_UNIV_OBJECTS)]
        self.ship_count: dict[int, int] = {i: 0 for i in range(cs.NO_OF_SHIPS + 1)}
        
        ships = load_wireframes_from_json('files/Elite_ships.json')
        station5 = load_wireframes_from_json('stationv.json')
        ships = ships + station5
        self.ship_dict = {ship.name: ship for ship in ships}
        # add planet and sun
        
        if cs.WIREFRAME:
            self.ship_dict['SUN'] = WireSphere(radius=6400, lat_lines=16, lon_lines=16,
                                               color=cs.YELLOW)
            self.ship_dict['PLANET'] = WireSphere(radius=6400, lat_lines=16, lon_lines=16,
                                                  color=cs.GREEN)
        else:
            self.generate_sun()
            self.generate_landscape()
                                            
        self.ship_dict['SUN'].header = self.ship_dict['CORIOLIS'].header
        self.ship_dict['SUN'].name = ('SUN',)
        self.ship_dict['PLANET'].header = self.ship_dict['CORIOLIS'].header
        self.ship_dict['PLANET'].name = ('PLANET',)
                                                                    
        self.ship_names = {v: k for k, v in cs.SHIP_DICT.items()}
        # construct ship_list dictionary containing operational properties of each
        # ship type
        alternatve_names = {'Max. canisters on demise': 'max_loot',
                            'Bounty': 'bounty',
                            'Max. energy': 'energy',
                            'Max. speed': 'velocity',
                            'Missiles': 'missiles',
                            'Laser power': 'laser_strength',
                            'Targetable area': 'target_area'}
        # SHIP_DICT Translates name to type
        self.ship_list = {}
        for k, v in cs.SHIP_DICT.items():
          if v:
             header = self.ship_dict[k].header
             header_ = {alternatve_names[k1]: v1
                        for k1, v1 in header.items()
                        if k1 in alternatve_names}
             self.ship_list[v] = SimpleNamespace(**header_)
                
        self.laser_counter = 0
        self.laser = 0
        self.laser2 = 0
        self.laser_x = 0
        self.laser_y = 0

        self.ecm_active = 0
        self.missile_target = cs.MISSILE_UNARMED
        self.ecm_ours = 0
        self.in_battle = 0
        self.step = 0
        self.light = 0
        self.HOMING_DAMAGE = 1         # damage applied to target on impact
    
    # ----- Universe management
    def generate_landscape(self):
        # create a new alien planet with correct colour
        # use AlienPlanet to change images/planet_texture.png
        # then change Sprite3D image
        colour = cs.COLOUR_LIST[self.gs.present_planet.colour]
        colour = colorsys.rgb_to_hsv(*colour)[0]
        cloud_threshold = 0.3 + 0.1 * (self.gs.present_planet.c % 6)  # lower is more cloud
        sea_level = 0.4 + 0.1 * (self.gs.present_planet.b % 4)
        # blob_size = 3  # 1 + self.gs.present_planet.d % 2
        img = AlienPlanet(400, 400, colour, seed=self.gs.present_planet.a,
                          cloud_threshold=cloud_threshold,
                          sea_level=sea_level,
                          # blob_size=blob_size
                          ).final
        # rel to screen
        clip_rect = ((cs.FLIGHT_RECT.x + cs.BORDER) / cs.W,  # left
                     cs.TOP_H / cs.H,   # top
                     (cs.FLIGHT_RECT.max_x - 2 * cs.BORDER) / cs.W,  # width
                     (cs.FLIGHT_RECT.h + 4 * cs.BORDER) / cs.H)  # height
        try:
            self.planet_image.planet.remove_from_parent()
        except AttributeError:
            pass
        except Exception as e:
            logger.debug(f'{e}')
        self.planet_image = Planet(size=500, position=cs.FLIGHT_RECT.center(), clip_rect=clip_rect)
        img = self.planet_image.planet
        self.planet_image.planet.z_position = -1
        self.planet_image.planet.alpha = 0
        self.gs.parent_scene.add_child(self.planet_image.planet)
        self.ship_dict['PLANET'] = Sprite3D(img, width=200, height=200,
                                            distance_scale=True, scale=25000,
                                            name='planet')
        self.ship_dict['PLANET'].header = self.ship_dict['CORIOLIS'].header
        self.ship_dict['PLANET'].name = ('PLANET',)
        # logger.debug('generated new planet')
    
    def generate_sun(self, imagepath='images/sun_texture400.png'):
        # create a realistic sun
        # then change Sprite3D image
        clip_rect = ((cs.FLIGHT_RECT.x + cs.BORDER) / cs.W,  # left
                     cs.TOP_H / cs.H,   # top
                     (cs.FLIGHT_RECT.max_x - 2 * cs.BORDER) / cs.W,  # width
                     (cs.FLIGHT_RECT.h + 4 * cs.BORDER) / cs.H)  # height
        try:
            self.sun_image.planet.remove_from_parent()
        except AttributeError:
            pass
        except Exception as e:
            logger.debug(f'{e}')
        self.sun_image = Planet(size=800, position=cs.FLIGHT_RECT.center(),
                                clip_rect=clip_rect,
                                image_path=imagepath,
                                light_dir=(0, 0, 1), soft=0.08)
        img = self.sun_image.planet
        # self.sun_image.planet.color = cs.RED
        self.sun_image.planet.z_position = -1
        self.sun_image.planet.alpha = 0
        try:
           self.gs.parent_scene.add_child(self.sun_image.planet)
        except AttributeError:
           pass
        self.ship_dict['SUN'] = Sprite3D(img, width=200, height=200,
                                         distance_scale=True, scale=25000,
                                         name='sun')
        self.ship_dict['SUN'].header = self.ship_dict['CORIOLIS'].header
        self.ship_dict['SUN'].name = ('sun',)
                
    def add_axis_display(self, obj):
        # add axis to object for debug
        axis_display = WireAxes(size=100, line_width=5)
        obj = deepcopy(obj)
        rotmat = obj.rotmat
    
        axis_display.rotation.x = obj.rotx / 16  # yaw 1/16 radian
        axis_display.rotation.y = obj.roty / 8  # pitch 1/16 radian  # pitch
        axis_display.rotation.z = obj.rotz / 16  # roll
        axis_display.rotation_angles_in_world = axis_display.rotation.clone()
     
        axis_display.position_in_world = Vector3(*obj.location.to_tuple)
        
        # Rotation: store rotmat on the model so the renderer can use it
        # Convert from Vector (Elite) to Vector3 (renderer) once here
        axis_display.rotmat_world = [Vector3(*rot.to_tuple) for rot in rotmat]
        
    def clear_universe(self, all_others=False):
        # if all_others,clear all but sun, planet, station
        for i, obj in enumerate(self.gs.universe):
            if all_others and i < 3:
                continue
            obj.type = 0
            if hasattr(obj, 'model'):
               delattr(obj, 'model')
        for k in self.ship_count:
            self.ship_count[k] = 0
        self.in_battle = 0
        
    def update_model(self, ship):
        # transfer ship status to model
        if hasattr(ship, 'model'):
           ship.model.rotation.x = ship.rotx / 16  # yaw 1/16 radian
           ship.model.rotation.y = ship.roty / 16  # pitch 1/16 radian  # pitch
           ship.model.rotation.z = ship.rotz / 16  # roll
           ship.model.position.x = ship.location.x
           ship.model.position.y = ship.location.y
           ship.model.position.z = ship.location.z
           ship.model.position_in_world = ship.model.position.clone()
           ship.model.rotation_angles_in_world = ship.model.rotation.clone()
           
    def move_towards(self, loc1, loc2, initial_distance=None, velocity=None):
        """
        Move loc2 towards loc1
    
        Args:
            loc1: (x1, y1, z1) - target location (stays fixed)
            loc2: (x2, y2, z2) - location to move
            initial_distance: distance to base the step size on (computed if None)
            
    
        Returns:
            new_loc2: (x, y, z) tuple, loc2 moved towards loc1
        """
        x1, y1, z1 = loc1.to_tuple
        x2, y2, z2 = loc2.to_tuple
    
        delta = loc1 - loc2
        delta = unit_vector(loc1 - loc2)
        step = velocity * 1.5
        # Normalize direction and scale by step
        return loc2 + delta * step
                   
    def rotmat_facing(self, from_loc: Vector, to_loc: Vector, roof_hint=None, roll=0) -> list:
        """
        Build a rotmat [SIDEV, ROOFV, NOSEV] whose NOSEV axis points from
        from_loc toward to_loc.
        """
        nose = unit_vector(to_loc - from_loc)
    
        if roof_hint is None:
            roof_hint = Vector(0, 1, 0)  # world "up"
            
        side = cross_product(roof_hint, nose)
            
        # guard against nose ~parallel to roof_hint (degenerate cross product)
        side_len = side.magnitude
        if side_len < 1e-6:
            roof_hint = Vector(1, 0, 0)  # fall back to a different up-vector
            side = cross_product(roof_hint, nose)
    
        side = unit_vector(side)
        roof = cross_product(nose, side)
        if roll != 0.0:
            side, roof = self._rotate_around_axis(side, roof, nose, roll)
        return [side, roof, nose]
        
    def _rotate_around_axis(self, side: Vector, roof: Vector, axis: Vector, angle: float):
        """
        Rotate the side/roof pair around `axis` (assumed unit length) by `angle`
        radians, using Rodrigues' rotation formula. Returns (new_side, new_roof).
        """
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
    
        def rodrigues(v: Vector) -> Vector:
            # v_rot = v*cos + (axis x v)*sin + axis*(axis . v)*(1 - cos)
            cross = cross_product(axis, v)
            dot = vector_dot_product(axis, v)
            return v * cos_a + cross * sin_a + axis * dot * (1 - cos_a)
            
        return rodrigues(side), rodrigues(roof)
        
    def add_new_ship(self, ship_type, x, y, z, rotmat, rotx, rotz, roty=0) -> int:
        if rotmat is None:
            rotmat = [Vector(1, 0, 0), Vector(0, 1, 0), Vector(0, 0, 1)]
            
        ship_name = self.ship_names[ship_type]
        # find an empty slot
        for i, obj in enumerate(self.gs.universe):
            if obj.type == 0:
                obj.name = ship_name
                obj.type = ship_type
                obj.model = copy(self.ship_dict[ship_name])
                obj.location = Vector(x, y, z)
                obj.distance = math.sqrt(x*x + y*y + z*z)
                obj.rotmat = list(rotmat)
                obj.rotx = rotx
                obj.roty = roty
                obj.rotz = rotz
                obj.velocity = 0
                obj.acceleration = 0
                obj.bravery = 0
                obj.target = 0
                obj.flags = cs.INITIAL_FLAGS.get(ship_type, 0)

                if obj.type not in (cs.SHIP_PLANET, cs.SHIP_SUN):
                    ship_data = obj.model.header
                    
                    obj.energy = ship_data['Max. energy']
                    obj.missiles = ship_data['Missiles']
                    obj.max_loot = ship_data.get('Max. canisters on demise', 0)
                    self.ship_count[ship_type] = self.ship_count.get(ship_type, 0) + 1
                elif obj.type == cs.SHIP_PLANET:
                    # generate planet colour, matches charts
                    try:
                        # spin on its axis
                        obj.roty = -127
                        if cs.WIREFRAME:
                            obj.model.color = cs.COLOUR_LIST[self.gs.present_planet.colour]
                    except (AttributeError, IndexError):
                        pass
                return i
        return -1

    def remove_ship(self, index: int):
        obj = self.gs.universe[index]
        ship_type = obj.type
        if ship_type == 0:
            return

        if ship_type > 0:
            self.ship_count[ship_type] = max(0, self.ship_count.get(ship_type, 1) - 1)

        obj.type = 0
        obj.name = ''
        self.check_missiles(index)
        
        if index == STATION and not self.gs.missions.in_mission():
            self.add_new_ship(ship_type, *obj.location, None, 0, 0)

    def add_new_station(self, sx, sy, sz, rotmat):
        match self.gs.present_planet.tech:
            case 11 | 12 | 13 | 14:
                station = cs.SHIP_STATIONV
            case 9 | 10:
                station = cs.SHIP_DODEC
            case _:
                station = cs.SHIP_CORIOLIS
        self.add_new_ship(station, sx, sy, sz, rotmat, 0, -127)
        # self.add_axis_display(self.gs.universe[1])
            
    # ------ Missiles & ECM
    def check_missiles(self, index: int):
        if self.missile_target == index:
            self.missile_target = cs.MISSILE_UNARMED
            self.gs.info_message("Target Lost")
        for obj in self.gs.universe:
            if obj.type == cs.SHIP_MISSILE and obj.target == index:
                obj.flags |= cs.FLG_DEAD

    def reset_weapons(self):
        self.gs.laser_temp = 0
        self.laser_counter = 0
        self.laser = 0
        self.ecm_active = 0
        self.missile_target = cs.MISSILE_UNARMED

    def arm_missile(self):
        if self.gs.cmdr.missiles != 0 and self.missile_target == cs.MISSILE_UNARMED:
            self.missile_target = cs.MISSILE_ARMED

    def unarm_missile(self):
        self.missile_target = cs.MISSILE_UNARMED
        self.gs.sound.play_sample(cs.SND_BOOP)

    def fire_missile(self):
        if self.missile_target < 0:
            return

        rotmat = [Vector(1, 0, 0), Vector(0, 1, 0), Vector(0, 0, 1)]
        rotmat[NOSEV].z = 1.0
        rotmat[SIDEV].x = -1.0

        newship = self.add_new_ship(cs.SHIP_MISSILE, 0, -28, 14, rotmat, 0, 0)
        if newship == -1:
            self.gs.info_message("Missile Jammed")
            return

        ns = self.gs.universe[newship]
        ns.velocity = self.gs.flight_speed * 2
        ns.flags = cs.FLG_ANGRY
        ns.target = self.missile_target

        if self.gs.universe[self.missile_target].type > cs.SHIP_ROCK:
            self.gs.universe[self.missile_target].flags |= cs.FLG_ANGRY

        self.gs.cmdr.missiles -= 1
        self.missile_target = cs.MISSILE_UNARMED
        self.gs.sound.play_sample(cs.SND_MISSILE)

    def activate_ecm(self, ours: int):
        if self.ecm_active == 0:
            self.ecm_active = 32
            self.ecm_ours = ours
            self.gs.sound.play_sample(cs.SND_ECM)

    def time_ecm(self):
        if self.ecm_active != 0:
            self.ecm_active -= 1
            if self.ecm_ours:
                self.gs.space.decrease_energy(-1)

    #  ------- Laser
    
    def fire_laser(self) -> int:
        gs = self.gs
        if self.laser_counter == 0 and gs.laser_temp < 242:
            screen = gs.current_screen
            laser = {
                cs.SCR_FRONT_VIEW: gs.cmdr.front_laser,
                cs.SCR_REAR_VIEW:  gs.cmdr.rear_laser,
                cs.SCR_RIGHT_VIEW: gs.cmdr.right_laser,
                cs.SCR_LEFT_VIEW:  gs.cmdr.left_laser,
            }.get(screen, 0)
            heating = {cs.PULSE_LASER: 8,
                       cs.BEAM_LASER: 12,
                       cs.MILITARY_LASER: 24,
                       cs.MINING_LASER: 24}.get(laser, 8)
            if laser != 0:
                self.laser_counter = 0 if laser > 127 else (laser & 0xFA)
                laser &= 127
                self.laser = laser
                self.laser2 = laser
                gs.sound.play_sample(cs.SND_PULSE)
                gs.laser_temp += heating
                if gs.energy > 1:
                    gs.energy -= 1

                self.laser_x = random.randint(-2, 2) * cs.GFX_SCALEX
                self.laser_y = random.randint(-2, 2) * cs.GFX_SCALEY
                return 2
        return 0

    def cool_laser(self):
        self.laser = 0
        if self.gs.laser_temp > 0:
            self.gs.laser_temp -= 1
        if self.laser_counter > 0:
            self.laser_counter -= 1
        if self.laser_counter > 0:
            self.laser_counter -= 1

    def draw_laser_lines(self):
        gs = self.gs
        gs.parent_scene.laser_lines.alpha = 1
        gs.parent_scene.laser_lines.position = gs.FLIGHT_RECT.center() + (self.laser_y, self.laser_y)
        """
        s = gs.GFX_SCALE
        if gs.wireframe:
            for x in (32, 48, 208, 224):
                gs.gfx_draw_colour_line(x * s, gs.GFX_VIEW_BY, self.laser_x, self.laser_y, gs.WHITE)
        else:
            gs.gfx_draw_triangle(32*s, gs.GFX_VIEW_BY, self.laser_x, self.laser_y, 48*s,  gs.GFX_VIEW_BY, gs.RED)
            gs.gfx_draw_triangle(208*s, gs.GFX_VIEW_BY, self.laser_x, self.laser_y, 224*s, gs.GFX_VIEW_BY, gs.RED)
        """
    # ------ Combat helpers
    def target_object(self, key):
        # select a target from the onscreen list of universe objects
        # pass it to autopilot to orient ship to target for firing
        gs = self.gs
        obj_status = gs.obj_status
        
        no_items = obj_status.text.count('\n') + 1
        logger.debug(no_items)
        
        y_loc = int(key.split(',')[1])
        relative_y = obj_status.bbox.max_y - y_loc
        line_index = int((relative_y * no_items) / obj_status.bbox.h)
        if line_index >= no_items:
            line_index = no_items - 1
        # allow for obj_status not being in universe order
        target = gs.status_objects[line_index]
        # gs.msg.text = (f'no lines {no_items} {key} {line_index} {target.name}')
        logger.debug(f'targeting {target.name}')
        
        gs.pilot.disengage_auto_pilot()
        gs.pilot.flight_phase = 'FIND_TARGET'
        gs.pilot.target = target
        gs.pilot.engage_auto_pilot(target=True)
                        
    def in_target(self, ship_type: int, x: float, y: float, z: float) -> bool:
        # use model targetable area
        # self.gs.msg.text = f'{x=:.0f} {y=:.0f} {z=:.0f}  Error {(x*x+y*y)/1000:.0f}k'
        if z < 0:
            return False
        if ship_type == 0:
            return False
        ship_name = self.ship_names[ship_type]
        model = self.ship_dict[ship_name]
        target_area = model.header['Targetable area']
        # cr = '\n'
        # self.gs.msg_left.text = f'{cr}{(x*x + y*y)/ cs.FIRE_ACCURACY:.0f} {target_area=:.0f}'
        # logger.debug(f'{x*x + y*y} {target_area=}')
        return (x*x + y*y) / cs.FIRE_ACCURACY <= target_area

    def make_angry(self, index: int):
        obj = self.gs.universe[index]
        if obj.flags & cs.FLG_INACTIVE:
            return
        if index == STATION:
            obj.flags |= cs.FLG_ANGRY
            return
        if obj.type > cs.SHIP_ROCK:
            obj.rotx = 4
            obj.acceleration = 2
            obj.flags |= cs.FLG_ANGRY
            obj.flags |= cs.FLG_BOLD
            
    def explode_object(self, index: int):
       
        gs = self.gs
        ship = self.gs.universe[index]
        logger.debug('exploding')
        gs.cmdr.score += 1
        if (gs.cmdr.score & 255) == 0:
            gs.info_message("Right On Commander!")
        gs.sound.play_sample(cs.SND_EXPLODE)
        
        gs.missions.check_destroy(ship)
        
        ship.exploding = True
        ship.explosion_time = 0.0
        
    def _flip_location(self, world_loc):
        """
        Returns the view-space location vector, or None if behind camera.
        """
        x, y, z = world_loc.to_tuple
        match self.gs.current_screen:
            case cs.SCR_REAR_VIEW:
                x, z = -x, -z
            case cs.SCR_LEFT_VIEW:
                x, z = z, -x
            case cs.SCR_RIGHT_VIEW:
                x, z = -z, x
        return x, y, z
         
    def check_target(self, index: int):
        univ = self.gs.universe[index]
        
        if not self.in_target(univ.type, *self._flip_location(univ.location)):
            return

        if self.missile_target == cs.MISSILE_ARMED and univ.type >= 0:
            self.missile_target = index
            self.gs.info_message("Target Locked")
            self.gs.sound.play_sample(cs.SND_BEEP)

        if self.laser:
            # loot is invulnerable to fire for short time once spawned
            remaining = (getattr(univ, 'invuln_until', 0) - self.gs.mcount) % 256
            if remaining != 0 and remaining <= GRACE_TICKS:  # loot is still immune
                return
                
            x, y, z = univ.location.to_tuple
            
            self.gs.sound.play_sample(cs.SND_HIT_ENEMY)
            
            if index != STATION:
                if univ.type in (cs.SHIP_CONSTRICTOR, cs.SHIP_COUGAR):
                    if self.laser == (cs.MILITARY_LASER & 127):
                        univ.energy -= self.laser // 4
                else:
                    univ.energy -= self.laser
            # self.gs.msg.text = f'{x=:.0f} {y=:.0f} Error{(x*x+y*y):.0f} {univ.model.header["Targetable area"]}'
            # logger.debug(f'{self.ship_names[univ.type]} {univ.location}   {(x*x + y*y)= } {univ.energy=}')
            # This runs once only
            logger.debug(f'{univ.name} energy {univ.energy}')
            
            if univ.energy <= 0 and not univ.exploding:
                                
                logger.debug(f'{univ.name} exploded')
                if univ.type == cs.SHIP_ASTEROID:
                    if self.laser == (cs. MINING_LASER & 127):
                        self.launch_loot(index, cs.SHIP_ROCK, univ)
                else:
                    if univ.max_loot:
                        self.launch_loot(index, cs.SHIP_CARGO, parent=univ)
                    else:
                        self.launch_loot(index, cs.SHIP_ALLOY, parent=univ)
                self.explode_object(index)
            self.make_angry(index)
            
    # ------ Ship spawning
    def spawn_homing_object(self, ship_type: int, location, target_index: int,
                            velocity: float = 10, offset: Vector = None,
                            flyby: bool = False, max_range: float = 40000,
                            sequential: bool = False) -> int:
        """
        Spawn a new UnivObject at `location`, oriented to face the target
        (optionally offset from the target's actual position), that homes in
        every tick.
    
        offset: Vector added to the target's location each tick to compute the
                actual aim point (e.g. Vector(0, 0, 0) for a direct hit,
                or some lateral/vertical offset for a flyby past the object).
        flyby:  if True, once the seeker gets within HOMING_HIT_DISTANCE of the
                aim point it does NOT explode/impact — it keeps flying in a
                straight line along its current heading until it exceeds
                max_range, at which point it's removed.
                
        sequential: If True, ships attack one at a time rather than all at once.
                    This means that they can be targetted and engaged before
                    attacking. If ship is flying by, next ship can start
                    attacking.
                    
                    
        max_range: distance from origin at which a flyby seeker is auto-removed.
        """
        target = self.gs.universe[target_index]
        offset = offset or Vector(0, 0, 0)
        aim_point = target.location + offset
    
        rotmat = self.rotmat_facing(location, aim_point)
        
        newship = self.add_new_ship(ship_type,
                                    location.x, location.y, location.z,
                                    rotmat, 16, 16)
            
        if newship == -1:
            return -1
    
        ns = self.gs.universe[newship]
        ns.sync_model()
        ns.velocity = 0 if sequential != 0 else velocity
        ns.acceleration = 0
        ns.flags = cs.FLG_SEEKER
        ns.target = target_index
        ns.original_target = target_index
        ns.bravery = 113
        # New per-seeker state — offset targeting / flyby behaviour
        ns.homing_offset = offset
        ns.flyby = flyby
        ns.max_range = max_range
        ns.roll = 0
        ns.roll_rate = 16
        ns.flyby_locked = False       # becomes True once past closest approach
        # ns.flyby_heading = None       # frozen unit vector once locked
        return newship
                    
    def home_on_target(self, index: int):
        """
        Per-tick homing behaviour for an autonomous seeker created by
        spawn_homing_object().
        Currently it is intended for STATION targetting.
        Note that seeker can change its target
        """
        seeker = self.gs.universe[index]
        if seeker.target == cs.SHIP_PLAYER:
            return
        if seeker.target != seeker.original_target:
            return
        target = self.gs.universe[seeker.target]
        
        if seeker.flags & (cs.FLG_DEAD | cs.FLG_INACTIVE):
            return
        if seeker.location.magnitude > getattr(seeker, 'max_range', 40000):
            self.remove_ship(index)
            return
        # Once a flyby seeker has locked its heading (passed closest approach)
        # it is ignored here, continues on its merry way
        if getattr(seeker, 'flyby_locked', False):
            return
        if seeker.velocity == 0:
            return  # waiting its turn — literally inert
        
        if target.type == 0:
            # not homing any more
            return
        offset = getattr(seeker, 'homing_offset', Vector(0, 0, 0))
        vec = target.location + offset - seeker.location
        target_vec = target.location - seeker.location
        # Impact check — delete self, damage target
        if vec.magnitude < HOMING_HIT_DISTANCE and not seeker.flyby_locked:
            if getattr(seeker, 'flyby', False):
                # Passed the aim point without colliding
                # continue straight until out of range.
                seeker.flyby_locked = True
               
            else:
                # real impact
                seeker.exploding = True
                seeker.flags |= cs.FLG_DEAD
                self.gs.msg.text = f'{seeker.name} impacted'
                self.gs.sound.play_sample(cs.SND_EXPLODE)
                
                target.energy -= self.HOMING_DAMAGE
                self.gs.msg_left_lower.text = f'{target.name} energy = {target.energy:.0f}'
                if target.energy < 64:
                    self.gs.info_message('target.name} Critical!')
                if target.energy <= 0 and not target.exploding:
                    self.explode_object(seeker.target)
            return
            
        if abs(target_vec.magnitude) < MIN_FIRING_DISTANCE / 2 and seeker.flyby:
            self.strafe(seeker, target)
            
        # Steer nose towards target
        seeker.roll = (seeker.roll + seeker.roll_rate * 0.001) % (2 * math.pi)
        seeker.rotmat = self.rotmat_facing(seeker.location, target.location + offset, roll=seeker.roll)
    
        seeker.sync_model()
        
    def strafe(self, seeker, target):
        """ allow an NPC to fire at target even if not pointed directly. Dont change flight direction """
        if self.gs.mcount % 30 == 0:
                        
            self.ship_fire(seeker, target)
            self.gs.sound.play_sample(cs.SND_HIT_ENEMY)
            self.gs.msg_left_lower.text = f'{seeker.name} firing {cs.CR}at {target.name}{cs.CR}{target.name} energy = {target.energy:.0f}'
            laser_strength = self.ship_list[seeker.type].laser_strength / 2
            target.energy -= laser_strength
            if target.energy < 64:
                self.gs.info_message(f'{target.name} Critical!', msg_count=37)
            if target.energy <= 0 and not target.exploding:
                self.explode_object(seeker.target)
                self.gs.message_count = 0
                self.gs.info_message(f'{target.name} Destroyed, mission failed!', msg_count=100)
                                         
    def launch_enemy(self, index: int, ship_type: int, flags: int, bravery: int):
        src = self.gs.universe[index]
        newship = self.add_new_ship(ship_type,
                                    *src.location.to_tuple,
                                    src.rotmat, src.rotx, src.rotz)
        # logger.error(f'{newship} {self.gs.universe[newship]}')               
        if newship == -1:
            return

        ns = self.gs.universe[newship]
        if index != STATION:
            ns.velocity = 32
            ns.location += ns.rotmat[NOSEV] * 2
        else:
            ns.velocity = 10
        ns.flags |= flags
        ns.rotz = (ns.rotz // 2) * 2
        ns.bravery = bravery

        if ship_type in (cs.SHIP_CARGO, cs.SHIP_ALLOY, cs.SHIP_ROCK):
            ns.rotz = ((rand255() * 2) & 255) - 128
            ns.rotx = ((rand255() * 2) & 255) - 128
            ns.velocity = rand255() & 15
        if ship_type == cs.SHIP_THARGON:
            ns.target = self._select_target(index, ns)
        return ns
        
    def launch_loot(self, index: int, loot: int, parent: UnivObject):
        """ up to 3 rocks, up to 3 plates, max_loot cannisters if
        max_loot < 3 
        Track who it belonged to to allow special treatment in mission scooping"""
        if loot == cs.SHIP_ROCK:
            cnt = rand_no(3)
        elif loot == cs.SHIP_ALLOY:
           cnt = rand_no(1)
        elif loot == cs.SHIP_CARGO:
            cnt = getattr(parent, 'special_cargo', None)
            if cnt is None:
                if rand_no(1):
                    return
                cnt = max(parent.max_loot, 2)            
        else:
            cnt = 0
            
        for _ in range(cnt):
            ns = self.launch_enemy(index, loot, 0, 0)
            if ns:
                setattr(ns, 'parent', parent.name)
                ns.invuln_until = (self.gs.mcount + GRACE_TICKS) % 256  # ~8 ticks grace period
                
    def launch_shuttle(self):
        gs = self.gs
        if (self.ship_count.get(cs.SHIP_TRANSPORTER, 0) != 0
                or self.ship_count.get(cs.SHIP_SHUTTLE, 0) != 0
                or rand255() < 253 or gs.auto_pilot or gs.on_final_approach):
            return
        ship_type = cs.SHIP_SHUTTLE if rand255() & 1 else cs.SHIP_TRANSPORTER
        self.launch_enemy(1, ship_type, cs.FLG_HAS_ECM | cs.FLG_FLY_TO_PLANET, 113)
    
    # ------ AI / Tactics

    # Faction groupings used by _select_target to decide who is willing to
    # shoot at whom. This is deliberately simple: police hunt anything
    # flagged hostile/bold (pirates, bounty hunters gone rogue), Thargoids
    # are hostile to everyone including each other's victims, and ordinary
    # hostiles (pirates/hunters) prefer the player but will engage a police
    # ship that is actively hunting them if the player isn't a viable target.
    def _is_police(self, obj) -> bool:
        return bool(obj.flags & cs.FLG_POLICE)

    def _is_thargoid(self, obj) -> bool:
        return obj.type in (cs.SHIP_THARGOID, cs.SHIP_THARGON)

    def _is_hostile_npc(self, obj) -> bool:
        # a non-police, non-Thargoid ship currently marked as angry, i.e.
        # a pirate/bounty-hunter type that is willing to fight
        return bool(obj.flags & cs.FLG_ANGRY) and not self._is_police(obj) and not self._is_thargoid(obj)

    def _nearest(self, index: int, ship: UnivObject, candidate_fn) -> int | None:
        best = None
        best_dist = None
        for i, other in enumerate(self.gs.universe):
            # wont shoot at station
            if i == index:   # or other.type == 0:
                continue
            if not candidate_fn(other):
                continue
            dvec = Vector(other.location.x - ship.location.x,
                          other.location.y - ship.location.y,
                          other.location.z - ship.location.z)
            dist = math.sqrt(dvec.x*dvec.x + dvec.y*dvec.y + dvec.z*dvec.z)
            if dist < MIN_FIRING_DISTANCE and (best_dist is None or dist < best_dist):
                best, best_dist = i, dist
        return best

    def _select_target(self, index: int, ship: UnivObject) -> int:
        """
        Decide who `ship` should be aiming at this tick: the player (0) or
        another universe object (its index). Ships continue to prefer the
        player — this only introduces ship-vs-ship targeting for the cases
        where NPC-on-NPC conflict makes sense (police vs pirates/hunters,
        Thargoids vs anyone). Returns the chosen target index, which is
        also written to ship.target.
        """
        if self._is_police(ship):
            # Police prefer to hunt down a nearby hostile NPC; if none is
            # in range they fall back to the player as before.
            best = self._nearest(index, ship, self._is_hostile_npc)
            ship.target = best if best is not None else cs.SHIP_PLAYER
            return ship.target

        if self._is_thargoid(ship):
            # Thargoids are hostile to everything; prefer the nearest
            # non-Thargoid ship, otherwise the player.
            best = self._nearest(index, ship, lambda o: not self._is_thargoid(o))
            ship.target = best if best is not None else cs.SHIP_PLAYER
            return ship.target

        # Ordinary hostiles (pirates, bounty hunters): go after the player,
        # as in the original game, unless a police ship is actively hunting
        # them at close range and the player is out of reach.
        if ship.distance >= MIN_FIRING_DISTANCE:
            best = self._nearest(index, ship,
                                 lambda o: self._is_police(o) and o.target == index)
            if best is not None:
                ship.target = best
                return ship.target

        ship.target = cs.SHIP_PLAYER
        return cs.SHIP_PLAYER

    def tactics(self, index: int):
        gs = self.gs
        ship = self.gs.universe[index]
        flags = ship.flags
    
        if ship.type in (cs.SHIP_PLANET, cs.SHIP_SUN):
            return
        if flags & (cs.FLG_DEAD | cs.FLG_INACTIVE):
            return
        if ship.type == cs.SHIP_MISSILE:
            if flags & cs.FLG_ANGRY:
                self.missile_tactics(index)
            return
        if index == STATION:
            self._tactics_station(index, flags)
            return
        if ship.type == cs.SHIP_HERMIT:
            self._tactics_hermit(index, ship)
            return
        if flags & cs.FLG_SEEKER:
            self.home_on_target(index)
            
        # If the ship is not hostile, fly to and from  the planet and station
        if not (flags & cs.FLG_ANGRY):
            if flags & (cs.FLG_FLY_TO_PLANET | cs.FLG_FLY_TO_STATION):
                gs.pilot.auto_pilot_ship(index)
            return
            
        # every 8 /60ths
        if ((index ^ gs.mcount) & 15) != 0:
            return
        
        # Recharge the ship's energy banks by 1
        try:
            if ship.energy < self.ship_list[ship.type].energy:
                ship.energy += 1
        except KeyError:
            pass
                
        # If this is a lone Thargon without a mothership, set it adrift aimlessly
        if ship.type == cs.SHIP_THARGON and self.ship_count.get(cs.SHIP_THARGOID, 0) == 0:
            ship.flags = 0
            ship.velocity //= 2
            return
        # If this is a trader, 80% of the time we're done, 20% of the time the
        # trader performs the same checks as the bounty hunter
        if flags & cs.FLG_SLOW and rand255() > 50:
            return
        #  If this is a bounty hunter (or one of the 20% of traders) and we have been
        # really bad (i.e. a fugitive or serious offender), the ship becomes hostile
        #  (if it isn't already)
        if flags & cs.FLG_POLICE and gs.cmdr.legal_status >= 64:
            flags |= cs.FLG_ANGRY
            ship.flags = flags
        if (flags & cs.FLG_POLICE) and (flags & cs.FLG_ANGRY):
            self.flash_police_lights(ship)
        
        if self.gs.cloaking_device_active:
            return

        # Decide whether this ship is engaging the player or another ship.
        self._select_target(index, ship)

        self._tactics_attack(index, ship, flags)
        
    def flash_police_lights(self, ship):
       # flash red/blue on Viper
       if self.gs.mcount % 32 < 4:
           colors = [('red', 'cornflowerblue'), ('cornflowerblue', 'red')]
           color1, color2 = colors[self.light]
           ship.model.face_colors[3] = color1
           ship.model.face_colors[4] = color2
           ship.model.face_colors[6] = color2
           
           self.light = not self.light
       
    def track_object(self, ship: UnivObject, direction: float, nvec: Vector):
        rat = 3
        rat2 = 0.111
        dir_ = vector_dot_product(nvec, ship.rotmat[ROOFV])

        if direction < self._cos(149.4):
            ship.rotx = 7 if dir_ < 0 else -7
            ship.rotz = 0
            return

        ship.rotx = 0
        if abs(dir_) * 2 >= rat2:
            ship.rotx = rat if dir_ < 0 else -rat

        if abs(ship.rotz) < 16:
            dir_ = vector_dot_product(nvec, ship.rotmat[SIDEV])
            ship.rotz = 0
            if abs(dir_) * 2 > rat2:
                ship.rotz = rat if dir_ < 0 else -rat
                if ship.rotx < 0:
                    ship.rotz = -ship.rotz
            
    def missile_tactics(self, index):
        missile = self.gs.universe[index]
        gs = self.gs
        # If E.C.M. is active, destroy the missile
        if self.ecm_active:
            gs.sound.play_sample(cs.SND_EXPLODE)
            missile.flags |= cs.FLG_DEAD
            return
        #  If the missile is hostile towards us, then check how close it is. If it
        # hasn't reached us, jump to part 3 so it can streak towards us, otherwise
        # we've been hit, so process a large amount of damage to our ship
        if missile.target == 0:
            if missile.distance < 256:
                missile.flags |= cs.FLG_DEAD
                gs.sound.play_sample(cs.SND_EXPLODE)
                gs.space.damage_ship(250, missile.location.z >= 0.0)
                return
            vec = Vector(missile.location.x, missile.location.y, missile.location.z)
        else:
            # Otherwise see how close the missile is to its target. If it has not yet
            # reached its target, give the target a chance to activate its E.C.M. if it
            # has one, otherwise jump to TA19 with K3 set to the vector from the target
            # to the missile
            target = self.gs.universe[missile.target]
            vec = Vector(
                missile.location.x - target.location.x,
                missile.location.y - target.location.y,
                missile.location.z - target.location.z,
            )
            if abs(vec.x) < 256 and abs(vec.y) < 256 and abs(vec.z) < 256:
                missile.flags |= cs.FLG_DEAD
                if missile.target != STATION:
                    self.explode_object(missile.target)
                else:
                    gs.sound.play_sample(cs.SND_EXPLODE)
                return

            if rand255() < 16 and (target.flags & cs.FLG_HAS_ECM):
                self.activate_ecm(0)
                return

        nvec = unit_vector(vec)
        direction = vector_dot_product(nvec, missile.rotmat[NOSEV])
        nvec.x, nvec.y, nvec.z = -nvec.x, -nvec.y, -nvec.z
        direction = -direction

        self.track_object(missile, direction, nvec)

        if direction <= self._cos(99.6):
            missile.acceleration = -2
            return
        if direction >= self._cos(77.1):
            missile.acceleration = 3
            return
        if missile.velocity < 6:
            missile.acceleration = 3
        elif rand255() >= 200:
            missile.acceleration = -2
            
    def ship_fire(self, ship, target=None):
        gs = self.gs
        gfx = self.gs.gfx
        cam = gs.camera
        fl = cam.focal_length
        # could change laser colour deoending on ship.
        colours = {0: cs.WHITE,  # clean
                   cs.FLG_POLICE: cs.YELLOW,  # tracked
                   cs.FLG_ALIEN: cs.PURPLE,  # thargoid
                   cs.FLG_BOLD | cs.FLG_ANGRY: cs.ORANGE}  # pirate/bounty hunter
             
        for k, v in colours.items():
            if ship.flags & k:
                colour = v
                break
            else:
                colour = cs.ORANGE
        # Draw laser line from ship toward its target. When target is None
        # (or the player), that's the origin, as before. When target is
        # another UnivObject, aim the line at its on-screen position instead.
        # Project ship position to screen
        
        cam_pos = gs.renderer._to_camera(ship.model.position_in_world, cam)
        screen_pt = gs.renderer._project(cam_pos, fl, cam, clip_to_screen=False)
        if True:  # ship.location.z > 0:
            scale = fl / ship.location.z
            if screen_pt:
               sx, sy = screen_pt
            else:
                sx = gfx.X_CENTRE + ship.location.x * scale
                sy = gfx.Y_CENTRE - ship.location.y * scale
            
            if target is not None and target.type != 0:
                # Aim the laser line at the target ship's projected screen
                # position rather than always the origin.
                # Convert both world points to camera space
                cam_pos1 = gs.renderer._to_camera(target.model.position_in_world, cam)
                cam_pos2 = gs.renderer._to_camera(ship.model.position_in_world, cam)
                
                # Project the line segment with built-in near-plane intersection clipping
                line_screen_pts = gs.renderer._project_line(cam_pos1, cam_pos2, fl, cam)
                
                if line_screen_pts is not None:
                    pt1, pt2 = line_screen_pts
                    # Draw line from pt1 to pt2 on your canvas/display
                    gfx.draw_line(*pt1, *pt2,
                                  colour=colour, width=3)
                    return
                """
                if True: #target.location.z > 0:
                     scale = fl / target.location.z
                     if screen_pt1:
                        ex, ey = screen_pt1
                     else:
                         ex = gfx.X_CENTRE + target.location.x * scale
                         ey = gfx.Y_CENTRE - target.location.y * scale"""
            else:
                # tx, ty, tz = target.location.to_tuple
                # if tz > 0:
                #    tscale = fl / tz
                #    ex_screen = gfx.X_CENTRE + tx * tscale
                #    ey_screen = gfx.Y_LOW - ty * tscale
                # else:
                ex_screen = gfx.X_CENTRE
                ey_screen = gfx.Y_LOW
                
                gfx.draw_line(sx, sy, ex_screen, ey_screen,
                              colour=colour, width=3)
                return

            # Nose vector points toward us (negative z), so laser fires from
            # ship toward origin — extend in nosev direction to screen edge
            nose = ship.rotmat[NOSEV]
            # A large step along the nose direction in view space
            far = 10000.0
            ex = ship.location.x + nose.x * far
            ey = ship.location.y + nose.y * far
            ez = ship.location.z + nose.z * far
            if ez > 0:
                escale = fl / ez
                ex_screen = gfx.X_CENTRE + ex * escale
                ey_screen = gfx.Y_LOW - ey * escale
            else:
                # Line passes through or behind camera — aim at screen centre
                ex_screen = gfx.X_CENTRE
                ey_screen = gfx.Y_LOW
            # logger.debug(f'{ez=:.0f} {sx=:.0f} {sy=:.0f} {ex_screen=:.0f} {ey_screen=:.0f}')
            gfx.draw_line(sx, sy, ex_screen, ey_screen,
                          colour=colour, width=3)
                                                            
    def _tactics_station(self, index, flags):
        # If this is the space station and it is hostile, consider spawning a cop
        # (6.2% chance, up to a maximum of seven) and we're done
        gs = self.gs
        if index == STATION:
            if gs.pilot.auto_pilot_active and gs.space.safe_mode:
                return  # don't spawn during autopilot - it's just rude
    
            rnd_ = rand255()
            if rnd_ < 240:
                return
    
            if flags & cs.FLG_ANGRY:
                if self.ship_count.get(cs.SHIP_VIPER, 0) >= 4:
                    return
                self.launch_enemy(index, cs.SHIP_VIPER, cs.FLG_ANGRY | cs.FLG_HAS_ECM, 113)
            else:
                self.launch_shuttle()
                
    def _tactics_hermit(self, index, ship):
        # If this is a rock hermit, consider spawning (22% chance) a highly
        # aggressive and hostile Sidewinder, Mamba, Krait, Adder or Gecko (equal
        # odds of each type) and we're done
        if rand255() > 200:
            self.launch_enemy(index, cs.SHIP_SIDEWINDER + (rand255() & 3),
                              cs.FLG_ANGRY | cs.FLG_HAS_ECM, 113)
            ship.flags |= cs.FLG_INACTIVE
            
    def _tactics_attack(self, index, ship, flags):
        # Ship is angry — attack!
        
        #  If the ship is hostile, and a pirate, and we are within the space station
        # safe zone, stop the pirate from attacking by removing all its aggression
        
        if self.gs.space.safe_mode and not (flags & cs.FLG_BOLD):
            ship.bravery = 0
        # If this is an Anaconda, consider spawning (22% chance) a Worm (61% of the
        # time) or a Sidewinder (39% of the time)
        if ship.type == cs.SHIP_ANACONDA and rand255() > 200:
            spawn = cs.SHIP_WORM if rand255() > 100 else cs.SHIP_SIDEWINDER
            self.launch_enemy(index, spawn, cs.FLG_ANGRY | cs.FLG_HAS_ECM, 113)
            return
        # Rarely (2.5% chance) roll the ship by a noticeable amount
        if rand255() >= 250:
            ship.rotz = rand255() | 0x68
            if ship.rotz > 127:
                ship.rotz = -(ship.rotz & 127)
        # If the ship has at least half its energy banks full, jump to part 6 to
        # consider firing the lasers
        maxeng = self.ship_list[ship.type].energy
        energy = ship.energy
        if energy < maxeng // 2:
            if self._tactics_escape_pod(index, ship, energy, maxeng):
                return
            if self._tactics_fire_missile(index, ship):
                return
        
        self._tactics_combat(index, ship, flags)
        
    def _tactics_escape_pod(self, index, ship, energy, maxeng):
        # If the ship is into the last 1/8th of its energy, and this ship type has
        # an escape pod fitted, then rarely (10% chance) the ship launches an escape
        # pod and is left drifting in space
        if energy < maxeng // 8 and rand255() > 230 and ship.type != cs.SHIP_THARGOID:
            ship.flags &= ~cs.FLG_ANGRY
            ship.flags |= cs.FLG_INACTIVE
            self.launch_enemy(index, cs.SHIP_ESCAPE_CAPSULE, 0, 126)
            return True
        return False
        
    def _tactics_fire_missile(self, index, ship) -> bool:
        
        # Randomly decide whether to fire a missile (or, in the case of Thargons,
        # release a Thargoid), and if we do, we're done
        gs = self.gs
        if (ship.missiles != 0 and self.ecm_active == 0
                and ship.missiles >= (rand255() & 31)
                and not ship.has_fired):
            ship.missiles -= 1
            ship.has_fired = True
            if ship.type == cs.SHIP_THARGOID:
                self.launch_enemy(index, cs.SHIP_THARGON, cs.FLG_ANGRY, ship.bravery)
            else:
                self.launch_enemy(index, cs.SHIP_MISSILE, cs.FLG_ANGRY, 126)
                gs.info_message("INCOMING MISSILE")
            return True
        return False
        
    def _target_vector_and_distance(self, ship, target_index):
        """
        Vector from `ship` toward its current target, and the distance
        between them. For the player (target_index == -96), `ship.location`
        is already player-relative.
        """
        if target_index == cs.SHIP_PLAYER:
            return ship.location, ship.distance

        target = self.gs.universe[target_index]
        vec = target.location - ship.location
        return vec, vec.magnitude

    def _tactics_combat(self, index, ship, flags):
        cnt2 = self._cos(77.1)
        target_index = ship.target
        rel_loc, distance = self._target_vector_and_distance(ship, target_index)
        nvec = unit_vector(rel_loc)
        direction = vector_dot_product(nvec, ship.rotmat[NOSEV])
    
        if (distance < MIN_FIRING_DISTANCE and direction >= self._cos(33.6)
                and self.ship_list[ship.type].laser_strength != 0):
            self._tactics_fire_at_target(index, ship, target_index, rel_loc, distance, direction, nvec)
            return
    
        attacking = self._tactics_should_attack(ship, rel_loc, direction, nvec)
        if attacking is not None:
            attacking_flag, direction = attacking
        else:
            attacking_flag = False
    
        self.track_object(self.gs.universe[index], direction, nvec)
    
        if attacking_flag and distance < 2048:
            if direction >= cnt2:
                ship.acceleration = -1
                return
            if ship.velocity < 6:
                ship.acceleration = 3
            elif rand255() >= 200:
                ship.acceleration = -1
            return
    
        if direction <= self._cos(99.6):
            ship.acceleration = -1
        elif direction >= cnt2:
            ship.acceleration = 3
        elif ship.velocity < 6:
            ship.acceleration = 3
        elif rand255() >= 200:
            ship.acceleration = -1
                 
    def _tactics_fire_at_target(self, index, ship, target_index, rel_loc, distance, direction, nvec):
        # Calculate the dot product of the ship's nose vector (i.e. the direction it
        # is pointing) with the vector between it and its target. This value will
        # help us work out whether the attacking ship is pointing towards its
        # target, and therefore whether it can hit it with its lasers.
        gs = self.gs
        CR = '\n'
        firing_at_player = (target_index == cs.SHIP_PLAYER)
        target_obj = None if firing_at_player else self.gs.universe[target_index]
        target_name = 'you' if firing_at_player else target_obj.name
        # If the ship is not pointing at its target, skip to the next part
        if direction >= self._cos(23.5):
            ship.flags |= cs.FLG_FIRING | cs.FLG_HOSTILE
            if ship.target == cs.SHIP_PLAYER:
                target_str = 'player'
            else:
                target_str = self.gs.universe[ship.target].name
            self.gs.msg_left.text = f'{ship.name} firing {CR}at {target_str}'
            # gs.msg_left.text = f'{ship.name} firing '
            logger.debug(gs.msg_left.text)
            self.ship_fire(ship, target_obj)
        # If the target is in the ship's crosshairs, register damage, slow down
        # the attacking ship, and make the appropriate noise.
        if direction >= self._cos(13.6):
            gs.msg_left.text = f'{ship.name} firing {CR}accurate at {target_name}'
            logger.debug(gs.msg_left.text)
            self.ship_fire(ship, target_obj)
            laser_strength = self.ship_list[ship.type].laser_strength
            if firing_at_player:
                gs.space.damage_ship(laser_strength, ship.location.z >= 0.0)
                if ((ship.location.z >= 0.0 and gs.front_shield == 0)
                        or (ship.location.z < 0.0 and gs.aft_shield == 0)):
                    gs.sound.play_sample(cs.SND_INCOMMING_FIRE_2)
                else:
                    gs.sound.play_sample(cs.SND_INCOMMING_FIRE_1)
            else:
                target = self.gs.universe[target_index]
                gs.sound.play_sample(cs.SND_HIT_ENEMY)
                if target.type in (cs.SHIP_CONSTRICTOR, cs.SHIP_COUGAR):
                    if laser_strength == (cs.MILITARY_LASER & 127):
                        target.energy -= laser_strength // 4
                else:
                    target.energy -= laser_strength
                if target.energy <= 0 and not target.exploding:
                    if hasattr(target, 'max_loot'):
                        self.launch_loot(target_index, cs.SHIP_CARGO, parent=target)
                    else:
                        self.launch_loot(target_index, cs.SHIP_ALLOY, parent=target)
                    self.explode_object(target_index)
                self.make_angry(target_index)
            ship.acceleration -= 1
        else:
            nvec.x, nvec.y, nvec.z = -nvec.x, -nvec.y, -nvec.z
            direction = -direction
            self.track_object(self.gs.universe[index], direction, nvec)
    
        if abs(rel_loc.z) < 768:
            ship.rotx = rand255() & 0x87
            if ship.rotx > 127:
                ship.rotx = -(ship.rotx & 127)
            ship.acceleration = 3
            return
        ship.acceleration = -1 if distance < 8192 else 3

    def _tactics_should_attack(self, ship, rel_loc, direction, nvec):
        if (abs(rel_loc.z) >= 768
                or abs(rel_loc.x) >= 512
                or abs(rel_loc.y) >= 512):
            if ship.bravery > (rand255() & 127):
                nvec.x, nvec.y, nvec.z = -nvec.x, -nvec.y, -nvec.z
                return True, -direction
        return False, direction
                             
    # ------ Random encounter spawning
    def create_other_ship(self, ship_type: int) -> int:
        z = 12000
        x = 1000 + random.randint(0, 8191)
        y = 1000 + random.randint(0, 8191)
        if rand255() > 127:
            x = -x
        if rand255() > 127:
            y = -y
        return self.add_new_ship(ship_type, x, y, z, None, 0, 0)

    def create_thargoid(self):
        newship = self.create_other_ship(cs.SHIP_THARGOID)
        if newship != -1:
            self.gs.universe[newship].flags = cs.FLG_ANGRY | cs.FLG_HAS_ECM
            self.gs.universe[newship].bravery = 113
            if rand255() > 64:
                self.launch_enemy(newship, cs.SHIP_THARGON, cs.FLG_ANGRY | cs.FLG_HAS_ECM, 96)

    def create_cougar(self):
        if self.ship_count.get(cs.SHIP_COUGAR, 0) != 0:
            return
        newship = self.create_other_ship(cs.SHIP_COUGAR)
        if newship != -1:
            self.gs.universe[newship].flags = cs.FLG_HAS_ECM
            self.gs.universe[newship].bravery = 121
            self.gs.universe[newship].velocity = 18

    def create_trader(self):
        ship_type = cs.SHIP_COBRA3 + (rand255() & 3)
        newship = self.create_other_ship(ship_type)
        if newship != -1:
            obj = self.gs.universe[newship]
            obj.rotmat[NOSEV].z = -1.0
            obj.rotz = rand255() & 7
            rnd = rand255()
            obj.velocity = (rnd & 31) | 16
            obj.bravery = rnd // 2
            if rnd & 1:
                obj.flags |= cs.FLG_HAS_ECM

    def create_lone_hunter(self, ship_type=None):
        if not ship_type:
            ship_type = self.gs.missions.spawn_ship()
        if ship_type is None:
            rnd = rand255()
            ship_type = cs.SHIP_COBRA3_LONE + (rnd & 3) + (1 if rnd > 127 else 0)

        newship = self.create_other_ship(ship_type)
        if newship != -1:
            self.gs.universe[newship].flags = cs.FLG_ANGRY
            if rand255() > 200 or ship_type == cs.SHIP_CONSTRICTOR:
                self.gs.universe[newship].flags |= cs.FLG_HAS_ECM
            self.gs.universe[newship].bravery = ((rand255() * 2) | 64) & 127
            self.in_battle = 1

    def check_for_asteroids(self):
        if rand255() >= 35 or self.ship_count.get(cs.SHIP_ASTEROID, 0) >= 3:
            return
        ship_type = cs.SHIP_HERMIT if rand255() > 253 else cs.SHIP_ASTEROID
        newship = self.create_other_ship(ship_type)
        if newship != -1:
            self.gs.universe[newship].velocity = 8
            self.gs.universe[newship].rotz = -127 if rand255() > 127 else 127
            self.gs.universe[newship].rotx = 16

    def check_for_cops(self):
        gs = self.gs
        offense = gs.trade.carrying_contraband() * 2
        if self.ship_count.get(cs.SHIP_VIPER, 0) == 0:
            offense |= gs.cmdr.legal_status
        if rand255() >= offense:
            return
        newship = self.create_other_ship(cs.SHIP_VIPER)
        if newship != -1:
            self.gs.universe[newship].flags = cs.FLG_ANGRY
            if rand255() > 245:
                self.gs.universe[newship].flags |= cs.FLG_HAS_ECM
            self.gs.universe[newship].bravery = ((rand255() * 2) | 64) & 127

    def check_for_others(self):
        """spawn other ship """
        gov = self.gs.current_planet_data.government
        rnd = rand255()
        # skip if not anarchy
        if gov != 0 and (rnd >= 90 or (rnd & 7) < gov):
            return
        if rand255() < 100:
            self.create_lone_hunter()
            return

        z = 12000
        x = 1000 + random.randint(0, 8191)
        y = 1000 + random.randint(0, 8191)
        if rand255() > 127:
            x = -x
        if rand255() > 127:
            y = -y

        rnd = rand255() & 3
        for _ in range(rnd + 1):
            ship_type = cs.SHIP_SIDEWINDER + (rand255() & rand255() & 7)
            newship = self.add_new_ship(ship_type, x, y, z, None, 0, 0)
            if newship != -1:
                self.gs.universe[newship].flags = cs.FLG_ANGRY
                if rand255() > 245:
                    self.gs.universe[newship].flags |= cs.FLG_HAS_ECM
                self.gs.universe[newship].bravery = ((rand255() * 2) | 64) & 127
                self.in_battle += 1

    def random_encounter(self):
        # logger.error(f'{self.gs.space.safe_mode=} {self.gs.missions.in_mission()}')
        # logger.error(f'{Mission(self.gs.cmdr.mission)} {self.gs.cmdr.galaxy_number} {self.gs.present_planet.name}')
        if (self.gs.space.safe_mode
                and not self.gs.missions.in_mission()):
            return
        
        if rand255() == 136:
            if (int(self.gs.universe[PLANET].location.z) & 0x3e) != 0:
                self.create_thargoid()
            else:
                self.create_cougar()
            return

        if (rand255() & 7) == 0:
            self.create_trader()
            return
        ship_type = self.gs.missions.spawn_ship()
        if ship_type == cs.SHIP_THARGOID:
            self.create_thargoid()
        elif ship_type == cs.SHIP_CONSTRICTOR:
            self.create_lone_hunter(ship_type)
                  
        self.check_for_asteroids()
        self.check_for_cops()

        if self.ship_count.get(cs.SHIP_VIPER, 0):
            return
        if self.in_battle:
            return
        
        self.check_for_others()
    
    # ---- Player escape

    def abandon_ship(self):
        gs = self.gs
        cmdr = gs.cmdr
        cmdr.escape_pod = 0
        cmdr.legal_status = 0
        cmdr.fuel = gs.myship.max_fuel
        for i in range(len(gs.trade.STOCK_MARKET)):
            cmdr.current_cargo[i] = 0
        gs.sound.play_sample(cs.SND_DOCK)
        gs.space.dock_player()
        gs.break_mode = 'docking'
        gs.current_screen = cs.SCR_BREAK_PATTERN
        
        
if __name__ == '__main__':
   # Example usage:
   game_engine = Swat(None)
   # game_engine.create_lone_hunter()
   # print(f"Ships in battle: {game_engine.in_battle}")
