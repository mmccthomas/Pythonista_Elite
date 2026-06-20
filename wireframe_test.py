from wireframe_3d import Vector3, WireframeObject, Camera, Renderer, GetEliteShips
from wireframe_3d import load_wireframes_from_json, Sprite3D, WireSphere
from random import choice, uniform
import random
import math
import ui
import scene
from change_screensize import get_screen_size
# ---------------------------------------------------------------------------
# SpaceFlight demo
# ---------------------------------------------------------------------------
SPACE_X = 5000.0
SPACE_Y = 4000.0
SPACE_Z = 3000.0
# ---------Colour constants
GREEN = (0, 1, 0, 1)
RED = (1, 0, 0, 1)
YELLOW = (1, 1, 0, 1)
WHITE = (1, 1, 1, 1)
CYAN = (0, 1, 1, 1)
BLUE = (0, 0, 1, 1)
MIN_SHIP_SPEED = 0.1
MAX_SHIP_SPEED = 1.0
ROLL_RATE = math.radians(0.2)
PITCH_RATE = math.radians(0.15)
THRUST_STEP = 0.5
MAX_THRUST = 5
MIN_THRUST = 0
SHIP_COLORS = [GREEN, RED, YELLOW, WHITE, CYAN, BLUE]
BTN_W = 80
BTN_H = 60
BTN_PAD = 8
BTN_Y = 20
W, H = get_screen_size()


class MovingShip:
    def __init__(self, obj: WireframeObject, bounds):
        self.obj = obj
        bx, by, bz = bounds
        obj.position = Vector3(uniform(0, bx), uniform(0, by), uniform(0, bz))
        obj.position_in_world = obj.position.clone()
        speed = uniform(MIN_SHIP_SPEED, MAX_SHIP_SPEED)
        dx, dy, dz = uniform(-1,1), uniform(-1,1), uniform(-1, 1)
        length = math.sqrt(dx*dx+dy*dy+dz*dz) or 1.0
        self.velocity = Vector3(dx/length*speed, dy/length*speed, dz/length*speed)
        self.spin_y   = 0
        self.spin_z   = uniform(-0.02, 0.02)
        self._bounds  = bounds

    def update(self):
        obj = self.obj
        obj.position.x += self.velocity.x
        obj.position.y += self.velocity.y
        obj.position.z += self.velocity.z
        bx, by, bz = self._bounds
        obj.position.x %= bx
        obj.position.y %= by
        obj.position.z %= bz
        obj.position_in_world = obj.position.clone()
        obj.rotation.y += self.spin_y
        obj.rotation.z += self.spin_z
        obj.rotation_angles_in_world = obj.rotation.clone()


class TouchButton:
    def __init__(self, label, x, y, w, h, color=(0.2, 0.8, 0.4, 0.85)):
        self.label   = label
        self.rect    = scene.Rect(x, y, w, h)
        self.color   = color
        self.pressed = False

    def contains(self, pt):
        r = self.rect
        return r.x <= pt.x <= r.x + r.w and r.y <= pt.y <= r.y + r.h

    def draw(self):
        r = self.rect
        if self.pressed:
            scene.fill(self.color[0]*1.4, self.color[1]*1.4,
                       self.color[2]*1.4, self.color[3])
        else:
            scene.fill(*self.color)
        scene.stroke(1, 1, 1, 0.6)
        scene.stroke_weight(1.5)
        scene.rect(r.x, r.y, r.w, r.h)
        scene.fill(1, 1, 1, 1)
        scene.text(self.label, font_name='Courier', font_size=13,
                   x=r.x + r.w/2, y=r.y + r.h/2, alignment=5)


class SpaceFlight(scene.Scene):

    def setup(self):
        self.bounds = (SPACE_X, SPACE_Y, SPACE_Z)
        start_pos   = Vector3(uniform(0,SPACE_X), uniform(0,SPACE_Y), uniform(0,SPACE_Z))
        self.camera = Camera(
            position=start_pos,
            yaw=uniform(0, math.tau),
            pitch=uniform(-0.4, 0.4),
            fov=math.radians(70),
            z_near=-50,
            z_far=4000.0,
        )
        self.status = scene.LabelNode(
            '', font=('Avenir Next', 20), color='white',
            position=(0, self.size.h-100), anchor_point=(0,0), parent=self
        )
        self.spd_status = scene.LabelNode(
            '', font=('Avenir Next', 20), color='white',
            position=(0, self.size.h-120), anchor_point=(0,0), parent=self
        )
        self.thrust    = 0.0
        self.roll_angle = 0.0

        self.renderer = Renderer(depth_sort=True, backface_cull=False)
        self.renderer.viewport = scene.Rect(0 , 0, W, H)

        raw_objects = self._load_ships()[:5]
        self.moving_ships = []
        for obj in raw_objects:
            obj.scale   = uniform(0.4, 1.8)
            obj.color   = choice(SHIP_COLORS)
            obj.visible = True
            self.moving_ships.append(MovingShip(obj, self.bounds))

        sunpos = Vector3(SPACE_X/2 + 500, SPACE_Y/2, 500)
        sun = Sprite3D('images/Fire2.png', width=100, height=100, distance_scale=True)
        sun.position_in_world = sunpos.clone()
        self.static_objects = [sun]

        self._build_buttons()
        self._touch_map = {}
        self.hud_roll_indicator()

    def hud_roll_indicator(self):
        cx, cy = self.size.w/2, self.size.h/2
        r = 12
        path = ui.Path()
        path.move_to(-r, 0)
        path.line_to( r, 0)
        path.oval(-6, -6, 12, 12)
        scene.ShapeNode(path, stroke_color=(0.3,1.0,0.3,0.7),
                        position=(cx,cy), z_position=5, parent=self)

        hr   = 40
        path = ui.Path()
        path.line_width = 2
        path.move_to(-hr, 0)
        path.line_to( hr, 0)
        path.move_to(0, 0)
        path.line_to(0, 10)
        self.roll_indicator = scene.ShapeNode(
            path, stroke_color=(1.0,1.0,0.1),
            alpha=0.4, position=(cx,cy), z_position=5, parent=self
        )
        path = ui.Path()
        for ref in (-math.pi/4, math.pi/4):
            a  = ref
            tx = math.cos(a) * (hr + 6)
            ty = math.sin(a) * (hr + 6)
            path.move_to(tx - math.cos(a)*5, ty - math.sin(a)*5)
            path.line_to(tx, ty)
        scene.ShapeNode(path, stroke_color=(0.6,0.6,0.6,0.5),
                        position=(cx,cy), z_position=5, parent=self)

    def _load_ships(self):
        objects = load_wireframes_from_json('files/Elite_ships.json')
        if objects:
            return objects

    def _build_buttons(self):
        sw = self.size.w
        labels = [
            ('ROLL\nL',   (0.3, 0.6, 1.0, 0.85)),
            ('ROLL\nR',   (0.3, 0.6, 1.0, 0.85)),
            ('PITCH\nUP', (0.2, 0.9, 0.5, 0.85)),
            ('PITCH\nDN', (0.2, 0.9, 0.5, 0.85)),
            ('THST\n+',   (1.0, 0.6, 0.1, 0.85)),
            ('THST\n-',   (1.0, 0.6, 0.1, 0.85)),
        ]
        n       = len(labels)
        total_w = n * BTN_W + (n-1) * BTN_PAD
        start_x = (sw - total_w) / 2
        self.buttons = [
            TouchButton(lbl, start_x + i*(BTN_W+BTN_PAD), BTN_Y, BTN_W, BTN_H, col)
            for i, (lbl, col) in enumerate(labels)
        ]

    def touch_began(self, touch):
        for i, btn in enumerate(self.buttons):
            if btn.contains(touch.location):
                btn.pressed = True
                self._touch_map[touch.touch_id] = i
                return

    def touch_moved(self, touch):
        uid = touch.touch_id
        if uid in self._touch_map:
            i = self._touch_map[uid]
            if not self.buttons[i].contains(touch.location):
                self.buttons[i].pressed = False
                del self._touch_map[uid]

    def touch_ended(self, touch):
        uid = touch.touch_id
        if uid in self._touch_map:
            self.buttons[self._touch_map[uid]].pressed = False
            del self._touch_map[uid]

    def update(self):
        self._apply_controls()
        self._move_camera()
        for ms in self.moving_ships:
            ms.update()

    def _apply_controls(self):
        MAX_BANK   = math.radians(85)
        BANK_DECAY = 0.88
        pressed = [b.pressed for b in self.buttons]
        rolling = False
        if pressed[0]:
            self.roll_angle = max(-MAX_BANK, self.roll_angle - ROLL_RATE)
            rolling = True
        if pressed[1]:
            self.roll_angle = min( MAX_BANK, self.roll_angle + ROLL_RATE)
            rolling = True
        if not rolling:
            self.roll_angle *= BANK_DECAY
        self.camera.roll = -self.roll_angle
        if pressed[2]:
            self.camera.pitch = min( math.radians(80), self.camera.pitch + PITCH_RATE)
        if pressed[3]:
            self.camera.pitch = max(-math.radians(80), self.camera.pitch - PITCH_RATE)
        if pressed[4]:
            self.thrust = min(MAX_THRUST, self.thrust + THRUST_STEP)
        if pressed[5]:
            self.thrust = max(MIN_THRUST, self.thrust - THRUST_STEP)

    def _move_camera(self):
        if abs(self.thrust) < 0.01:
            return
        fwd = self.camera.forward()
        cam = self.camera.position
        cam.x += fwd.x * self.thrust
        cam.y += fwd.y * self.thrust
        cam.z += fwd.z * self.thrust
        bx, by, bz = self.bounds
        cam.x %= bx
        cam.y %= by
        cam.z %= bz

    def draw(self):
        scene.background(0, 0, 0)
        all_objs = [ms.obj for ms in self.moving_ships] + self.static_objects
        self.renderer.draw(all_objs, self.camera, self.size)
        self._draw_hud()

    def _draw_hud(self):
        self.roll_indicator.rotation = -self.roll_angle
        self.roll_indicator.alpha    = 0.4 + 0.6 * abs(math.sin(self.roll_angle))
        scene.push_matrix()
        for btn in self.buttons:
            btn.draw()
        scene.pop_matrix()
        self.spd_status.text = f'SPD {self.thrust:+.1f}'
        c = self.camera.position
        self.status.text = f'{c.x:.0f}, {c.y:.0f}, {c.z:.0f}'
        
class Demo2(scene.Scene):
    def setup(self):
        from change_screensize import get_screen_size
        W, H = get_screen_size()
        self.camera = Camera(
            position=Vector3(0, 0, -500),
            fov=math.radians(80),
            z_far=10000,
            z_near=5
        )
        self.renderer = Renderer(depth_sort=True, backface_cull=False)
        self.t = 0

        self.objects = [
            WireSphere(10, lat_lines=10, lon_lines=32,
                       position=Vector3(0, 0, 100), color=YELLOW),
        ]

        try:
            objects = load_wireframes_from_json('files/Elite_ships.json')
        except Exception:
            ship_locs = [
                'missile','coriolis','escape_pod','plate','canister',
                'Boulder','Asteroid','Splinter','Shuttle','Transporter',
                'Cobra_Mk_3','Python','Boa','Anaconda','Rock_hermit',
                'Viper','Sidewinder','Mamba','Krait','Adder','Gecko',
                'Cobra_Mk_1','Worm','Cobra_Mk_3_p','Asp_Mk_2','Python_p',
                'Fer_de_lance','Moray','Thargoid','Thargon','Constrictor',
                'logo','Cougar','Dodo'
            ]
            ships = GetEliteShips('6502sp', ship_locs)
            objects = ships.ship_objects

        spacing = 100
        for i, ship in enumerate(objects):
            ship.position = Vector3(
                -4*spacing + i % 10 * spacing,
                -2*spacing + spacing * i / 10,
                500
            )
            ship.scale   = 0.5
            ship.visible = i % 2
            ship.color   = choice([GREEN, RED, YELLOW, WHITE, CYAN, BLUE])
            ship.explosion_time = random.random()
            self.objects.append(ship)

        self._exploding_obj = None
        self._explosion_t   = random.random()

    def _pick_new_explosion(self):
        candidates = [o for o in self.objects if hasattr(o, 'name')]
        if candidates:
            obj = random.choice(candidates)
            obj.explosion_time  = 0.0
            self._exploding_obj = obj
            self._explosion_t   = 0.0

    def update(self):
        self.t += self.dt * .001
        for obj in self.objects[:]:
            obj.rotation.y = math.radians(-45)
            obj.rotation.z = self.t
            obj.position_in_world        = obj.position.clone()
            obj.rotation_angles_in_world = obj.rotation.clone()

        EXPLOSION_SPEED = 0.4
        if self._exploding_obj is None:
            self._pick_new_explosion()
        else:
            self._explosion_t += self.dt * EXPLOSION_SPEED
            self._exploding_obj.explosion_time = self._explosion_t
            if self._explosion_t >= 1.0:
                self._exploding_obj = None

    def draw(self):
        scene.background(0, 0, 0)
        exploding = self._exploding_obj
        for obj in self.objects:
            if obj == exploding:
                self.renderer.explode(obj, self.camera, self.size)
            else:
                self.renderer.draw([obj], self.camera, self.size)


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    #g = Demo()
    #g.setup()
    #g.draw()
    scene.run(Demo2(), show_fps=True, multi_touch=True)
