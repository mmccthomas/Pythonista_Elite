import math
import random
# from scene import Rect
# from ui import Path
from copy import deepcopy
from types import SimpleNamespace
import colorsys
import constants as cs
from vector import Vector, unit_vector, vector_dot_product
from wireframe_3d_2 import load_wireframes_from_json, WireframeObject, WireSphere
from wireframe_3d_2 import Vector3, Sprite3D, WireAxes
from dataclasses import dataclass, field
from planet_generator import Planet, AlienPlanet
import logging
logger = logging.getLogger(__name__)
NOSEV = 2
ROOFV = 1
SIDEV = 0
PLANET = 0
STATION = 1
MIN_FIRING_DISTANCE = 8192


def rand255():
   return random.randint(0, 255)

      
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
    
    # ----- Universe management
    def generate_landscape(self):
        # create a new alien planet with correct colour
        # use AlienPlanet to change images/planet_texture.png
        # then change Sprite3D image
        colour = cs.COLOUR_LIST[self.gs.present_planet.colour]
        colour = colorsys.rgb_to_hsv(*colour)[0]
        # cloud_threshold = 1.0  # 0.8 +  0.1* (self.gs.present_planet.c % 3)  # lower is more cloud
        # sea_level = (1 + self.gs.present_planet.b % 8) / 10
        # blob_size = 3  # 1 + self.gs.present_planet.d % 2
        
        img = AlienPlanet(400, 400, colour, seed=self.gs.present_planet.a,
                          # cloud_threshold=cloud_threshold,
                          # sea_level=sea_level,
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
    
    def generate_sun(self):
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
                                image_path='images/sun_texture400.png',
                                light_dir=(0, 0, 1), soft=0.08)
        img = self.sun_image.planet
        self.sun_image.color = cs.RED
        self.sun_image.planet.z_position = -1
        self.sun_image.planet.alpha = 0
        self.gs.parent_scene.add_child(self.sun_image.planet)
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
        for i, obj in enumerate(self.universe):
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
           
    def add_new_ship(self, ship_type, x, y, z, rotmat, rotx, rotz) -> int:
        if rotmat is None:
            rotmat = [Vector(1, 0, 0), Vector(0, 1, 0), Vector(0, 0, 1)]
            
        ship_name = self.ship_names[ship_type]
        for i, obj in enumerate(self.universe):
            if obj.type == 0:
                obj.name = ship_name
                obj.type = ship_type
                obj.model = self.ship_dict[ship_name]
                obj.location = Vector(x, y, z)
                obj.distance = math.sqrt(x*x + y*y + z*z)
                obj.rotmat = list(rotmat)
                obj.rotx = rotx
                obj.roty = 0
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
        obj = self.universe[index]
        ship_type = obj.type
        if ship_type == 0:
            return

        if ship_type > 0:
            self.ship_count[ship_type] = max(0, self.ship_count.get(ship_type, 1) - 1)

        obj.type = 0
        self.check_missiles(index)

        if ship_type in (cs.SHIP_CORIOLIS, cs.SHIP_DODEC):
            px = obj.location.x
            py = obj.location.y
            pz = obj.location.z
            py = (int(py) & 0xFFFF) | 0x60000
            self.add_new_ship(cs.SHIP_SUN, px, py, pz, None, 0, 0)

    def add_new_station(self, sx, sy, sz, rotmat):
        station = cs.SHIP_DODEC if self.gs.current_planet_data.tech_level >= 10 else cs.SHIP_CORIOLIS
        self.add_new_ship(station, sx, sy, sz, rotmat, 0, -127)
        # self.add_axis_display(self.universe[1])
            
    # ------ Missiles & ECM
    def check_missiles(self, index: int):
        if self.missile_target == index:
            self.missile_target = cs.MISSILE_UNARMED
            self.gs.info_message("Target Lost")
        for obj in self.universe:
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

        ns = self.universe[newship]
        ns.velocity = self.gs.flight_speed * 2
        ns.flags = cs.FLG_ANGRY
        ns.target = self.missile_target

        if self.universe[self.missile_target].type > cs.SHIP_ROCK:
            self.universe[self.missile_target].flags |= cs.FLG_ANGRY

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

            if laser != 0:
                self.laser_counter = 0 if laser > 127 else (laser & 0xFA)
                laser &= 127
                self.laser = laser
                self.laser2 = laser

                gs.sound.play_sample(cs.SND_PULSE)
                gs.laser_temp += 8
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
        obj = self.universe[index]
        if obj.flags & cs.FLG_INACTIVE:
            return
        if index == STATION:
            obj.flags |= cs.FLG_ANGRY
            return
        if obj.type > cs.SHIP_ROCK:
            obj.rotx = 4
            obj.acceleration = 2
            obj.flags |= cs.FLG_ANGRY

    def explode_object(self, index: int):
        gs = self.gs
        ship = self.universe[index]
        # logger.debug('exploding')
        gs.cmdr.score += 1
        if (gs.cmdr.score & 255) == 0:
            gs.info_message("Right On Commander!")
        gs.sound.play_sample(cs.SND_EXPLODE)
        # ship.flags |= cs.FLG_REMOVE
        if ship.type == cs.SHIP_CONSTRICTOR:
            gs.cmdr.mission = 2  # MISSION_1_COMPLETE
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
         
    def check_target(self, index: int, flip: UnivObject):
        univ = self.universe[index]
        
        if not self.in_target(univ.type, *self._flip_location(flip.location)):
            return

        if self.missile_target == cs.MISSILE_ARMED and univ.type >= 0:
            self.missile_target = index
            self.gs.info_message("Target Locked")
            self.gs.sound.play_sample(cs.SND_BEEP)

        if self.laser:
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
            if univ.energy <= 0 and not univ.exploding:
                if univ.type == cs.SHIP_ASTEROID:
                    if self.laser == (cs. MINING_LASER & 127):
                        self.launch_loot(index, cs.SHIP_ROCK, univ)
                else:
                    
                    self.launch_loot(index, cs.SHIP_ALLOY, univ)
                    self.launch_loot(index, cs.SHIP_CARGO, univ)
                self.explode_object(index)
            self.make_angry(index)
    
    # ------ Ship spawning
    
    def launch_enemy(self, index: int, ship_type: int, flags: int, bravery: int):
        src = self.universe[index]
        newship = self.add_new_ship(ship_type,
                                    src.location.x, src.location.y, src.location.z,
                                    src.rotmat, src.rotx, src.rotz)
        if newship == -1:
            return

        ns = self.universe[newship]
        if index != STATION:
            ns.velocity = 32
            ns.location.x += ns.rotmat[NOSEV].x * 2
            ns.location.y += ns.rotmat[NOSEV].y * 2
            ns.location.z += ns.rotmat[NOSEV].z * 2
        else:
            ns.velocity = 10
        ns.flags |= flags
        ns.rotz = (ns.rotz // 2) * 2
        ns.bravery = bravery

        if ship_type in (cs.SHIP_CARGO, cs.SHIP_ALLOY, cs.SHIP_ROCK):
            ns.rotz = ((rand255() * 2) & 255) - 128
            ns.rotx = ((rand255() * 2) & 255) - 128
            ns.velocity = rand255() & 15
        return ns
        
    def launch_loot(self, index: int, loot: int, parent: UnivObject):
        if loot == cs.SHIP_ROCK:
            cnt = rand255() & 3
        elif loot == cs.SHIP_ALLOY:
           cnt = rand255() & 3
        else:
            cnt = rand255()
            if cnt >= 128:
                return
            try:
                cnt &= self.ship_list[self.universe[index].type].max_loot
                cnt &= 15
            except AttributeError:
                # no max_loot
                cnt &= 3

        for _ in range(cnt):
            ns = self.launch_enemy(index, loot, 0, 0)
            if ns:
                setattr(ns, 'parent', parent.name)

    def launch_shuttle(self):
        gs = self.gs
        if (self.ship_count.get(cs.SHIP_TRANSPORTER, 0) != 0
                or self.ship_count.get(cs.SHIP_SHUTTLE, 0) != 0
                or rand255() < 253 or gs.auto_pilot or gs.on_final_approach):
            return
        ship_type = cs.SHIP_SHUTTLE if rand255() & 1 else cs.SHIP_TRANSPORTER
        self.launch_enemy(1, ship_type, cs.FLG_HAS_ECM | cs.FLG_FLY_TO_PLANET, 113)
    
    # ------ AI / Tactics
    def tactics(self, index: int):
        gs = self.gs
        ship = self.universe[index]
        flags = ship.flags
    
        if ship.type in (cs.SHIP_PLANET, cs.SHIP_SUN):
            return
        if flags & (cs.FLG_DEAD | cs.FLG_INACTIVE):
            return
        if ship.type == cs.SHIP_MISSILE:
            if flags & cs.FLG_ANGRY:
                self.missile_tactics(index)
            return
        # every 8 /60ths
        if ((index ^ gs.mcount) & 15) != 0:
            return
    
        if index == STATION:
            self._tactics_station(index, flags)
            return
        if ship.type == cs.SHIP_HERMIT:
            self._tactics_hermit(index, ship)
            return
        # Recharge the ship's energy banks by 1
        if ship.energy < self.ship_list[ship.type].energy:
            ship.energy += 1
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
        # If the ship is not hostile, fly to and from  the planet and station
        if not (flags & cs.FLG_ANGRY):
            if flags & (cs.FLG_FLY_TO_PLANET | cs.FLG_FLY_TO_STATION):
                gs.pilot.auto_pilot_ship(index)
            return
    
        self._tactics_attack(index, ship, flags)
        
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
        missile = self.universe[index]
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
            target = self.universe[missile.target]
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
            
    def ship_fire(self, ship):
        gs = self.gs
        gfx = self.gs.gfx
        cam = gs.camera
        fl = cam.focal_length
        # Draw laser line from ship toward player (origin)
        # Project ship position to screen
        
        cam_pos = gs.renderer._to_camera(ship.model.position_in_world, cam)
        screen_pt = gs.renderer._project(cam_pos, fl, cam)
        if ship.location.z > 0:
            scale = fl / ship.location.z
            if screen_pt:
               sx, sy = screen_pt
            else:
                sx = gfx.X_CENTRE + ship.location.x * scale
                sy = gfx.Y_CENTRE - ship.location.y * scale
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
                          colour=cs.WHITE, width=2)
                                                            
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
        
    def _tactics_combat(self, index, ship, flags):
        cnt2 = self._cos(77.1)
        nvec = unit_vector(ship.location)
        direction = vector_dot_product(nvec, ship.rotmat[NOSEV])
    
        if (ship.distance < MIN_FIRING_DISTANCE and direction >= self._cos(33.6)
                and self.ship_list[ship.type].laser_strength != 0):
            self._tactics_fire_at_player(index, ship, direction, nvec)
            return
    
        attacking = self._tactics_should_attack(ship, direction, nvec)
        if attacking is not None:
            attacking_flag, direction = attacking
        else:
            attacking_flag = False
    
        self.track_object(self.universe[index], direction, nvec)
    
        if attacking_flag and ship.distance < 2048:
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
                 
    def _tactics_fire_at_player(self, index, ship,  direction, nvec):
        # Calculate the dot product of the ship's nose vector (i.e. the direction it
        # is pointing) with the vector between us and the ship. This value will help
        # us work out later on whether the enemy ship is pointing towards us, and
        # therefore whether it can hit us with its lasers.
        gs = self.gs
        # If the ship is not pointing at us, skip to the next part
        if direction >= self._cos(23.5):
            ship.flags |= cs.FLG_FIRING | cs.FLG_HOSTILE
            gs.msg_left.text = f'{ship.name} firing '
            logger.debug(gs.msg_left.text)
            self.ship_fire(ship)
        # If we are in the ship's crosshairs, register some damage to our ship, slow
        # down the attacking ship, make the noise of us being hit by laser fire
        if direction >= self._cos(13.6):
            gs.msg_left.text = f'{ship.name} firing accurate '
            logger.debug(gs.msg_left.text)
            self.ship_fire(ship)
            gs.space.damage_ship(self.ship_list[ship.type].laser_strength,
                                 ship.location.z >= 0.0)
            ship.acceleration -= 1
            if ((ship.location.z >= 0.0 and gs.front_shield == 0)
                    or (ship.location.z < 0.0 and gs.aft_shield == 0)):
                gs.sound.play_sample(cs.SND_INCOMMING_FIRE_2)
            else:
                gs.sound.play_sample(cs.SND_INCOMMING_FIRE_1)
        else:
            nvec.x, nvec.y, nvec.z = -nvec.x, -nvec.y, -nvec.z
            direction = -direction
            self.track_object(self.universe[index], direction, nvec)
    
        if abs(ship.location.z) < 768:
            ship.rotx = rand255() & 0x87
            if ship.rotx > 127:
                ship.rotx = -(ship.rotx & 127)
            ship.acceleration = 3
            return
        ship.acceleration = -1 if ship.distance < 8192 else 3

    def _tactics_should_attack(self, ship, direction, nvec):
        if (abs(ship.location.z) >= 768
                or abs(ship.location.x) >= 512
                or abs(ship.location.y) >= 512):
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
            self.universe[newship].flags = cs.FLG_ANGRY | cs.FLG_HAS_ECM
            self.universe[newship].bravery = 113
            if rand255() > 64:
                self.launch_enemy(newship, cs.SHIP_THARGON, cs.FLG_ANGRY | cs.FLG_HAS_ECM, 96)

    def create_cougar(self):
        if self.ship_count.get(cs.SHIP_COUGAR, 0) != 0:
            return
        newship = self.create_other_ship(cs.SHIP_COUGAR)
        if newship != -1:
            self.universe[newship].flags = cs.FLG_HAS_ECM
            self.universe[newship].bravery = 121
            self.universe[newship].velocity = 18

    def create_trader(self):
        ship_type = cs.SHIP_COBRA3 + (rand255() & 3)
        newship = self.create_other_ship(ship_type)
        if newship != -1:
            obj = self.universe[newship]
            obj.rotmat[NOSEV].z = -1.0
            obj.rotz = rand255() & 7
            rnd = rand255()
            obj.velocity = (rnd & 31) | 16
            obj.bravery = rnd // 2
            if rnd & 1:
                obj.flags |= cs.FLG_HAS_ECM

    def create_lone_hunter(self):
        gs = self.gs
        cmdr = gs.cmdr
        if (cmdr.mission == 1 and cmdr.galaxy_number == 1
                and gs.present_planet.x == 144 and gs.present_planet.y == 33
                and self.ship_count.get(cs.SHIP_CONSTRICTOR, 0) == 0):
            ship_type = cs.SHIP_CONSTRICTOR
        else:
            rnd = rand255()
            ship_type = cs.SHIP_COBRA3_LONE + (rnd & 3) + (1 if rnd > 127 else 0)

        newship = self.create_other_ship(ship_type)
        if newship != -1:
            self.universe[newship].flags = cs.FLG_ANGRY
            if rand255() > 200 or ship_type == cs.SHIP_CONSTRICTOR:
                self.universe[newship].flags |= cs.FLG_HAS_ECM
            self.universe[newship].bravery = ((rand255() * 2) | 64) & 127
            self.in_battle = 1

    def check_for_asteroids(self):
        if rand255() >= 35 or self.ship_count.get(cs.SHIP_ASTEROID, 0) >= 3:
            return
        ship_type = cs.SHIP_HERMIT if rand255() > 253 else cs.SHIP_ASTEROID
        newship = self.create_other_ship(ship_type)
        if newship != -1:
            self.universe[newship].velocity = 8
            self.universe[newship].rotz = -127 if rand255() > 127 else 127
            self.universe[newship].rotx = 16

    def check_for_cops(self):
        gs = self.gs
        offense = gs.trade.carrying_contraband() * 2
        if self.ship_count.get(cs.SHIP_VIPER, 0) == 0:
            offense |= gs.cmdr.legal_status
        if rand255() >= offense:
            return
        newship = self.create_other_ship(cs.SHIP_VIPER)
        if newship != -1:
            self.universe[newship].flags = cs.FLG_ANGRY
            if rand255() > 245:
                self.universe[newship].flags |= cs.FLG_HAS_ECM
            self.universe[newship].bravery = ((rand255() * 2) | 64) & 127

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
                self.universe[newship].flags = cs.FLG_ANGRY
                if rand255() > 245:
                    self.universe[newship].flags |= cs.FLG_HAS_ECM
                self.universe[newship].bravery = ((rand255() * 2) | 64) & 127
                self.in_battle += 1

    def random_encounter(self):
        if self.gs.space.safe_mode:
            return

        if rand255() == 136:
            if (int(self.universe[PLANET].location.z) & 0x3e) != 0:
                self.create_thargoid()
            else:
                self.create_cougar()
            return

        if (rand255() & 7) == 0:
            self.create_trader()
            return

        self.check_for_asteroids()
        self.check_for_cops()

        if self.ship_count.get(cs.SHIP_VIPER, 0):
            return
        if self.in_battle:
            return
        if self.gs.cmdr.mission == 5 and rand255() >= 200:
            self.create_thargoid()

        self.check_for_others()
    
    # ---- Player escape

    def abandon_ship(self):
        gs = self.gs
        cmdr = gs.cmdr
        cmdr.escape_pod = 0
        cmdr.legal_status = 0
        cmdr.fuel = gs.myship.max_fuel
        for i in range(gs.NO_OF_STOCK_ITEMS):
            cmdr.current_cargo[i] = 0
        gs.sound.play_sample(cs.SND_DOCK)
        gs.space.dock_player()
        gs.current_screen = cs.SCR_BREAK_PATTERN
        
        
if __name__ == '__main__':
   # Example usage:
   game_engine = Swat(None)
   # game_engine.create_lone_hunter()
   # print(f"Ships in battle: {game_engine.in_battle}")
   
   
   

