import math
import random
# from scene import Rect
# from ui import Path
from types import SimpleNamespace
import constants as cs
from vector import Vector, unit_vector, vector_dot_product
from wireframe_3d import load_wireframes_from_json, WireframeObject, WireSphere
from dataclasses import dataclass, field


def rand255():
   return random.randint(0, 255)


@dataclass
class UnivObject:
    type: int = 0
    name: str = ''
    model: WireframeObject = field(default_factory=WireframeObject)
    location: Vector = field(default_factory=Vector)
    rotmat: list = field(default_factory=lambda: [Vector(), Vector(), Vector()])
    rotx: int = 0
    rotz: int = 0
    velocity: float = 0
    acceleration: float = 0
    bravery: int = 0
    target: int = 0
    flags: int = 0
    energy: int = 0
    missiles: int = 0
    distance: float = 0.0


Ship = UnivObject


class Swat:
    """Special Weapons And Tactics — space combat manager """
 
    def __init__(self, game_state):
        self.gs = game_state          # holds cmdr, ship_list, gfx, snd, etc.

        self.universe: list[UnivObject] = [UnivObject() for _ in range(cs.MAX_UNIV_OBJECTS)]
        self.ship_count: dict[int, int] = {i: 0 for i in range(cs.NO_OF_SHIPS + 1)}
        
        ships = load_wireframes_from_json('files/Elite_ships.json')
        self.ship_dict = {ship.name[0]: ship for ship in ships}
        # add planet and sun
        self.ship_dict['SUN'] = WireSphere(radius=5, lat_lines=16, lon_lines=16,
                                           color=cs.YELLOW,
                                           )
        self.ship_dict['SUN'].header = self.ship_dict['CORIOLIS'].header
        self.ship_dict['SUN'].name = ('SUN',)
        self.ship_dict['PLANET'] = WireSphere(radius=1, lat_lines=6, lon_lines=8,
                                              color=cs.GREEN)
        self.ship_dict['PLANET'].header = self.ship_dict['CORIOLIS'].header
        self.ship_dict['PLANET'].name = ('PLANET',)
        self.ship_names = {v: k for k, v in cs.SHIP_DICT.items()}
        # constuct ship_list dictionary containing operational properties of each
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
          if v > 0:
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
    def clear_universe(self):
        for obj in self.universe:
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
           ship.model.rotation.y = 0  # pitch
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
                        obj.model.color = cs.COLOUR_LIST[self.gs.docked_planet.colour]
                    except (AttributeError, IndexError):
                        pass
                return i
        return -1

    def remove_ship(self, un: int):
        obj = self.universe[un]
        ship_type = obj.type
        if ship_type == 0:
            return

        if ship_type > 0:
            self.ship_count[ship_type] = max(0, self.ship_count.get(ship_type, 1) - 1)

        obj.type = 0
        self.check_missiles(un)

        if ship_type in (cs.SHIP_CORIOLIS, cs.SHIP_DODEC):
            px = obj.location.x
            py = obj.location.y
            pz = obj.location.z
            py = (int(py) & 0xFFFF) | 0x60000
            self.add_new_ship(cs.SHIP_SUN, px, py, pz, None, 0, 0)

    def add_new_station(self, sx, sy, sz, rotmat):
        station = cs.SHIP_DODEC if self.gs.current_planet_data.tech_level >= 10 else cs.SHIP_CORIOLIS
        self.universe[1].type = 0
        self.add_new_ship(station, sx, sy, sz, rotmat, 0, -127)
    
    # ------ Missiles & ECM

    def check_missiles(self, un: int):
        if self.missile_target == un:
            self.missile_target = cs.MISSILE_UNARMED
            self.gs.info_message("Target Lost")
        for obj in self.universe:
            if obj.type == cs.SHIP_MISSILE and obj.target == un:
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
        rotmat[2].z = 1.0
        rotmat[0].x = -1.0

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
    
    def in_target(self, ship_type: int, x: float, y: float, z: float) -> bool:
        # use model targetable area
        if z < 0:
            return False
        ship_name = self.ship_names[ship_type]
        model = self.ship_dict[ship_name]
        target_area = model.header['Targetable area']
        return (x*x + y*y) <= target_area

    def make_angry(self, un: int):
        obj = self.universe[un]
        if obj.flags & cs.FLG_INACTIVE:
            return
        if obj.type in (cs.SHIP_CORIOLIS, cs.SHIP_DODEC):
            obj.flags |= cs.FLG_ANGRY
            return
        if obj.type > cs.SHIP_ROCK:
            obj.rotx = 4
            obj.acceleration = 2
            obj.flags |= cs.FLG_ANGRY

    def explode_object(self, un: int):
        gs = self.gs
        gs.cmdr.score += 1
        if (gs.cmdr.score & 255) == 0:
            gs.info_message("Right On Commander!")
        gs.sound.play_sample(cs.SND_EXPLODE)
        self.universe[un].flags |= cs.FLG_DEAD
        if self.universe[un].type == cs.SHIP_CONSTRICTOR:
            gs.cmdr.mission = 2

    def check_target(self, un: int, flip: UnivObject):
        univ = self.universe[un]
        if not self.in_target(univ.type, flip.location.x, flip.location.y, flip.location.z):
            return

        if self.missile_target == cs.MISSILE_ARMED and univ.type >= 0:
            self.missile_target = un
            self.gs.info_message("Target Locked")
            self.gs.sound.play_sample(cs.SND_BEEP)

        if self.laser:
            self.gs.sound.play_sample(cs.SND_HIT_ENEMY)

            if univ.type not in (cs.SHIP_CORIOLIS, cs.SHIP_DODEC):
                if univ.type in (cs.SHIP_CONSTRICTOR, cs.SHIP_COUGAR):
                    if self.laser == (cs.MILITARY_LASER & 127):
                        univ.energy -= self.laser // 4
                else:
                    univ.energy -= self.laser

            if univ.energy <= 0:
                self.explode_object(un)
                if univ.type == cs.SHIP_ASTEROID:
                    if self.laser == (cs. MINING_LASER & 127):
                        self.launch_loot(un, cs.SHIP_ROCK)
                else:
                    self.launch_loot(un, cs.SHIP_ALLOY)
                    self.launch_loot(un, cs.SHIP_CARGO)

            self.make_angry(un)
    
    # ------ Ship spawning
    
    def launch_enemy(self, un: int, ship_type: int, flags: int, bravery: int):
        src = self.universe[un]
        newship = self.add_new_ship(ship_type,
                                    src.location.x, src.location.y, src.location.z,
                                    src.rotmat, src.rotx, src.rotz)
        if newship == -1:
            return

        ns = self.universe[newship]
        if src.type in (cs.SHIP_CORIOLIS, cs.SHIP_DODEC):
            ns.velocity = 32
            ns.location.x += ns.rotmat[2].x * 2
            ns.location.y += ns.rotmat[2].y * 2
            ns.location.z += ns.rotmat[2].z * 2

        ns.flags |= flags
        ns.rotz = (ns.rotz // 2) * 2
        ns.bravery = bravery

        if ship_type in (cs.SHIP_CARGO, cs.SHIP_ALLOY, cs.SHIP_ROCK):
            ns.rotz = ((rand255() * 2) & 255) - 128
            ns.rotx = ((rand255() * 2) & 255) - 128
            ns.velocity = rand255() & 15

    def launch_loot(self, un: int, loot: int):
        if loot == cs.SHIP_ROCK:
            cnt = rand255() & 3
        else:
            cnt = rand255()
            if cnt >= 128:
                return
            cnt &= self.ship_list[self.universe[un].type].max_loot
            cnt &= 15

        for _ in range(cnt):
            self.launch_enemy(un, loot, 0, 0)

    def launch_shuttle(self):
        gs = self.gs
        if (self.ship_count.get(cs.SHIP_TRANSPORTER, 0) != 0
                or self.ship_count.get(cs.SHIP_SHUTTLE, 0) != 0
                or rand255() < 253 or gs.auto_pilot):
            return
        ship_type = cs.SHIP_SHUTTLE if rand255() & 1 else cs.SHIP_TRANSPORTER
        self.launch_enemy(1, ship_type, cs.FLG_HAS_ECM | cs.FLG_FLY_TO_PLANET, 113)
    
    # ------ AI / Tactics
    
    def track_object(self, ship: UnivObject, direction: float, nvec: Vector):
        rat = 3
        rat2 = 0.111
        dir_ = vector_dot_product(nvec, ship.rotmat[1])

        if direction < -0.861:
            ship.rotx = 7 if dir_ < 0 else -7
            ship.rotz = 0
            return

        ship.rotx = 0
        if abs(dir_) * 2 >= rat2:
            ship.rotx = rat if dir_ < 0 else -rat

        if abs(ship.rotz) < 16:
            dir_ = vector_dot_product(nvec, ship.rotmat[0])
            ship.rotz = 0
            if abs(dir_) * 2 > rat2:
                ship.rotz = rat if dir_ < 0 else -rat
                if ship.rotx < 0:
                    ship.rotz = -ship.rotz

    def missile_tactics(self, un: int):
        missile = self.universe[un]
        gs = self.gs
        cnt2 = 0.223

        if self.ecm_active:
            gs.sound.play_sample(cs.SND_EXPLODE)
            missile.flags |= cs.FLG_DEAD
            return

        if missile.target == 0:
            if missile.distance < 256:
                missile.flags |= cs.FLG_DEAD
                gs.sound.play_sample(cs.SND_EXPLODE)
                gs.space.damage_ship(250, missile.location.z >= 0.0)
                return
            vec = Vector(missile.location.x, missile.location.y, missile.location.z)
        else:
            target = self.universe[missile.target]
            vec = Vector(
                missile.location.x - target.location.x,
                missile.location.y - target.location.y,
                missile.location.z - target.location.z,
            )
            if abs(vec.x) < 256 and abs(vec.y) < 256 and abs(vec.z) < 256:
                missile.flags |= cs.FLG_DEAD
                if target.type not in (cs.SHIP_CORIOLIS, cs.SHIP_DODEC):
                    self.explode_object(missile.target)
                else:
                    gs.sound.play_sample(cs.SND_EXPLODE)
                return

            if rand255() < 16 and (target.flags & cs.FLG_HAS_ECM):
                self.activate_ecm(0)
                return

        nvec = unit_vector(vec)
        direction = vector_dot_product(nvec, missile.rotmat[2])
        nvec.x, nvec.y, nvec.z = -nvec.x, -nvec.y, -nvec.z
        direction = -direction

        self.track_object(missile, direction, nvec)

        if direction <= -0.167:
            missile.acceleration = -2
            return
        if direction >= cnt2:
            missile.acceleration = 3
            return
        if missile.velocity < 6:
            missile.acceleration = 3
        elif rand255() >= 200:
            missile.acceleration = -2

    def tactics(self, un: int):
        gs = self.gs
        ship = self.universe[un]
        ship_type = ship.type
        flags = ship.flags
        cnt2 = 0.223

        if ship_type in (cs.SHIP_PLANET, cs.SHIP_SUN):
            return
        if flags & cs.FLG_DEAD:
            return
        if flags & cs.FLG_INACTIVE:
            return

        if ship_type == cs.SHIP_MISSILE:
            if flags & cs.FLG_ANGRY:
                self.missile_tactics(un)
            return

        if ((un ^ gs.mcount) & 7) != 0:
            return

        if ship_type in (cs.SHIP_CORIOLIS, cs.SHIP_DODEC):
            if flags & cs.FLG_ANGRY:
                if (random.randint(0, 255)) < 240:
                    return
                if self.ship_count.get(cs.SHIP_VIPER, 0) >= 4:
                    return
                self.launch_enemy(un, cs.SHIP_VIPER, cs.FLG_ANGRY | cs.FLG_HAS_ECM, 113)
            else:
                self.launch_shuttle()
            return

        if ship_type == cs.SHIP_HERMIT:
            if rand255() > 200:
                self.launch_enemy(un, cs.SHIP_SIDEWINDER + (rand255() & 3),
                                  cs.FLG_ANGRY | cs.FLG_HAS_ECM, 113)
                ship.flags |= cs.FLG_INACTIVE
            return

        if ship.energy < self.ship_list[ship_type].energy:
            ship.energy += 1

        if ship_type == cs.SHIP_THARGLET and self.ship_count.get(cs.SHIP_THARGOID, 0) == 0:
            ship.flags = 0
            ship.velocity //= 2
            return

        if flags & cs.FLG_SLOW:
            if rand255() > 50:
                return

        if flags & cs.FLG_POLICE:
            if gs.cmdr.legal_status >= 64:
                flags |= cs.FLG_ANGRY
                ship.flags = flags

        if not (flags & cs.FLG_ANGRY):
            if (flags & cs.FLG_FLY_TO_PLANET) or (flags & cs.FLG_FLY_TO_STATION):
                gs.pilot.auto_pilot_ship(self.universe[un])
            return

        # Ship is angry — attack!
        if self.ship_count.get(cs.SHIP_CORIOLIS, 0) or self.ship_count.get(cs.SHIP_DODEC, 0):
            if not (flags & cs.FLG_BOLD):
                ship.bravery = 0

        if ship_type == cs.SHIP_ANACONDA:
            if rand255() > 200:
                spawn = cs.SHIP_WORM if rand255() > 100 else cs.SHIP_SIDEWINDER
                self.launch_enemy(un, spawn, cs.FLG_ANGRY | cs.FLG_HAS_ECM, 113)
                return

        if rand255() >= 250:
            ship.rotz = rand255() | 0x68
            if ship.rotz > 127:
                ship.rotz = -(ship.rotz & 127)

        maxeng = self.ship_list[ship_type].energy
        energy = ship.energy

        if energy < maxeng // 2:
            if energy < maxeng // 8 and rand255() > 230 and ship_type != cs.SHIP_THARGOID:
                ship.flags &= ~cs.FLG_ANGRY
                ship.flags |= cs.FLG_INACTIVE
                self.launch_enemy(un, cs.SHIP_ESCAPE_CAPSULE, 0, 126)
                return

            if (ship.missiles != 0 and self.ecm_active == 0
                    and ship.missiles >= (rand255() & 31)):
                ship.missiles -= 1
                if ship_type == cs.SHIP_THARGOID:
                    self.launch_enemy(un, cs.SHIP_THARGLET, cs.FLG_ANGRY, ship.bravery)
                else:
                    self.launch_enemy(un, cs.SHIP_MISSILE, cs.FLG_ANGRY, 126)
                    gs.info_message("INCOMING MISSILE")
                return

        nvec = unit_vector(ship.location)
        direction = vector_dot_product(nvec, ship.rotmat[2])

        if (ship.distance < 8192 and direction <= -0.833
                and self.ship_list[ship_type].laser_strength != 0):
            if direction <= -0.917:
                ship.flags |= cs.FLG_FIRING | cs.FLG_HOSTILE
            if direction <= -0.972:
                gs.space.damage_ship(self.ship_list[ship_type].laser_strength,
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
                self.track_object(self.universe[un], direction, nvec)

            if abs(ship.location.z) < 768:
                ship.rotx = rand255() & 0x87
                if ship.rotx > 127:
                    ship.rotx = -(ship.rotx & 127)
                ship.acceleration = 3
                return

            ship.acceleration = -1 if ship.distance < 8192 else 3
            return

        attacking = False
        if (abs(ship.location.z) >= 768
                or abs(ship.location.x) >= 512
                or abs(ship.location.y) >= 512):
            if ship.bravery > (rand255() & 127):
                attacking = True
                nvec.x, nvec.y, nvec.z = -nvec.x, -nvec.y, -nvec.z
                direction = -direction

        self.track_object(self.universe[un], direction, nvec)

        if attacking and ship.distance < 2048:
            if direction >= cnt2:
                ship.acceleration = -1
                return
            if ship.velocity < 6:
                ship.acceleration = 3
            elif rand255() >= 200:
                ship.acceleration = -1
            return

        if direction <= -0.167:
            ship.acceleration = -1
        elif direction >= cnt2:
            ship.acceleration = 3
        elif ship.velocity < 6:
            ship.acceleration = 3
        elif rand255() >= 200:
            ship.acceleration = -1
    
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
                self.launch_enemy(newship, cs.SHIP_THARGLET, cs.FLG_ANGRY | cs.FLG_HAS_ECM, 96)

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
            obj.rotmat[2].z = -1.0
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
                and gs.docked_planet.d == 144 and gs.docked_planet.b == 33
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
        gov = self.gs.current_planet_data.government
        rnd = rand255()
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
        if self.ship_count.get(cs.SHIP_CORIOLIS, 0) or self.ship_count.get(cs.SHIP_DODEC, 0):
            return

        if rand255() == 136:
            if (int(self.universe[0].location.z) & 0x3e) != 0:
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
   
   
   

