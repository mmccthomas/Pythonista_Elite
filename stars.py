import random
import constants as cs

# NOTE graphics routine handles clipping


def _rand255():
    return random.randint(0, 255)
        
        
class Star:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        

class Starfield:
    def __init__(self, game_state, width=None, height=None, n_stars=12):
        self.gs = game_state
        self.gfx = game_state.gfx
        if width is None:
          width, height = cs.FLIGHT_RECT.size
        self.width, self.height = width, height
        self.center_x, self.center_y = cs.FLIGHT_RECT.center()
        self.n_stars = n_stars
        self.sz = 4
        self.total_stars = 20
        self.stars = [Star() for _ in range(self.total_stars)]
        self.warp_stars = True
        self.speedup = 1

    def create_new_stars(self):
        nstars = 3 if self.gs.witchspace else self.n_stars
        for star in self.stars[:nstars]:
            star.x = (_rand255() - 128) | 8  # skips 1-7
            star.y = (_rand255() - 128) | 4  # skips 1-3
            star.z = _rand255() | 0x90
        self.warp_stars = True

    def front_starfield(self):
        gfx = self.gfx
        nstars = 3 if self.gs.space else self.n_stars
        delta = 50.0 if self.warp_stars else float(self.gs.flight_speed) * self.speedup
        alpha = float(self.gs.space.flight_roll) / 256.0
        beta = float(self.gs.space.flight_climb)
        delta /= 2.0
        cx = self.center_x
        cy = self.center_y

        for star in self.stars[:nstars]:
            # Plot current position
            sx = star.x * cs.GFX_SCALEX + cx
            sy = star.y * cs.GFX_SCALEY + cy
            zz = star.z

            if not self.warp_stars:
                gfx.plot_pixel(sx, sy, cs.WHITE, self.sz)
                if zz < 0xC0:
                    gfx.plot_pixel(sx + 1, sy, cs.WHITE), self.sz
                if zz < 0x90:
                    gfx.plot_pixel(sx, sy + 1, cs.WHITE, self.sz)
                    gfx.plot_pixel(sx + 1, sy + 1, cs.WHITE, self.sz)

            # Movement logic
            q = delta / star.z
            star.z -= delta
            
            yy = star.y + (star.y * q)
            xx = star.x + (star.x * q)
            
            # Apply Roll and Climb
            yy = yy + (xx * alpha)
            xx = xx - (yy * alpha)
            yy = yy + beta

            if self.warp_stars:
                gfx.draw_line(sx, sy, xx * cs.GFX_SCALEX + cx, yy * cs.GFX_SCALEY + cy, self.sz)

            star.x = xx
            star.y = yy

            # Recycle stars that go off screen or too close
            if abs(xx) > 120 or abs(yy) > 120 or star.z < 16:
                star.x = (_rand255() - 128) | 8
                star.y = (_rand255() - 128) | 4
                star.z = _rand255() | 0x90

        self.warp_stars = False

    def rear_starfield(self):
        gfx = self.gfx
        nstars = 3 if self.gs.witchspace else self.n_stars
        delta = 50.0 if self.warp_stars else float(self.gs.flight_speed) * self.speedup
        alpha = -float(self.gs.space.flight_roll) / 256.0
        beta = -float(self.gs.space.flight_climb)
        delta /= 2.0
        cx = self.center_x
        cy = self.center_y
        
        for star in self.stars[:nstars]:
            sx = star.x * cs.GFX_SCALEX + cx
            sy = star.y * cs.GFX_SCALEY + cy
            zz = star.z

            if not self.warp_stars:
                gfx.plot_pixel(sx, sy, cs.WHITE, self.sz)
                # (Simplified thickness logic same as front)
                if zz < 0xC0:
                    gfx.plot_pixel(sx + 1, sy, cs.WHITE, self.sz)

            q = delta / star.z
            star.z += delta
            
            yy = star.y - (star.y * q)
            xx = star.x - (star.x * q)
            
            yy = yy + (xx * alpha)
            xx = xx - (yy * alpha)
            yy = yy + beta

            if self.warp_stars:
                ex = xx * cs.GFX_SCALEX + cx
                ey = yy * cs.GFX_SCALEY + cy
                gfx.draw_line(sx, sy, ex, ey)

            star.x = xx
            star.y = yy

            if star.z >= 300 or abs(yy) >= 110:
                star.z = (_rand255() & 127) + 51
                if _rand255() & 1:
                    star.x = _rand255() - 128
                    star.y = -115 if (_rand255() & 1) else 115
                else:
                    star.x = -126 if (_rand255() & 1) else 126
                    star.y = _rand255() - 128

        self.warp_stars = False

    def side_starfield(self):
        gfx = self.gfx
        nstars = 3 if self.gs.witchspace else self.n_stars
        delta = 50.0 if self.warp_stars else float(self.gs.flight_speed) * self.speedup
        alpha = float(self.gs.space.flight_roll)
        beta = float(self.gs.space.flight_climb)
        cx = self.center_x
        cy = self.center_y
        
        if self.gs.current_screen == cs.SCR_LEFT_VIEW:
            delta, alpha, beta = -delta, -alpha, -beta

        for star in self.stars[:nstars]:
            sx = star.x * cs.GFX_SCALEX + cx
            sy = star.y * cs.GFX_SCALEY + cy
            
            if not self.warp_stars:
                gfx.plot_pixel(sx, sy, cs.WHITE, self.sz)

            xx, yy, zz = star.x, star.y, star.z
            
            delt8 = delta / (zz / 32.0)
            xx += delt8
            xx += (yy * (beta / 256.0))
            yy -= (xx * (beta / 256.0))
            
            rot = (yy / 256.0) * (alpha / 256.0)
            xx += rot * (-xx)
            yy += rot * yy
            yy += alpha

            if self.warp_stars:
                gfx.draw_line(sx, sy, xx * cs.GFX_SCALEX + cx, yy * cs.GFX_SCALEY + cy, self.sz)

            star.x, star.y = xx, yy

            if abs(xx) >= 116:
                star.y = _rand255() - 128
                star.x = 115 if self.gs.current_screen == cs.SCR_LEFT_VIEW else -115
                star.z = _rand255() | 8
            elif abs(yy) >= 116:
                star.x = _rand255() - 128
                star.y = -110 if alpha > 0 else 110
                star.z = _rand255() | 8

        self.warp_stars = False

    def flip_stars(self):
        nstars = 3 if self.gs.witchspace else self.n_stars
        for star in self.stars[:nstars]:
            star.x, star.y = star.y, star.x

    def update_starfield(self):
        gs = self.gs
        if gs.current_screen in [cs.SCR_FRONT_VIEW, cs.SCR_INTRO_ONE, cs.SCR_INTRO_TWO, cs.SCR_ESCAPE_POD]:
            self.front_starfield()
        elif gs.current_screen in [cs.SCR_REAR_VIEW, cs.SCR_GAME_OVER]:
            self.rear_starfield()
        elif gs.current_screen in [cs.SCR_LEFT_VIEW, cs.SCR_RIGHT_VIEW]:
            self.side_starfield()

    def update_front_view_(self, flight_speed, flight_roll, flight_climb):
        """Vectorized version of the front_starfield function."""
        count = 3 if self.gs.witchspace else 12
        
        delta = 50 if self.warp_stars else flight_speed
        alpha = flight_roll / 256.0
        beta = flight_climb
        delta_eff = delta / 2.0

        for star in self.stars[:count]:
            x, y, z = star
            
            # 1. Project current coordinates to screen
            # (Matches: sx = x + 128, sy = y + 96)
            sx = x + self.center_x
            sy = y + self.center_y

            # 2. Calculate perspective shift (Q = delta / z)
            q = delta_eff / z
            
            # 3. Move the stars
            new_z = z - delta_eff
            new_y = y + (y * q)
            new_x = x + (x * q)
            
            # 4. Apply Roll (Alpha) and Pitch/Climb (Beta)
            # The original C logic: yy = yy + (xx * alpha); xx = xx - (yy * alpha);
            new_y = new_y + (new_x * alpha)
            new_x = new_x - (new_y * alpha)
            new_y = new_y + beta

            # 5. Check Boundaries / Respawn
            if abs(new_x) > 120 or abs(new_y) > 120 or new_z < 16:
                star = [
                    (random.randint(0, 255) - 128) | 8,
                    (random.randint(0, 255) - 128) | 4,
                    random.randint(0, 255) | 0x90
                ]
            else:
                star = [new_x, new_y, new_z]
            
            # Return values for the drawing loop
            # yields (old_sx, old_sy, new_sx, new_sy, brightness_based_on_z)
            yield (sx, sy, new_x + self.center_x, new_y + self.center_y, z)

# Example usage for a game loop:
# star_engine = Starfield()
# for old_x, old_y, new_x, new_y, z in star_engine.update_front_view(speed, roll, climb):
#     plot_pixel(new_x, new_y)
