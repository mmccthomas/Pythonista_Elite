from elite import GalaxySeed
from types import SimpleNamespace
import math


class PlanetGenerator:
    def __init__(self, game_state):
        self.gs = game_state
        # The famous Elite digrams used for name generation
        self.digrams = "ABOUSEITILETSTONLONUTHNOALLEXEGEZACEBISOUSESARMAINDIREA?ERATENBERALAVETIEDORQUANTEISRION"
        
        self.inhabitant_desc1 = ["Large ", "Fierce ", "Small "]
        self.inhabitant_desc2 = ["Green ", "Red ", "Yellow ", "Blue ", "Black ", "Harmless "]
        self.inhabitant_desc3 = ["Slimy ", "Bug-Eyed ", "Horned ", "Bony ", "Fat ", "Furry "]
        self.inhabitant_desc4 = ["Rodent", "Frog", "Lizard", "Lobster", "Bird", "Humanoid", "Feline", "Insect"]

        # The procedural description grammar
        self.desc_list = [
            ["fabled", "notable", "well known", "famous", "noted"],
            ["very", "mildly", "most", "reasonably", ""],
            ["ancient", "<20>", "great", "vast", "pink"],
            ["<29> <28> plantations", "mountains", "<27>", "<19> forests", "oceans"],
            ["shyness", "silliness", "mating traditions", "loathing of <5>", "love for <5>"],
            ["food blenders", "tourists", "poetry", "discos", "<13>"],
            ["talking tree", "crab", "bat", "lobst", "%R"],
            ["beset", "plagued", "ravaged", "cursed", "scourged"],
            ["<21> civil war", "<26> <23> <24>s", "a <26> disease", "<21> earthquakes", "<21> solar activity"],
            ["its <2> <3>", "the %I <23> <24>", "its inhabitants' <25> <4>", "<32>", "its <12> <13>"],
            ["juice", "brandy", "water", "brew", "gargle blasters"],
            ["%R", "%I <24>", "%I %R", "%I <26>", "<26> %R"],
            ["fabulous", "exotic", "hoopy", "unusual", "exciting"],
            ["cuisine", "night life", "casinos", "sit coms", " <32> "],
            ["%H", "The planet %H", "The world %H", "This planet", "This world"],
            ["n unremarkable", " boring", " dull", " tedious", " revolting"],
            ["planet", "world", "place", "little planet", "dump"],
            ["wasp", "moth", "grub", "ant", "%R"],
            ["poet", "arts graduate", "yak", "snail", "slug"],
            ["tropical", "dense", "rain", "impenetrable", "exuberant"],
            ["funny", "wierd", "unusual", "strange", "peculiar"],
            ["frequent", "occasional", "unpredictable", "dreadful", "deadly"],
            ["<1> <0> for <9>", "<1> <0> for <9> and <9>", "<7> by <8>", "<1> <0> for <9> but <7> by <8>", " a<15> <16>"],
            ["<26>", "mountain", "edible", "tree", "spotted"],
            ["<30>", "<31>", "<6>oid", "<18>", "<17>"],
            ["ancient", "exceptional", "eccentric", "ingrained", "<20>"],
            ["killer", "deadly", "evil", "lethal", "vicious"],
            ["parking meters", "dust clouds", "ice bergs", "rock formations", "volcanoes"],
            ["plant", "tulip", "banana", "corn", "%Rweed"],
            ["%R", "%I %R", "%I <26>", "inhabitant", "%I %R"],
            ["shrew", "beast", "bison", "snake", "wolf"],
            ["leopard", "cat", "monkey", "goat", "fish"],
            ["<11> <10>", "%I <30> <33>", "its <12> <31> <33>", "<34> <35>", "<11> <10>"],
            ["meat", "cutlet", "steak", "burgers", "soup"],
            ["ice", "mud", "Zero-G", "vacuum", "%I ultra"],
            ["hockey", "cricket", "karate", "polo", "tennis"]
        ]
        
        # Internal state for the pseudo-random generator
        self.rnd_a = 0
        self.rnd_b = 0
        self.rnd_c = 0
        self.rnd_d = 0

    def gen_rnd_number(self) -> int:
        """The classic 6502 8-bit random number generator."""
        x = (self.rnd_a * 2) & 0xFF
        a = x + self.rnd_c
        if self.rnd_a > 127:
            a += 1
        self.rnd_a = a & 0xFF
        self.rnd_c = x

        carry = a // 256
        x_val = self.rnd_b
        a = (carry + x_val + self.rnd_d) & 0xFF
        self.rnd_b = a
        self.rnd_d = x_val
        return a
        
    def tweak(self, s: GalaxySeed):
        """The 'Waggle': moves the seed forward one step."""
        
        w0, w1, w2 = s.raw_seed()
        new_w2 = (w0 + w1 + w2) & 0xFFFF
        new_w = [w1, w2, new_w2]
        s.to_galaxy(new_w)
                            
    def get_planet_name(self, seed: GalaxySeed):
        """
        seed: A list of 3 16-bit integers [w0, w1, w2]
        representing the planet's unique state.
        """
        seed = seed.copy()
        syllables = ["AL", "LE", "XE", "GE", "ZA", "CE", "BI", "SO",
                     "US", "ES", "AR", "MA", "IN", "DI", "RE", "A?",
                     "ER", "AT", "EN", "BE", "RA", "LA", "VE", "TI",
                     "ED", "OR", "QU", "AN", "TE", "IS", "RI", "ON"]
        # seed = seed.raw_seed()[:]
        name = ""
        # A planet name is built from 3 or 4 syllables
        length = 3 if (seed.b & 0x40) == 0 else 4
        
        for i in range(length):
            # Determine the index for the syllable table (5 bits)
            index = seed.e & 0x1F
            if index > 0:
               syllable = syllables[index]
               syllable = syllable.replace('?', '')
               name += syllable
            seed.waggle()
        return name.capitalize()
            
    name_planet = get_planet_name
    
    def generate_planet_stats(self, seed: GalaxySeed):
        """Calculates government, economy, tech level, etc."""
        gov = (seed.d // 8) & 7
        econ = seed.a & 7
        if gov < 2:
            econ |= 2
            
        tech = (econ ^ 7) + (seed.c & 3) + (gov // 2) + (gov & 1)
        pop = (tech * 4) + gov + econ + 1
        radius = (((seed.e & 15) + 11) * 256) + seed.c
        prod = (econ ^ 7) + 3
        prod *= 8 * pop * (gov + 4)
         
        return SimpleNamespace(**{
            "government": gov,
            "economy": econ,
            "tech_level": tech,
            "population": pop / 10.0,  # billions
            "productivity": prod,
            "radius": radius
        })

    def expand_description(self, source: str, planet_name: str) -> str:
        """Recursively expands the procedural grammar."""
        result = ""
        i = 0
        while i < len(source):
            char = source[i]
            
            if char == '<':
                end = source.find('>', i)
                num = int(source[i+1:end])
                
                # Pick one of the 5 procedural options
                rnd = self.gen_rnd_number()
                option = 0
                if rnd >= 0x33:
                    option = 1
                if rnd >= 0x66:
                    option = 2
                if rnd >= 0x99:
                    option = 3
                if rnd >= 0xCC:
                    option = 4
                
                result += self.expand_description(self.desc_list[num][option], planet_name)
                i = end + 1
            elif char == '%':
                i += 1
                cmd = source[i]
                if cmd == 'H':
                    result += planet_name
                elif cmd == 'I':
                    result += planet_name + "ian"
                elif cmd == 'R':
                    # Procedural noise/name generation
                    length = self.gen_rnd_number() & 3
                    for _ in range(length + 1):
                        x = self.gen_rnd_number() & 0x3e
                        result += self.digrams[x:x+2].lower()
                i += 1
            else:
                result += char
                i += 1
        return result

    def describe_planet(self, seed: GalaxySeed) -> str:
        """Entry point for full planet description."""
        self.rnd_a, self.rnd_b = seed.c, seed.d
        self.rnd_c, self.rnd_d = seed.e, seed.f
        
        name = self.get_planet_name(seed)
        description = self.expand_description("<14> is <22>.", name)
        return description

    def find_planet(self, cx, cy):

        min_dist = 10000
  
        glx = GalaxySeed()
        for i in range(256):
            dx = abs(cx - glx.x)
            dy = abs(cy - glx.y)
            distance = math.hypot(dx, dy)            
            if distance < min_dist:
                min_dist = distance
                planet = glx.copy()
            for _ in range(4):
                glx.waggle()              
        return planet

    def get_closest_planets(self, current_glx, max_distance=None):
        # list all 256 systems
        glx = GalaxySeed().copy()
        planets = []
        for i in range(256):
            planet = {}
            name = self.get_planet_name(glx)
            planet['name'] = name
            planet['glx'] = glx.copy()
            for _ in range(4):
                glx.waggle()
        
            planet['x'] = planet['glx'].x
            planet['y'] = planet['glx'].y
            dx = planet['x'] - current_glx.x
            dy = planet['y'] - current_glx.y
            planet['distance'] = round(math.hypot(dx, dy))
            planets.append(SimpleNamespace(**planet))
        sorted_planets = sorted(planets, key=lambda x: x.distance)
        if max_distance is not None:
            sorted_planets = [planet for planet in sorted_planets
                              if planet.distance <= max_distance]
        return sorted_planets
     
    def get_known_planets(self):
       with open('files/PLANET_DATA.TXT', 'r') as f:
        data = f.readlines()
       
       # planets = [data[i].split("'")[1] for i in range(1, 1024, 4)]
       # locations = [data[i].split("(")[1].removesuffix('),') for i in range(1, 1024, 4)]
       import re
       planets = {}
       for i in range(1, 1024, 4):
           match = re.search(r"'([^']+)'\s*\((\d+),(\d+)\)", data[i])
           
           if match:
              name = match.group(1)
              # Convert the coordinates to integers
              x_coord = int(match.group(2))
              y_coord = int(match.group(3))
              planets[name] = {'x': x_coord, 'y': y_coord}
             
       base_x, base_y = planets['Lave']['x'], planets['Lave']['y']
       for planet, position in planets.items():
           x, y = position['x'], position['y']
           distance = math.sqrt((x-base_x)*(x-base_x) + (y-base_y)*(y-base_y))
           planets[planet]['distance'] = round(distance)
       return planets
        

if __name__ == '__main__':
    # --- Example Usage ---
    # Lave (starting planet) seed in Galaxy 1
    import numpy as np
    # x is glx.d y is glx.b
                     
    # --- TEST EXECUTION ---
    # The 'Golden Seed' for Galaxy 1
    current_seed = [0x5A4A, 0x0248, 0xB753]
    gfx = GalaxySeed().copy()
    gen = PlanetGenerator(None)
    for i in range(10):
        # print(gfx)
        gen.tweak(gfx)
        
    lave_seed = GalaxySeed(0xAD, 0x38, 0x14, 0x9C, 0x15, 0x1D)
    print(f"Planet Name: {gen.get_planet_name(lave_seed)}")
    print(f"Stats: {gen.generate_planet_stats(lave_seed)}")
    print(f"Description: {gen.describe_planet(lave_seed)}")
    print()
    # Test get_planet_name
    system_list = [([0x87AA, 0x0C38, 0x8053], 'Ra'),
                   ([0x2800, 0x1CC0, 0x4F4D], 'Ara'),
                   ([0xAD38, 0x149C, 0x151D], 'Lave'),
                   ([0x597A, 0xA4F0, 0xEFA3], 'Arexe'),
                   ([0x9580, 0xB8A0, 0x70DA], 'Errius'),
                   ([0x99C0, 0x8F08, 0x63BD], 'Geinona'),
                   ([0x5A4A, 0x0248, 0xB753], 'Tibedied')]
    # check spefic set of planets as listed in deep dive article
    galaxy = GalaxySeed().copy()
    for system in system_list:
        current_seed, planet_name = system
        galaxy.to_galaxy(current_seed)
        name = gen.get_planet_name(galaxy)
        assert (name == planet_name)
        start_seed_str = ", ".join([f"0x{s:#06x}" for s in current_seed])
        print(f'{start_seed_str} Expected name {planet_name:<8} returned name {name}')
    print()
    # list all 256 systems
    glx = GalaxySeed().copy()
    planet_names = []
    for i in range(256):
        seed_str = f"{glx}"
        name = gen.get_planet_name(glx)
        planet_names.append(name)
        for _ in range(4):
            glx.waggle()
        print(f"System {i:<3}: {name:<12} | Seed: {seed_str} | Colour: {glx.colour}")
    assert ('Lave' in planet_names)
    assert ('Tibedied' in planet_names)
    assert ('Diso' in planet_names)
    print()
    # closest to Lave
    current_glx = GalaxySeed(0xAD, 0x38, 0x14, 0x9c, 0x15, 0x1d)
    closest = gen.get_closest_planets(current_glx, max_distance=None)
    [print(planet) for planet in closest]
    x_locs = [planet.x for planet in closest]
    y_locs = [planet.y for planet in closest]
    print(f'{min(x_locs)=}, {max(x_locs)=}, {np.mean(x_locs)=:.0f}')
    print(f'{min(y_locs)=}, {max(y_locs)=}, {np.mean(y_locs)=:.0f}')
    # sorted_planets = dict(sorted(planets.items(), key=lambda x: x[1].distance))
    # print(sorted_planets.keys())
    # get planet name ab]nd coords at each corner
    
    

    def get_extremities(points):
        import numpy as np
        # points should be an array of shape (N, 2)
        pts = np.array(points)
        extremities = np.zeros((4, 2), dtype="int32")
    
        # 1. Top-Left: Smallest sum (x + y)
        s = pts.sum(axis=1)
        extremities[0] = pts[np.argmin(s)]
    
        # 2. Bottom-Right: Largest sum (x + y)
        extremities[2] = pts[np.argmax(s)]
    
        # 3. Top-Right: Smallest difference (x - y) 
        # (Or largest x - y depending on coordinate orientation)
        diff = np.diff(pts, axis=1)
        extremities[1] = pts[np.argmin(diff)]
    
        # 4. Bottom-Left: Largest difference (x - y)
        extremities[3] = pts[np.argmax(diff)]
    
        return extremities
    
    points = [[glx.x, glx.y] for glx in closest]
    names = [item.name for item in closest]
    extremities = get_extremities(points)
    for p in extremities:
        seed = gen.find_planet(*p)
        name = gen.get_planet_name(seed)
        print(f"{name} at ({p[0]}, {p[1]}")
             
    # Initial seed for Galaxy 1 (Tibedied / System 0)
    tibedied_seed = (0x5A4A, 0x0248, 0xB753)
    
