import vector
from vector import Vector, unit_vector, vector_dot_product
import constants as cs

class Pilot:
    """
    The auto-pilot logic for docking and NPC navigation.
    Based on Elite - The New Kind (C.J. Pinder).
    """
    
    def __init__(self, gs):
        self.universe = gs.universe
        self.auto_pilot_active = False
        self.gs = gs

    def fly_to_vector(self, ship, vec):
        """
        Calculates the necessary rotation and acceleration for a ship
        to point toward and move to a specific vector.
        """
        rat = 0.1 # 3
        rat2 = 0.1666
        cnt2 = 0.8055

        # Get normalized vector to target
        nvec = unit_vector(vec)
        
        # direction: dot product with ship forward vector (rotmat[2])
        # Tells us if the target is in front of or behind us
        direction = vector_dot_product(nvec, ship.rotmat[2])
        
        if direction < -0.6666:
            rat2 = 0

        # dir: dot product with ship up vector (rotmat[1])
        dir_up = vector_dot_product(nvec, ship.rotmat[1])

        # If target is far behind, perform a hard turn
        if direction < -0.861:
            ship.rotx = 7 if dir_up < 0 else -7
            ship.rotz = 0
            return

        ship.rotx = 0
        # TODO these are very bang bang , woukd like to smooth
        # Pitch control
        if (abs(dir_up) * 2) >= rat2:
            ship.rotx = rat if dir_up < 0 else -rat
            
        # Roll control
        if abs(ship.rotz) < 16:
            # dot product with ship side vector (rotmat[0])
            dir_side = vector_dot_product(nvec, ship.rotmat[0])
            ship.rotz = 0

            if (abs(dir_side) * 2) >= rat2:
                ship.rotz = rat if dir_side < 0 else -rat
                if ship.rotx < 0:
                    ship.rotz = -ship.rotz

        # Acceleration control
        if direction <= -0.167:
            ship.acceleration = -1
        elif direction >= cnt2:
            ship.acceleration = 3

    def fly_to_planet(self, ship):
        """Points the ship toward the planet (Universe object 0)."""
        planet = self.universe[0]
        vec = planet.location - ship.location
        self.fly_to_vector(ship, vec)

    def fly_to_station_front(self, ship):
        """
        Points the ship toward a spot 768 units in front
        of the station's docking bay.
        """
        station = self.universe[1]
        vec = station.location - ship.location

        # Offset target point using the station's forward orientation (rotmat[2])
        vec.x += station.rotmat[2].x * 768
        vec.y += station.rotmat[2].y * 768
        vec.z += station.rotmat[2].z * 768

        self.fly_to_vector(ship, vec)

    def fly_to_station(self, ship):
        """Points the ship directly toward the space station."""
        station = self.universe.objects[1]
        vec = station.location - ship.location
        self.fly_to_vector(ship, vec)

    def fly_to_docking_bay(self, ship):
        """Final docking stage: Fly straight into the slot."""
        station = self.universe.objects[1]
        diff = ship.location - station.location
        vec = unit_vector(diff)

        ship.rotx = 0
        
        # Logic for NPC ships or player during final approach
        if ship.is_player or ship.type < 0:
            ship.rotz = 1
            if (vec.x >= 0 and vec.y >= 0) or (vec.x < 0 and vec.y < 0):
                ship.rotz = -ship.rotz

            if abs(vec.x) >= 0.0625:
                ship.acceleration = 0
                ship.velocity = 1
                return

            if abs(vec.y) > 0.002436:
                ship.rotx = -1 if vec.y < 0 else 1

            if abs(vec.y) >= 0.0625:
                ship.acceleration = 0
                ship.velocity = 1
                return

        ship.rotz = 0
        # Check alignment with the bay's slot
        dir_align = vector_dot_product(ship.rotmat[0], station.rotmat[1])

        if abs(dir_align) >= 0.9166:
            ship.acceleration += 1
            ship.rotz = 127  # Rapid roll to match station rotation
            return

        ship.acceleration = 0
        ship.rotz = 0

    def auto_pilot_ship(self, ship):
        """The main decision engine for an automated ship."""
        
        # If no station exists or forced to fly to planet
        if (ship.flags & cs.FLG_FLY_TO_PLANET) or self.universe[1].type not in (cs.SHIP_CORIOLIS, cs.SHIP_DODEC):
            self.fly_to_planet(ship)
            return

        station = self.universe[1]
        diff = ship.location - station.location
        dist_ = diff.magnitude

        # If very close, the ship has officially 'docked'
        if dist_ < 160:
            ship.flags |= cs.FLG_REMOVE
            return
        
        vec = unit_vector(diff)
        # dir_to_bay: check if we are positioned in front of the bay slot
        dir_to_bay = vector_dot_product(station.rotmat[2], vec)

        if dir_to_bay < 0.9722:
            self.fly_to_station_front(ship)
            return

        # Check if ship is facing the station
        dir_facing = vector_dot_product(ship.rotmat[2], vec)

        if dir_facing < -0.9444:
            self.fly_to_docking_bay(ship)
            return

        self.fly_to_station(ship)

    def engage_auto_pilot(self):
        """Activates the docking computer and plays Blue Danube."""
        # Condition checks: not already on, not in witchspace, etc.
        self.auto_pilot_active = True
        # play_midi("BLUE_DANUBE")

    def disengage_auto_pilot(self):
        """Deactivates docking computer and stops music."""
        self.auto_pilot_active = False
        # stop_midi()
