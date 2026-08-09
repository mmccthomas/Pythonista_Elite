# missions code
# mission briefing and debriefs are triggered on docking
# ship activity is triggered on random_encounter, every 4.25 seconds
# Missions
#
# No Name.       Planet Galaxy Score
# 1 Constrictor.  -     0,1.   256
# 2 Plans.        -     2.     1280
# 3 Cloaking.     -     2
# 4 Thargoid.     -     3.     1500
# 5 Supernova.    -     3
# 6 Asteroids  not Ceenge  5

from vector import Vector
import constants as cs
import random
from enum import Enum
import logging
logger = logging.getLogger(__name__)


class Mission(Enum):
    NONE = 0
    HUNT_1 = 1
    COMPLETE_1 = 2
    DEBRIEFED_1 = 3
    START_2 = 4
    BRIEFED_2 = 5
    COMPLETE_2 = 6
    START_3 = 7
    BRIEFED_3 = 8
    COMPLETE_3 = 9
    START_4 = 10
    BRIEFED_4 = 11
    COMPLETE_4 = 12
    FINISHED_4 = 13
    START_5 = 14
    BRIEFED_5 = 15
    COMPLETE_5 = 16
    FINISHED_5 = 17
    START_6 = 18
    BRIEFED_6 = 19
    COMPLETE_6 = 20
    FINISHED_6 = 21
    
    
ST_SETUP = 0   # Initialise and setup
ST_UPDATE = 1  # run rotating ship for intro1
planet_2_2 = 'Soiserla'
planet_3_1 = 'Ceisis'
planet_3_2 = 'Beisria'
planet_3_3 = 'Onenqu'
planet_4_1 = "Edtira"
planet_5_1 = "Edbedi"
planet_6_1 = "Ceenge"
planet_6_2 = "Ceorge"

STATION = 1
SUN = 2


def rand255():
   return random.randint(0, 255)


class MissionManager:
    def __init__(self, gs):
        self.gs = gs
        self.cmdr = gs.cmdr
        self.universe = gs.universe
        self.gfx = gs.gfx
        self.no_opposition = 10
        self.destroyed_opposition = 0
        self.generated = 0
        self.MAX_OPPOSITION = 10
        self.SPAWN_DISTANCE = 30000
        self.state = 0
        
        # Mission 1 Text (The Constrictor)
        self.m1_brief_a = (
            "Greetings Commander, I am Captain Carruthers of "
            "Her Majesty's Space Navy and I beg a moment of your "
            "valuable time. We would like you to do a little job "
            "for us. The ship you see here is a new model, the "
            "Constrictor, equipped with a top secret new shield "
            "generator. Unfortunately it's been stolen."
        )

        self.m1_brief_b = (
            "It went missing from our ship yard on Xeer five months ago "
            "and was last seen at Reesdice. Your mission should you decide "
            "to accept it, is to seek and destroy this ship. You are "
            "cautioned that only Military Lasers will get through the new "
            "shields and that the Constrictor is fitted with an E.C.M. "
            "System. Good Luck, Commander. ---MESSAGE ENDS."
        )

        self.m1_brief_c = (
            "It went missing from our ship yard on Xeer five months ago "
            "and is believed to have jumped to this galaxy. "
            "Your mission should you decide to accept it, is to seek and "
            "destroy this ship. You are cautioned that only Military Lasers "
            "will get through the new shields and that the Constrictor is "
            "fitted with an E.C.M. System. Good Luck, Commander. ---MESSAGE ENDS."
        )
        self.m1_debrief = (
                "You succeeded in your mission to destroy the Constrictor."
                "Please accept a reward of 10000 credits."
                "There will always be a place for you in Her Majesty's Space Navy."
                "---MESSAGE ENDS.")
                
        self.m2_brief_a = (
            "Attention Commander, I am Captain Fortesque of Her Majesty's Space Navy. "
            "We have need of your services again. If you would be so good as to go to "
            "Ceerdi you will be briefed.If successful, you will be rewarded."
            "---MESSAGE ENDS.")
            
        self.m2_brief_b = (
            "Good Day Commander. I am Agent Blake of Naval Intelligence. As you know, "
            "the Navy have been keeping the Thargoids off your ass out in deep space "
            "for many years now. Well the situation has changed. Our boys are ready "
            "for a push right to the home system of those murderers."
            "I have obtained the defence plans for their Hive Worlds. The beetles "
            "know we've got something but not what. If I transmit the plans to our "
            f"base on {planet_2_2} they'll intercept the transmission. I need a ship to "
            "make the run. You're elected. The plans are unipulse coded within "
            "this transmission. You will be paid. Good luck Commander. ---MESSAGE ENDS.")
        
        self.m2_debrief = (
            "Well done Commander."
            "You have served us well and we shall remember. "
            "We did not expect the Thargoids to find out about you."
            "For the moment please accept this Navy Extra Energy Unit as payment. "
            "---MESSAGE ENDS.")
            
        self.m3_brief_a = (
                "Attention Commander, I am Captain Fortesque of Her Majesty's Space Navy. "
                "We have need of your services again. If you would be so good as to go to "
                f"{planet_3_1} you will be briefed."
                "If successful, you will be rewarded."
                "---MESSAGE ENDS.")
                
        self.m3_brief_b = (
                "We would like you retrieve some Alien technology stolen from our research station on this planet."
                "We understand that the perpetrators are in three Asp Mk2s,"
                "and the Alien tech is split between the three ships."
                "Your mission should you decide to accept it, is to seek and destroy these ships "
                f"and retrieve the cargo. They were last seen at {planet_3_2}"
                "Good Luck, Commander. ---MESSAGE ENDS."
            )
            
        self.m3_debrief = (
            "Well done Commander."
            "You have served us well and we shall remember. "
            "We have generated a new cloaking device and fitted it to your ship."
            "---MESSAGE ENDS.")
            
        self.m4_brief = (
            "Attention Commander, Captain Fortesque of Her Majesty's Space Navy."
            "We have need of your services again."
            f"We have a situation in {planet_4_1}, in which a large number of Thargoids"
            " are attacking our station. You have proved yourself very capable."
            "Destroy all the Thargoid motherships"
            f"We believe there are {self.MAX_OPPOSITION} near to the station."
            "Please help. If successful and you survive, you will be well rewarded."
            "---MESSAGE ENDS.")
            
        self.m4_debrief = (
            "Well done Commander.You have served us well and we shall remember."
            "Your legal status has been reset and you have been awarded 10,000 credits."
            "---MESSAGE ENDS.")
            
        self.m5_brief = (
            "Attention Commander."
            "We have need of your services again."
            f"The sun at {planet_5_1} is going supernova."
            "The last group of human refugees are gathered in the Coriolis station."
            "Please rescue them."
            "Time is of the essence, any delay will be disastrous for all."
            "---MESSAGE ENDS.")
            
        self.m5_debrief = (
            "Well done Commander."
            "All the refugees are extremely grateful."
            "Please accept our rescued gem stones."
            "---MESSAGE ENDS.")
            
        self.m6_brief = (
            "Attention Commander, Captain Fortesque of Her Majesty's Space Navy."
            "We have need of your services again."
            f"We have a situation in {planet_6_2}, in which our station is under bombardment from an asteroid storm."
            "Use your skills to protect the station."
            f"We believe there are {self.MAX_OPPOSITION} near to the station."
            "Please help."
            "---MESSAGE ENDS.")
            
        self.m6_debrief = (
            "Well done Commander.You have saved the station and we shall remember."
            "You have been awarded 10,000 credits."
            "---MESSAGE ENDS.")
            
    def in_mission(self):
        # allow spawning near station
        
        return Mission(self.gs.cmdr.mission) in (Mission.BRIEFED_4,
                                                 Mission.BRIEFED_5,
                                                 Mission.BRIEFED_6)
                    
    def get_mission_planet_desc(self):
        """
        Returns special mission-related text when visiting specific planets.
        Matches the pnum logic from missions.c
        called from planets.py in description
        """
        if Mission(self.gs.cmdr.mission) == Mission.HUNT_1:
            name = self.gs.present_planet.name
            match self.gs.cmdr.galaxy_number:
                case 0:
                    mapping = {'Xeer': 0, 'Reesdice': 1, 'Arexe': 2}
                    if name in mapping:
                        return self.m1_pdesc[mapping[name]]
                case 1:
                    # Clues scattered across Galaxy 2
                    mapping = {'Bebege': 3, 'Cearso': 3, 'Dicela': 3, 'Eringe': 3,
                               'Gexein': 3, 'Isarin': 3, 'Letibema': 3, 'Maisso': 3,
                               'Onen': 3, 'Ramaza': 3, 'Sosole': 3, 'Tivere': 3, 'Veriar': 3,
                               'Errius': 4, 'Inbibe': 5, 'Ausar': 6, 'Usleri': 7, 'Orarra': 8}
                    if name in mapping:
                        return self.m1_pdesc[mapping[name]]
                case  2:
                    return self.m1_pdesc[9]

        return None

    def constrictor_briefing(self):
        """Displays the scrolling text and rotating ship for Mission 1.
        State machine handles setup and run states
        Entry assumes universe has been ckeared previously"""
        if self.gs.swat.universe[0].type == 0:
            self.state = ST_SETUP
            
        if self.state == ST_SETUP:
                        
            self.gfx.clear_display()
            self.gfx.display_centre_text(0, "INCOMING MESSAGE", color=cs.GOLD)
            self.gfx.display_pretty_text(0, 3, self.m1_brief_a)
            
            brief_end = self.m1_brief_b if self.gs.cmdr.galaxy_number == 0 else self.m1_brief_c
            self.gfx.display_pretty_text(0, 10, brief_end)
            self.gfx.display_centre_text(cs.NUM_LINES-1, "Press OK to continue.", color=cs.GOLD)
    
            # Set up a rotating Constrictor in the display area
            self.gs.swat.clear_universe()
            self.gs.swat.add_new_ship(cs.SHIP_CONSTRICTOR, 0, -50, 600, None, -127, -127)
            # Keep ship at fixed distance for viewing
            self.gs.universe[0].location.z = 600
            self.gfx.update_screen()
            self.state = ST_UPDATE
            
        if self.state == ST_UPDATE:
            # Set a constant roll for the intro effect
            current_obj = self.universe[0]
            # Keep ship at fixed distance for viewing
            self.gs.universe[0].location.z = 600
            # current_obj.rotx += 0.5  # flight_yaw = 0.5 unit per cycle
            # current_obj.rotz += 0.5  # flight_roll = 0.5
            self.gs.space.update_universe()
            #self.gs.swat.update_model(current_obj)
            
    def constrictor_debrief(self):
        if self.state == ST_SETUP:
            logger.debug('')
            self.gs.cmdr.mission = Mission.DEBRIEFED_1.value
            self.gs.cmdr.score += 256
            self.gs.cmdr.credits += 100000  # 10000.0 Credits
            self.display_brief(self.m1_debrief)
            
    def thargoid_debrief(self):
        if self.state == ST_SETUP:
            self.gs.cmdr.score += 256
            self.gs.cmdr.energy_unit = 2
            self.display_brief(self.m2_debrief)
            
    def cloaking_debrief(self):
        if self.state == ST_SETUP:
            self.gs.cmdr.score += 256
            self.gs.cmdr.cloaking_device = True
            self.gs.keypad.key_change('N/A', name='Cloaking On', color='lightgreen')
            self.display_brief(self.m3_debrief)
            
    def thargoid_invasion_debrief(self):
        if self.state == ST_SETUP:
            self.gs.cmdr.score += 256
            self.gs.cmdr.credits += 100000
            self.gs.cmdr.legal_status = 0
            self.gs.space.scanner_scale = 256
            self.display_brief(self.m4_debrief)
            
    def supernova_debrief(self):
        if self.state == ST_SETUP:
            self.gs.cmdr.current_cargo = [0] * 17
            self.gs.cmdr.current_cargo[15] = 250
            self.display_brief(self.m5_debrief)
            
    def asteroid_debrief(self):
        if self.state == ST_SETUP:
            self.gs.cmdr.score += 256
            self.gs.cmdr.credits += 100000
            self.gs.space.scanner_scale = 256
            self.display_brief(self.m6_debrief)
                            
    def check_destroy(self, ship):
       # special case of destroyed ship in missions
       
       if ship.type == cs.SHIP_CONSTRICTOR:
           self.gs.cmdr.mission = Mission.COMPLETE_1.value
       if (Mission(self.gs.cmdr.mission) == Mission.BRIEFED_4
               and ship.type == cs.SHIP_THARGOID):
           self.destroyed_opposition += 1
           self.gs.msg.text = f'Destroyed {self.destroyed_opposition}/{self.MAX_OPPOSITION} Thargoids'
           if self.destroyed_opposition >= self.MAX_OPPOSITION:
               self.gs.cmdr.mission = Mission.COMPLETE_4.value
               self.gs.msg.text = 'All Thargoids destroyed'
       elif Mission(self.gs.cmdr.mission) == Mission.BRIEFED_6:
           if ship.type == cs.SHIP_ASTEROID:
               self.destroyed_opposition += 1
               self.gs.msg.text = f'Destroyed {self.destroyed_opposition}/{self.MAX_OPPOSITION} Asteroids'
               if self.destroyed_opposition >= self.MAX_OPPOSITION:
                   self.gs.cmdr.mission = Mission.COMPLETE_6.value
                   self.gs.msg.text = 'All asteroids destroyed'
           elif ship.type == cs.SHIP.CORIOLIS:
               self.gs.msg.text = 'Station Destroyed. Mission Failed'
       logger.debug(f'destroyed {ship.name} {self.destroyed_opposition}')
               
    def swarm_attack(self, ship_type, target_index, velocity=1,
                     offset=Vector(0, 0, 0), flyby=False, sequential=0):
        # create a swarm of enemies to attack the station
        # they can either target the station or an offset to fly by.
        gs = self.gs
        target = gs.universe[target_index]
        
        while gs.swat.ship_count[ship_type] < (self.MAX_OPPOSITION - self.destroyed_opposition):
         
            opp_offset = Vector(random.randint(-self.SPAWN_DISTANCE, self.SPAWN_DISTANCE),
                                random.randint(-self.SPAWN_DISTANCE, self.SPAWN_DISTANCE),
                                random.randint(-self.SPAWN_DISTANCE, self.SPAWN_DISTANCE))
            
            opposition_position = target.location + opp_offset
 
            newship = gs.swat.spawn_homing_object(ship_type, opposition_position,
                                                  target_index, velocity,
                                                  offset=offset,
                                                  flyby=flyby,
                                                  sequential=sequential)
            if newship == -1:  # universe is full
                break
            gs.swat.ship_list[ship_type].max_loot = 0
            self.generated += 1
            gs.universe[newship].name += f' {self.generated}'
       
        all_swarm = [ship for ship in gs.universe
                     if ship.flags & cs.FLG_SEEKER]
        # ensure at least one of the swarm is moving
        # waiting ships are  not flying by
        waiting_swarm = [ship for ship in all_swarm
                         if not ship.flyby_locked]
        # start a random swarm ship
        if waiting_swarm:
            if all([ship.velocity == 0 for ship in waiting_swarm]):
               for i in range(sequential):
                  try:
                      waiting_swarm[i].velocity = velocity
                  except IndexError:
                      pass
        if not all_swarm:
            return True
            
    def spawn_ship(self):
        # triggered every 4.25 seconds
        # lone hunter on missions
        gs = self.gs
        # logger.error(f'{Mission(gs.cmdr.mission)} {gs.cmdr.galaxy_number} {gs.present_planet.name}')
        match Mission(gs.cmdr.mission):
            case Mission.HUNT_1:
                if (gs.cmdr.galaxy_number == 1
                        and gs.present_planet.name == 'Orarra'
                        and gs.swat.ship_count.get(cs.SHIP_CONSTRICTOR, 0) == 0):
                    return cs.SHIP_CONSTRICTOR
            
            case Mission.BRIEFED_2:
                if rand255() >= 220:
                    return cs.SHIP_THARGOID
            
            case Mission.BRIEFED_3:
                if rand255() >= 220:
                    # 3 Asps
                    no_asps = gs.swat.ship_count.get(cs.SHIP_ASP2, 0)
                    if no_asps < 1:
                        for _ in range(1 - no_asps):
                           z = 12000
                           x = random.randint(-1024, 1024)
                           y = random.randint(-1024, 1024)
                           if rand255() > 127:
                               x = -x
                           if rand255() > 127:
                               y = -y
                           ship_type = cs.SHIP_ASP2
                           newship = gs.swat.add_new_ship(ship_type, x, y, z, None, 0, 0)
                           if newship != -1:
                               # give these asps a cargo
                               gs.swat.ship_list[cs.SHIP_ASP2].max_loot = 1
                               gs.universe[newship].flags = cs.FLG_ANGRY
                               if rand255() > 245:
                                   self.gs.universe[newship].flags |= cs.FLG_HAS_ECM
                               gs.universe[newship].bravery = ((rand255() * 2) | 64) & 127
                               gs.swat.in_battle += 1
                    
            case Mission.BRIEFED_4:
                if gs.present_planet.name == planet_4_1:
                    # produce a swarm of thargoids, , targetted near the station.
                    # slowly reducing as you kill.
                    # get attrition by distance
                    # logger.error('')
                    gs.space.scanner_scale = 128
                    finished = self.swarm_attack(cs.SHIP_THARGOID, STATION, velocity=5,
                                                 offset=Vector(0, 0, -1000),
                                                 flyby=True, sequential=2)
                    if finished:
                        self.gs.cmdr.mission = Mission.COMPLETE_4.value
                        self.gs.msg.text = 'All Thargoids destroyed'
                                        
            case Mission.BRIEFED_5:
                # place escaping boas
                if gs.present_planet.name == planet_5_1:
                    return cs.SHIP_BOA
                    
            case Mission.BRIEFED_6:
                if gs.present_planet.name == planet_6_2:
                    # produce a number of  asteroids, targetted at the station
                    # slowly reducing as you kill.
                    # get attrition by distance
                    self.SPAWN_DISTANCE = 30000
                    gs.swat.HOMING_DAMAGE = 10
                    gs.space.scanner_scale = 128
                    finished = self.swarm_attack(cs.SHIP_ASTEROID, STATION,
                                                 velocity=5, sequential=1)
                    if finished:
                        self.gs.cmdr.mission = Mission.COMPLETE_6
                        self.gs.msg.text = 'All Asteroids destroyed'
                    
    def scoop_cargo(self, obj):
        if (obj.type == cs.SHIP_CARGO
                and obj.parent == cs.SHIP_ASP2
                and Mission(self.gs.cmdr.mission) == Mission.BRIEFED_3):
           self.gs.cmdr.current_cargo[cs.ALIEN_ITEMS_IDX] += 1
           self.gs.info_message("Scooped: Cloaking Device")
           
    def system_arrival(self):
        # mission specific arrngements when we arrive in system
        if (Mission(self.gs.cmdr.mission) == Mission.BRIEFED_5
                and self.gs.present_planet.name == planet_5_1):
            # sun moves closer to planet by 1km / secs
            # make everthing Red
            sun = self.gs.universe[SUN]
            self.gs.renderer.hue_shift = 0.9
            rotmat = self.gs.swat.rotmat_facing(sun.location, self.gs.universe[STATION].location)
            sun.rotmat = rotmat
            sun.velocity = 10
        else:
            self.gs.renderer.hue_shift = 0
                        
    def mission1_message(self):
        # clues to mission 1
        if Mission(self.gs.cmdr.mission) == Mission.HUNT_1:
            mission_text = self.get_mission_planet_desc()
            if mission_text is not None:
                self.gs.gfx.display_centre_text(1, 'Incoming Message', color=cs.RED)
                return mission_text
        self.gs.in_dock.incoming_message = ''
        
    def display_brief(self, brief):
        if self.state == ST_SETUP:
            self.state = ST_UPDATE
        if self.state == ST_UPDATE:
            self.gfx.clear_display()
            self.gfx.display_centre_text(0, "INCOMING MESSAGE", 140, cs.GOLD)
            self.gfx.display_pretty_text(0, 3, brief)
            self.gfx.display_centre_text(cs.NUM_LINES-1, "Press OK to continue.", 140, cs.GOLD)
            self.gfx.update_screen()
                          
    def check_mission_brief(self, present_planet):
        """
        Main logic gate for triggering missions based on score and location.
        Triggered when player docks
        """
        gs = self.gs
        self.cmdr = self.gs.cmdr
        score = self.cmdr.score
        gal_num = self.cmdr.galaxy_number
        
        match Mission(self.cmdr.mission):
         
            case Mission.NONE:
                # Trigger Mission 1:
                if score >= 256 and gal_num < 2:
                    self.constrictor_briefing()
                    return Mission.HUNT_1
                    
            case Mission.COMPLETE_1:
                self.constrictor_debrief()
                return Mission.DEBRIEFED_1
                
            case Mission.DEBRIEFED_1:
                # Trigger Mission 2
                if score >= 1280 and gal_num == 2:
                    self.display_brief(self.m2_brief_a)
                    return Mission.START_2
                    
            case Mission.START_2:
                # Trigger Mission 2 Part 2:
                if present_planet.name == 'Ceerdi':
                    self.display_brief(self.m2_brief_b)
                    return Mission.BRIEFED_2
                    
            case Mission.BRIEFED_2:
                # Trigger Mission 2 End: Reach end planet
                if present_planet.name == 'Soiserla':
                    self.thargoid_debrief()
                    return Mission.COMPLETE_2
                    
            case Mission.COMPLETE_2:
                # Trigger Mission 3
                if gal_num == 2:
                    # self.state = ST_SETUP
                    self.display_brief(self.m3_brief_a)
                    return Mission.START_3
              
            case Mission.START_3:
                # Trigger Mission 3 Part 2: Reach 1st waypoint
                if present_planet.name == planet_3_1:
                    self.display_brief(self.m3_brief_b)
                    return Mission.BRIEFED_3
                    
            case Mission.BRIEFED_3:
                # Trigger Mission 3 End: Reach end planet
                if (present_planet.name == planet_3_2
                        and self.cmdr.current_cargo[cs.ALIEN_ITEMS_IDX] >= 3):
                    self.cloaking_debrief()
                    return Mission.COMPLETE_3
                       
            case Mission.COMPLETE_3:
                # Trigger Mission 4 :
                if score >= 1500 and gal_num == 3:
                    self.MAX_OPPOSITION = 10
                    self.destroyed_opposition = 0
                    self.display_brief(self.m4_brief)
                    self.state = ST_SETUP
                    return Mission.BRIEFED_4
                    
            case Mission.COMPLETE_4:
                self.thargoid_invasion_debrief()
                return Mission.FINISHED_4
                
            case Mission.FINISHED_4:
                # Trigger Mission 5 :
                if gal_num == 3:
                    self.display_brief(self.m5_brief)
                    self.state = ST_SETUP
                    return Mission.BRIEFED_5
                    
            case Mission.BRIEFED_5:
                if gs.present_planet.name == planet_5_1:
                    # clear the cargo hold(!) and fill with refugees
                    # oops, no fuel available
                    gs.cmdr.current_cargo = [0] * 17 + [250]
                    gs.in_dock.fuel_available = False
                    gs.input_queue.put('OK')
                    gs.input_queue.put('Status')
                    return Mission.COMPLETE_5
                    
            case Mission.COMPLETE_5:
                if gs.present_planet.name != planet_5_1:
                    self.supernova_debrief()
                    self.gs.in_dock.fuel_available = True
                    return Mission.FINISHED_5
                    
            case Mission.FINISHED_5:
                # Trigger Mission 6 :
                if (gal_num == 5 and gs.present_planet.name != planet_6_1):
                    self.MAX_OPPOSITION = 10
                    self.destroyed_opposition = 0
                    self.generated = 0
                    self.display_brief(self.m6_brief_a)
                    self.state = ST_SETUP
                    return Mission.BRIEFED_6
                    
            case Mission.COMPLETE_6:
                self.asteroid_debrief()
                return Mission.FINISHED_6
                                                    
        self.gs.current_screen = cs.SCR_PLANET_DATA
