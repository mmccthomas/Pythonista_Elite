
import io
from PIL import Image
import numpy as np
import ui
from scene import SpriteNode, Texture
import pathlib


def pil_to_ui(img):
    if isinstance(img, ui.Image):
      return img
    # Ensure the image has an alpha channel (Red, Green, Blue, Alpha)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    with io.BytesIO() as bIO:
        img.save(bIO, 'png')
        return ui.Image.from_data(bIO.getvalue())
        

def set_colorkey(image_name, color=None):
    """ open an image in images folder
    convert to array and use colour in top left corner
    to set transparency. Return image object"""
    image = Image.open(pathlib.Path('images',  image_name))
    # convert color to transparent
    img = image.convert('RGBA')
    arr = np.array(img)
    # get colour of top left pixel
    colorkey = arr[0, 0, :3]
    # create a mask where pixels match colorkey
    trans_pixels = np.all(arr[:, :, :3] == colorkey, axis=2)
    arr[trans_pixels, 3] = 0
    return Image.fromarray(arr)

    
def create_oval(rect, color, line_width=2, fill=False, clip=None):
    """ create an image of an oval, with or without fill"""
    x, y, w, h = rect
    
    inset = line_width / 2
    rect_inset = (x + inset, y + inset, w - 2 * line_width, h - 2 * line_width)
    # 1. Create context (Background is transparent by default)
    with ui.ImageContext(rect[2], rect[3]) as ctx:
        # 2. Inset the rect so the stroke doesn't get clipped at the edges
        ui.set_color('clear')
        ui.fill_rect(0, 0, rect[2], rect[3])
        # 3. Create the path and set properties
        if clip:
            ui.Path.rect(*clip).add_clip()
        ui.set_color(color)
        oval = ui.Path.oval(inset, inset, rect_inset[2], rect_inset[3])
        oval.line_width = line_width
        
        # 4. Set the color and draw the outline (stroke)
        oval.stroke()
        if fill:
            oval.fill()
        # 5. Capture the image
        image = ctx.get_image()
    return image


def create_circle(radius, color, line_width=2, fill=False, clip=None):
    """ create an image of a circle, with or without fill
    use oval with equal width and height"""
    w = h = radius * 2
    rect = (0, 0, w, h)
    img = create_oval(rect, color, line_width, fill, clip)
    return img

        
def draw_line(source_coord, target_coord, color, line_width=3):
    # In Pygame: draw.line(surface, color, start, end, width)
    # In Pythonista:
    side = int(abs(target_coord[0] - source_coord[0])), int(abs(target_coord[1] - source_coord[1]))
    with ui.ImageContext(*side) as ctx:
        path = ui.Path()
        path.line_width = line_width
        path.move_to(*source_coord)
        path.line_to(*target_coord)
        ui.set_color(color)
        path.stroke()
        # 5. Capture the image
        return ctx.get_image()

                
def new_sprite(image, parent=None, **kwargs):
    sprite = SpriteNode(Texture(pil_to_ui(image)))
    
    for k, v in kwargs.items():
       setattr(sprite, k, v)
    if parent:
       parent.add_child(sprite)
    return sprite

                          
if __name__ == '__main__':
   img = set_colorkey('asteroid.png')
   img.show()
   img = create_circle(100, 'red')
   img.show()
   img = create_circle(150, 'green', fill=True, clip=(50, 0, 280, 150))
   img.show()
   img = draw_line((0, 0), (100, 200), color='red')
   img.show()
   img = create_oval((0, 0, 300, 150), 'green', 5, fill=False, clip=(50, 0, 280, 150))
   img.show()
   
