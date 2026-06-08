# routine to generate good looking rotating planet
from scene import Scene, SpriteNode, Texture, Shader, run
from change_screensize import get_screen_size
import numpy as np
from PIL import Image, ImageFilter
import ui
import io
import colorsys
import random
import logging
logger = logging.getLogger(__name__)


def pil_to_ui(img):
    if isinstance(img, ui.Image):
      return img
    # Ensure the image has an alpha channel (Red, Green, Blue, Alpha)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    with io.BytesIO() as bIO:
        img.save(bIO, 'png')
        return ui.Image.from_data(bIO.getvalue())


shader_code = '''
precision highp float;
varying vec2 v_tex_coord;

uniform sampler2D u_texture;
uniform float u_time;
uniform float u_softness;
uniform vec4 u_clip_rect; // x, y, width, height (0.0 to 1.0)
uniform vec2 u_screen;    // width, height of screen in pixels
uniform vec3 u_light; // lighting direction

void main() {
    // --- 1. COORDINATE SETUP ---
    vec2 uv = v_tex_coord - 0.5;
    float dist = length(uv);
    float radius = 0.45;
    
    // --- 2. CLIPPING LOGIC ---
    // gl_FragCoord is bottom-left, Pythonista UI is top-left
    vec2 screen_uv = gl_FragCoord.xy / u_screen;
    float flipped_y = 1.0 - screen_uv.y;
    
    float clip_mask = step(u_clip_rect.x, screen_uv.x) * step(screen_uv.x, u_clip_rect.x + u_clip_rect.z) *
                      step(u_clip_rect.y, flipped_y) * step(flipped_y, u_clip_rect.y + u_clip_rect.w);

    // --- 3. SPHERE & LIGHTING ---
    float alpha = smoothstep(radius, radius - u_softness, dist);
    
    // Simple 3D Normal calculation
    float z = sqrt(max(0.0, radius * radius - dot(uv, uv)));
    vec3 normal = normalize(vec3(uv, z));
    vec3 light_dir = normalize(u_light);
    float diff = max(dot(normal, light_dir), 0.1);
    
    // --- 4. TEXTURE MAPPING ---
    // Scroll x over time to simulate rotation
    vec2 uv_texture = v_tex_coord;
    uv_texture.x = mod(uv_texture.x + u_time * 0.1, 1.0);
    vec3 tex_color = texture2D(u_texture, uv_texture).rgb;
    
    // --- 5. FINAL OUTPUT ---
    vec3 final_rgb = tex_color * diff;
    gl_FragColor = vec4(final_rgb, 1.0) * alpha * clip_mask;
}
'''

                                
class AlienPlanet():
 
  def __init__(self, W=1024, H=512, color=0.28, seed=None, **kwargs):
     # color is a hue from 0 - 1.0
     # sea_level controls islands
     self.W = W
     self.H = H
     self.cloud_threshold = 0.8  # lower is more cloud
     self.color = color  # 0 is red, 0.25 green
     self.sea_level = random.uniform(0.1, 0.8)
     self.blend = 10  # increase to blend more
     self.blob_size = 3
     self.rng = np.random.default_rng(42)
     self.edge_margin = 0.15 # ocean margin at edges
     if seed is None:
        self.seed = random.randint(1, 10)
     else:
         self.seed = 1 + seed % 9
         
     for k, v in kwargs.items():
         setattr(self, k, v)
     self.compose()
     
  def compose(self):
      # sea_level controls land/water  ratio higher is more
      self.terrain = self.build_terrain(warp_strength=0.3)
      polar_ice, polar_mask = self.polar_ice()
      polar_mask = 0
      colour = self.colour_surface(polar_mask, hue=self.color)
      surface_img = Image.fromarray(colour, 'RGB')
      cloud_img = self.clouds()
      # Composite
      final = surface_img.convert('RGBA')
      final = Image.alpha_composite(final, cloud_img).convert('RGB')
      
      # Light sharpening pass
      self.final = final.filter(ImageFilter.UnsharpMask(radius=1, percent=40, threshold=3))
      out_path = 'images/planet_texture.png'
      self.final.save(out_path, 'PNG')
      # logger.debug(f"Saved {self.final.size} texture to {out_path}")
      
  def build_terrain(self, seed=7, warp_strength=0.3):
   
      # ── Build terrain heightmap ────────────────────────────────────────────────────
    
      terrain = self.spherical_fbm(scale=80, octaves=8, seed=seed)
      
      # Add some large "continental shelf" blobs
      big_blob = [
          (0.25, 0.45, 0.18, 0.4),
          (0.55, 0.35, 0.22, 0.45),
          (0.72, 0.60, 0.14, 0.35),
          (0.10, 0.65, 0.12, 0.30),
          (0.88, 0.30, 0.10, 0.28)]
          
      middle_blob = [
          (0.25, 0.45, 0.08, 0.35),
          (0.55, 0.35, 0.09, 0.38),
          (0.72, 0.60, 0.06, 0.30),
          (0.10, 0.65, 0.07, 0.28),
          (0.88, 0.30, 0.05, 0.25),
          (0.40, 0.70, 0.06, 0.28),
          (0.65, 0.20, 0.07, 0.30),
          (0.30, 0.20, 0.05, 0.25),
          (0.80, 0.55, 0.06, 0.22)]
      small_blob = [
          (0.25, 0.45, 0.08, 0.35),
          (0.55, 0.35, 0.09, 0.38),
          (0.72, 0.60, 0.06, 0.30),
          (0.10, 0.65, 0.07, 0.28),
          (0.88, 0.30, 0.05, 0.25),
          (0.40, 0.70, 0.06, 0.28),
          (0.65, 0.20, 0.07, 0.30),
          (0.30, 0.20, 0.05, 0.25),
          (0.80, 0.55, 0.06, 0.22),
          (0.50, 0.55, 0.07, 0.28),
          (0.15, 0.35, 0.06, 0.25),
          (0.92, 0.65, 0.05, 0.22),
          (0.45, 0.15, 0.06, 0.27),
          (0.60, 0.80, 0.07, 0.24),
          (0.35, 0.60, 0.05, 0.23)]
      if self.blob_size is None:
          blob_size = random.choice([small_blob, middle_blob, big_blob])
      else:
          blob_size =  [small_blob, middle_blob, big_blob][self.blob_size % 3]
      for cx, cy, r, strength in blob_size:
          ys, xs = np.mgrid[0:self.H, 0:self.W]
          dx = (xs / self.W - cx)
          dy = (ys / self.H - cy)
          blob = np.exp(-(dx**2 + dy**2) / (2 * r**2)) * strength
          terrain += blob
      # Warp terrain with a second noise field to break up land bridges
      warp = self.smooth_noise(60, octaves=4, seed=seed+100) - 0.5
      terrain += warp * warp_strength  # increase 0.3 for more fragmentation
      terrain = (terrain - terrain.min()) / (terrain.max() - terrain.min())
      
      # âOcean margin: suppress land near the left/right wrap edges
      # Build a [0..1] weight that is 0 at the edges and 1 in the interior.
      # We use a smoothstep ramp over `edge_margin` fraction of the width.
      # Terrain values are then pulled below sea_level inside this band so the
      # wrap seam is guaranteed to be ocean.
      m = self.edge_margin          # e.g. 0.06
      xs_norm = np.linspace(0.0, 1.0, self.W)          # (W,)
      # ramp: 0 â 1 over [0, m], flat 1 in middle, 1 â 0 over [1-m, 1]
      left_ramp  = np.clip(xs_norm / m, 0.0, 1.0)
      right_ramp = np.clip((1.0 - xs_norm) / m, 0.0, 1.0)
      edge_weight = np.minimum(left_ramp, right_ramp)   # (W,)
      # smoothstep for a softer coastline gradient
      edge_weight = edge_weight * edge_weight * (3.0 - 2.0 * edge_weight)
      edge_weight = edge_weight[np.newaxis, :]          # broadcast over H

      # Pull terrain toward (sea_level - 0.15) at the edges.
      # Where edge_weight==1 (interior) terrain is unchanged.
      # Where edge_weight==0 (edge) terrain is forced well below sea level.
      ocean_floor = self.sea_level - 0.15
      terrain = terrain * edge_weight + ocean_floor * (1.0 - edge_weight)
      # Re-normalise so colour bands aren't shifted
      terrain = (terrain - terrain.min()) / (terrain.max() - terrain.min())
      
      return terrain
      
  def polar_ice(self):
            
      ys_norm = np.linspace(0, 1, self.H)[:, None]
      polar_mask = np.maximum(
          np.clip((0.08 - ys_norm) / 0.08, 0, 1),
          np.clip((ys_norm - 0.92) / 0.08, 0, 1),
      )
      polar_noise = self.smooth_noise(60, octaves=4, seed=99)
      return polar_mask, polar_noise

  def colour_surface(self, polar_mask, hue=0.08):
      
      def hc(h, s, v):
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return np.array([r * 255, g * 255, b * 255])
              
      sea_level = self.sea_level
      # Alien palette: deep violet ocean, rust-orange lowlands, amber highlands, grey peaks
      ocean_deep = np.array([18,  10,  55])    # deep indigo-violet
      ocean_shallow = np.array([55, 25, 110])    # violet
      lowland = hc(hue, 0.80, 0.55)
      midland = hc(hue, 0.65, 0.68)
      highland = hc(hue, 0.45, 0.80)
      peak = np.array([230, 220, 200])    # near-white
      ice = np.array([220, 230, 255])    # blue-white
           
      def lerp(a, b, t):
          t = np.clip(t, 0, 1)
          return a + (b - a) * t
      
      colour = np.zeros((self.H, self.W, 3), dtype=float)
      t = self.terrain
      
      # Ocean zones
      mask_deep = t < sea_level - 0.10
      mask_shallow = (t >= sea_level - 0.10) & (t < sea_level)
      mask_low = (t >= sea_level) & (t < sea_level + 0.12)
      mask_mid = (t >= sea_level + 0.12) & (t < sea_level + 0.28)
      mask_high = (t >= sea_level + 0.28) & (t < sea_level + 0.45)
      mask_peak = t >= sea_level + 0.45
      
      for c in range(3):
          td = np.clip((t - (sea_level - 0.10)) / 0.10, 0, 1)
          ts = np.clip((t - sea_level) / 0.12, 0, 1)
          tl = np.clip((t - (sea_level + 0.12)) / 0.16, 0, 1)
          tm = np.clip((t - (sea_level + 0.28)) / 0.17, 0, 1)
          tp = np.clip((t - (sea_level + 0.45)) / 0.15, 0, 1)
      
          colour[:, :, c] = (
               + mask_deep * lerp(ocean_deep[c], ocean_deep[c], td)
               + mask_shallow * lerp(ocean_deep[c],    ocean_shallow[c], td)
               + mask_low * lerp(lowland[c], lowland[c], ts)
               + mask_mid * lerp(lowland[c], midland[c], tl)
               + mask_high * lerp(midland[c], highland[c], tm)
               + mask_peak * lerp(highland[c], peak[c], tp)
          )
      
      # Apply polar ice
      for c in range(3):
         colour[:, :, c] = colour[:, :, c] * (1 - polar_mask) + ice[c] * polar_mask
      
      # Subtle noise variation on land
      land_mask = (t >= sea_level).astype(float)
      detail_noise = self.smooth_noise(30, octaves=4, seed=55) * 2 - 1
      for c in range(3):
          colour[:, :, c] += land_mask * detail_noise * 8
      
      colour = np.clip(colour, 0, 255).astype(np.uint8)
      return colour
                  
  def clouds(self):
      # Cloud layer
      
      cloud_noise = self.spherical_fbm(scale=140, octaves=6, seed=123)
      cloud_noise2 = self.smooth_noise(80, octaves=5, seed=77)
      cloud_combined = cloud_noise * 0.7 + cloud_noise2 * 0.3
            
      cloud_alpha = np.clip((cloud_combined - self.cloud_threshold) / 0.2, 0, 1)
      
      # Soften
      cloud_alpha_img = Image.fromarray((cloud_alpha * 255).astype(np.uint8))
      cloud_alpha_img = cloud_alpha_img.filter(ImageFilter.GaussianBlur(radius=3))
      cloud_alpha = np.array(cloud_alpha_img) / 255.0
      
      # Fade cloud opacity to zero at the horizontal edges (same margin as terrain)
      # so the wrap seam is always clear sky.
      m = self.edge_margin
      xs_norm = np.linspace(0.0, 1.0, self.W)
      left_ramp  = np.clip(xs_norm / m, 0.0, 1.0)
      right_ramp = np.clip((1.0 - xs_norm) / m, 0.0, 1.0)
      edge_weight = np.minimum(left_ramp, right_ramp)
      edge_weight = edge_weight * edge_weight * (3.0 - 2.0 * edge_weight)  # smoothstep
      cloud_alpha *= edge_weight[np.newaxis, :]
      
      # Cloud colour: slightly warm white / cream
      cloud_colour = np.array([248, 245, 255], dtype=float)
      cloud_layer = np.zeros((self.H, self.W, 4), dtype=np.uint8)
      for c in range(3):
          cloud_layer[:, :, c] = cloud_colour[c]
      cloud_layer[:, :, 3] = (cloud_alpha * 210).astype(np.uint8)
      
      cloud_img = Image.fromarray(cloud_layer, 'RGBA')
      return cloud_img
      
  # ── Noise helpers ──────────────────────────────────────────────────────────────
    
  def smooth_noise(self, scale, octaves=6, persistence=0.5, seed=0):
      w, h = self.W, self.H
      """Fractal Brownian Motion via summed random grids."""
      rs = np.random.RandomState(seed)
      result = np.zeros((h, w))
      amp = 1.0
      freq = 1.0
      max_val = 0.0
      for _ in range(octaves):
          gw = max(2, int(w / scale * freq) + 2)
          gh = max(2, int(h / scale * freq) + 2)
          grid = rs.rand(gh, gw)
          # bilinear up-sample
          from PIL import Image as _I
          img = _I.fromarray((grid * 255).astype(np.uint8))
          img = img.resize((w, h), _I.BILINEAR)
          result += np.array(img, dtype=float) / 255.0 * amp
          max_val += amp
          amp *= persistence
          freq *= 2.0
      return result / max_val
        
  def spherical_fbm(self, scale=200, octaves=7, seed=0):
      """FBM in latitude/longitude space with spherical wrap-around."""
      w, h = self.W, self.H
      rs = np.random.RandomState(seed)
      result = np.zeros((h, w))
      amp = 1.0
      freq = 1.0
      max_val = 0.0
      for o in range(octaves):
          s = max(2, int(scale / freq))
          gw = w // s + 2
          gh = h // s + 2
          grid = rs.rand(gh, gw)
          img = Image.fromarray((grid * 255).astype(np.uint8))
          img = img.resize((w, h), Image.BILINEAR)
          layer = np.array(img, dtype=float) / 255.0
          # horizontal wrap blend
          blend_w = max(1, w // self.blend)  # inrease to blend more
          left = layer[:, :blend_w]
          right = layer[:, -blend_w:]
          for x in range(blend_w):
              t = x / blend_w
              layer[:, x] = right[:, x] * (1 - t) + left[:, x] * t
              layer[:, w-1-x] = left[:, blend_w-1-x] * (1 - t) + right[:, blend_w-1-x] * t
          result += layer * amp
          max_val += amp
          amp *= 0.5
          freq *= 2.0
      return result / max_val


class PlanetScene(Scene):
    def setup(self):
        self.planet = Planet(size=500,
                             position=self.size/2,
                             # y measured from top
                             #.          x.  y.   w.    h
                             clip_rect=(0.1, 0.1, 0.9, 0.9))
        # image_path='images/sun_texture400.png')
        self.add_child(self.planet.planet)
        
    def update(self):
        self.planet.update(self.t)

                                
class Planet():
    def __init__(self, size=500, position=(0, 0), clip_rect=(0.1, 0.1, 0.9, 0.9),
                 image_path='images/planet_texture.png',
                 light_dir=(1, 1, 1), soft=0.001,
                 parent=None):
        # set light_dir to (0,0,1) for front lighting (sun)
        # set soft to higher value for soft
        # Load a built-in texture (Planet image)
        self.planet = SpriteNode(size=(size, size), position=position)
        if parent:
           parent.add_child(self.planet)
        self
        # Initialize Shader
        self.planet.shader = Shader(shader_code)
        if ':' in image_path:
            # builtin image is ui_image
            self.planet.shader.set_uniform('u_texture', Texture(image_path))
        else:
            image = Image.open(image_path)
            #image = image.rotate(90)
            self.planet.shader.set_uniform('u_texture', Texture(pil_to_ui(image)))
        # Set Uniforms
        # u_clip_rect: x, y, w, h in normalized (0..1) screen space
        # This example clips to the middle 50% of the screen
        #
        self.planet.shader.set_uniform('u_clip_rect', clip_rect)
        self.planet.shader.set_uniform('u_softness', soft)
        self.planet.shader.set_uniform('u_light', light_dir)
        self.planet.alpha = 1
        
    def update(self, t):
        # Update time and screen size (in case of rotation)
        s = get_screen_size() * 2  # Multiply by 2 for Retina scale
        self.planet.shader.set_uniform('u_screen', (s.w, s.h))
        self.planet.shader.set_uniform('u_time', t)

                                
if __name__ == '__main__':
 
    from time import time
    for i in range(1):
        t = time()
        color = i/10
        print(color)
        img = AlienPlanet(400, 400, color).final
        print(time()-t)
        img.show()
    run(PlanetScene())
