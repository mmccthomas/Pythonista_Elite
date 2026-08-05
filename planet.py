from elite import GalaxySeed
from types import SimpleNamespace
import math
from vector import Vector
import constants as cs
import numpy as np


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
            ["funny", "weird", "unusual", "strange", "peculiar"],
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
        
    def next_galaxy(self, seed: GalaxySeed):

        def rotate_byte_left(x):
            return ((x << 1) | (x >> 7)) & 0xFF
        new_seed = seed.copy()
        for attr in ('a', 'b', 'c', 'd', 'e', 'f'):
            setattr(new_seed, attr,
                    rotate_byte_left(getattr(seed, attr)))
        return new_seed
        
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
        description = None
        self.rnd_a, self.rnd_b = seed.c, seed.d
        self.rnd_c, self.rnd_d = seed.e, seed.f
        try:  # to allow testing
            description = self.gs.missions.mission_message()
        except AttributeError:
            pass
        # name = self.get_planet_name(seed)
        if description is None:
            description = self.expand_description("<14> is <22>.", seed.name)
        return description

    def find_planet(self, cx, cy, galaxy_seed):

        min_dist = 10000
  
        glx = galaxy_seed.copy()
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
        
    def get_planet_list(self, seed):
        # list all 256 systems
        
        glx = seed.copy()
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
            
            planets.append(SimpleNamespace(**planet))
        return planets
            
    def get_closest_planets(self, galaxy_seed, current_glx, max_distance=None):
        # list all 256 systems
        glx = galaxy_seed.copy()
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
            planet['tech'] = planet['glx'].tech
            planets.append(SimpleNamespace(**planet))
        sorted_planets = sorted(planets, key=lambda x: x.distance)
        if max_distance is not None:
            sorted_planets = [planet for planet in sorted_planets
                              if planet.distance <= max_distance]
        return sorted_planets
        
    def get_planet_route(self, current_planet_name, target_planet_name, seed):
        """ Find a route between two planet names within fuel range of each planet """
        
        planets = self.get_planet_list(seed)
        locations = np.array([[planet.x, planet.y] for planet in planets])
        names = [planet.name for planet in planets]
        num_locations = len(locations)
        start_node = names.index(current_planet_name)
        end_node = names.index(target_planet_name)

        threshold = 7

        # 2. Build adjacency list (Graph represented as a dictionary)
        adj = {i: [] for i in range(num_locations)}
        for i in range(len(locations)):
            for j in range(i + 1, len(locations)):
             if cs.CLASSIC_DISTANCE:
                x1, y1 = locations[i]
                x2, y2 = locations[j]
                dx, dy = abs(x1-x2), abs(y1-y2)
                
                dist = math.sqrt(dx**2 + 0.25 * dy**2) * 4 / 10
                # print(names[i], names[j], i, j, dist)
             else:
                dist = math.dist(locations[i], locations[j]) * 4
             if dist <= threshold:
                 adj[i].append(j)
                 adj[j].append(i)
        
        # 3. Breadth-First Search to find the path
        def find_path(start, end, graph):
            queue = [[start]]
            visited = {start}
            
            while queue:
                path = queue.pop(0)
                node = path[-1]
                
                if node == end:
                    return path, visited
                    
                for neighbor in graph[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        new_path = list(path)
                        new_path.append(neighbor)
                        queue.append(new_path)
            # if the queue is empty, return None and all reachable nodes
            return None, visited

        def planet_name(index, seed):
            return self.find_planet(locations[index][0],
                                    locations[index][1],
                                    seed).name
        # adj_names = {planet_name(k, seed) : [planet_name(v1, seed) for v1 in v] for k, v in adj.items()}
        # print(adj_names)
        path, visited_nodes = find_path(start_node, end_node, adj)
        if path:
            pathnames = [names[index] for index in path]
            return path, pathnames, None
        else:
            # Get coordinates of target
            target_coords = locations[end_node]
            
            # Calculate distance from all visited nodes to target
            # We want the one with the smallest distance to the target
            min_dist = float('inf')
            closest_reachable = None
            
            for i in visited_nodes:
                dist = math.dist(locations[i], target_coords)
                if dist < min_dist:
                    min_dist = dist
                    closest_reachable = names[i]
                    
            return None, [], closest_reachable
        
    def plot_path(self, path, seed):
        if path:
            planets = self.get_planet_list(seed)
            locations = np.array([[planet.x, planet.y] for planet in planets])
            plt.figure(figsize=(8, 8))
            # Plot all points
            plt.scatter([p[0] for p in locations], [p[1] for p in locations], s=5, c='gray')
            
            # Plot the path
            path_x = [locations[i][0] for i in path]
            path_y = [locations[i][1] for i in path]
            plt.plot(path_x, path_y, 'r-', marker='o', markersize=4)
            
            plt.title("Route Found via BFS")
            plt.show()
        else:
            print("No path found.")
        
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
        
if __name__ == '__main__':
    # --- Example Usage ---
    # Lave (starting planet) seed in Galaxy 1
    import matplotlib.pyplot as plt
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
    # print(f"Planet Name: {gen.get_planet_name(lave_seed)}")
    # print(f"Stats: {gen.generate_planet_stats(lave_seed)}")
    # print(f"Description: {gen.describe_planet(lave_seed)}")
    print()
    # Test get_planet_name
    system_list = [([0x87AA, 0x0C38, 0x8053], 'Ra'),
                   ([0x2800, 0x1CC0, 0x4F4D], 'Ara'),
                   ([0xAD38, 0x149C, 0x151D], 'Lave'),
                   ([0x597A, 0xA4F0, 0xEFA3], 'Arexe'),
                   ([0x9580, 0xB8A0, 0x70DA], 'Errius'),
                   ([0x99C0, 0x8F08, 0x63BD], 'Geinona'),
                   ([0x5A4A, 0x0248, 0xB753], 'Tibedied')]
    # check specific set of planets as listed in deep dive article
    galaxy = GalaxySeed().copy()
    for system in system_list:
        current_seed, planet_name = system
        galaxy.to_galaxy(current_seed)
        name = gen.get_planet_name(galaxy)
        assert (name == planet_name)
        start_seed_str = ", ".join([f"0x{s:#06x}" for s in current_seed])
        # print(f'{start_seed_str} Expected name {planet_name:<8} returned name {name}')
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
        # print(f"System {i:<3}: {name:<12} | Seed: {seed_str} | Colour: {glx.colour}")
    assert ('Lave' in planet_names)
    assert ('Tibedied' in planet_names)
    assert ('Diso' in planet_names)
    print()
    # closest to Lave
    current_glx = GalaxySeed(0xAD, 0x38, 0x14, 0x9c, 0x15, 0x1d)
    closest = gen.get_closest_planets(GalaxySeed(), current_glx, max_distance=None)
    # closest = sorted(closest, key = lambda x: x.tech)
    [print(planet) for planet in closest]
    x_locs = [planet.x for planet in closest]
    y_locs = [planet.y for planet in closest]
    # print(f'{min(x_locs)=}, {max(x_locs)=}, {np.mean(x_locs)=:.0f}')
    # print(f'{min(y_locs)=}, {max(y_locs)=}, {np.mean(y_locs)=:.0f}')
    new_seed = gen.next_galaxy(GalaxySeed())
    
    closest = gen.get_closest_planets(new_seed, new_seed, max_distance=None)
    # print('Galaxy 2')
    # [print(planet) for planet in closest]
    seed = gen.find_planet(0x60, 0x60, new_seed)
    # print(gen.get_planet_name(seed))
    
    # sorted_planets = dict(sorted(planets.items(), key=lambda x: x[1].distance))
    # print(sorted_planets.keys())
    # get planet name and coords at each corner
        
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
        seed = gen.find_planet(*p, GalaxySeed())
        name = gen.get_planet_name(seed)
        # print(f"{name} at ({p[0]}, {p[1]}")
             
    # Initial seed for Galaxy 1 (Tibedied / System 0)
    tibedied_seed = (0x5A4A, 0x0248, 0xB753)
    
    planets = gen.get_planet_list(GalaxySeed())
    # for i, planet in enumerate(planets):
    #    print(i, planet.name)
    
    new_seed = gen.next_galaxy(GalaxySeed())
    # print(new_seed)
    planets = gen.get_planet_list(new_seed)
    # for i, planet in enumerate(planets):
    #     print(i, planet.name, planet.glx.tech)
    new_seed = gen.next_galaxy(new_seed)
    # print(new_seed)
    planets = gen.get_planet_list(new_seed)
    # for i, planet in enumerate(planets):
    #    print(i, planet.name, planet.glx.tech)
        
    path, pathnames, _ = gen.get_planet_route('Lave', 'Ribilebi', GalaxySeed())
    print(pathnames)
    gen.plot_path(path, GalaxySeed())
    new_seed = gen.next_galaxy(GalaxySeed())
    new_seed = gen.next_galaxy(new_seed)

    path, pathnames, _ = gen.get_planet_route('Birera', 'Dicemari', new_seed)
    print(pathnames)
    gen.plot_path(path, GalaxySeed())
    new_seed = GalaxySeed(210, 82, 16, 66, 189, 154)
    
    glx = new_seed.copy()     
    min_dist = 1e6
    for i in range(255):
                    
         for _ in range(4):
             glx.waggle()
         
         planet_loc, sun_loc =get_solar_system_vectors(glx)
         dist =  Vector(*planet_loc) - Vector(*sun_loc)
         dist = dist.magnitude
         if dist < min_dist:
            min_dist = dist
            name = glx.name
            glxmin = glx.copy()
         print(f'{glx.name}, {dist/1000:.1f}k')
    print('min', name, min_dist/1000, glxmin)
    new_seed = gen.next_galaxy(new_seed)
    print(new_seed.name, new_seed)
