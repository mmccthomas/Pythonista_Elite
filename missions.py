from vector import Vector
import constants as cs
import random
import logging
logger = logging.getLogger(__name__)
# Mission State Constants
MISSION_NONE = 0
MISSION_1_HUNT = 1
MISSION_1_COMPLETE = 2
MISSION_1_DEBRIEFED = 3
MISSION_2_START = 4
MISSION_2_BRIEFED = 5
MISSION_2_COMPLETE = 6
MISSION_3_START = 7
MISSION_3_BRIEFED = 8
MISSION_3_COMPLETE = 9
MISSION_4_START = 10
MISSION_4_BRIEFED = 11
MISSION_4_COMPLETE = 12
MISSION_4_FINISHED = 13
MISSION_5_START = 14
MISSION_5_BRIEFED = 15
MISSION_5_COMPLETE = 16
ST_SETUP = 0   # Initialise and setup
ST_UPDATE = 1  # run rotating ship for intro1
planet_2_2 = 'Soiserla'
planet_3_1 = 'Ceisis'
planet_3_2 = 'Beisria'
planet_3_3 = 'Onenqu'
planet_4_1 = "Edtira"
planet_5_1 = "Edbedi"
MAX_THARGOIDS = 10
SPAWN_DISTANCE = 30000
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
        self.no_thargoids = 10
        self.destroyed_thargoids = 0
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

        self.m1_pdesc = [
            "THE CONSTRICTOR WAS LAST SEEN AT REESDICE, COMMANDER.",  # 0
            "A STRANGE LOOKING SHIP LEFT HERE A WHILE BACK. LOOKED BOUND FOR AREXE.",  # 1
            "YEP, AN UNUSUAL NEW SHIP HAD A GALACTIC HYPERDRIVE FITTED HERE, USED IT TOO.",  # 2
            "I HEAR A WEIRD LOOKING SHIP WAS SEEN AT ERRIUS.",  # 3
            "THIS STRANGE SHIP DEHYPED HERE FROM NOWHERE, SUN SKIMMED AND JUMPED. I HEAR IT WENT TO INBIBE.",  # 4
            "ROGUE SHIP WENT FOR ME AT AUSAR. MY LASERS DIDN'T EVEN SCRATCH ITS HULL.",  # 5
            "OH DEAR ME YES. A FRIGHTFUL ROGUE WITH WHAT I BELIEVE YOU PEOPLE CALL A LEAD. POSTERIOR SHOT UP LOTS OF THOSE BEASTLY PIRATES AND WENT TO USLERI.",  # 6
            "YOU CAN TACKLE THE VICIOUS SCOUNDREL IF YOU LIKE. HE'S AT ORARRA.",  # 7
            "THERE'S A REAL DEADLY PIRATE OUT THERE.",  # 8
            "BOY ARE YOU IN THE WRONG GALAXY!"  # 9
        ]
        self.m2_brief_a = (
            "Attention Commander, I am Captain Fortesque of Her Majesty's Space Navy. "
            "We have need of your services again. If you would be so good as to go to "
            "Ceerdi you will be briefed.If successful, you will be rewarded."
            "---MESSAGE ENDS.")
            
        self.m1_debrief = (
                "Congratulations Commander!"
                "You succeeded in your mission to destroy the Constrictor."
                "Please accept a reward of 10000 credits."
                "There will always be a place for you in Her Majesty's Space Navy."
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
            
        self.m4_brief_a = (
            "Attention Commander, Captain Fortesque of Her Majesty's Space Navy."
            "We have need of your services again."
            f"We have a situation in {planet_4_1}, in which a large number of Thargoids"
            " are attacking our station. You have proved yourself very capable."
            "Destroy all the Thargoid motherships"
            "We believe there are 10 near to the station."
            "Please help. If successful and you survive, you will be well rewarded."
            "---MESSAGE ENDS.")
            
        self.m4_debrief = (
            "Well done Commander.You have served us well and we shall remember."
            "Your legal status has been reset and you have been awarded 10,000 credits."
            "---MESSAGE ENDS.")
            
        self.m5_brief_a = (
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
            
    def in_mission(self):
        if self.gs.cmdr.mission == MISSION_4_BRIEFED:
            return True
        elif self.gs.cmdr.mission == MISSION_5_BRIEFED:
             return True
        return None
       
    def get_mission_planet_desc(self):
        """
        Returns special mission-related text when visiting specific planets.
        Matches the pnum logic from missions.c
        called from planets.py in description
        """
        if self.gs.cmdr.mission == 1:
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
            self.gs.swat.update_model(current_obj)
            
    def constrictor_debrief(self):
        if self.state == ST_SETUP:
            logger.debug('')
            self.gs.cmdr.mission = MISSION_1_DEBRIEFED
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
            self.display_brief(self.m4_debrief)
            
    def supernova_debrief(self):
        if self.state == ST_SETUP:      
            self.gs.cmdr.current_cargo = [0] * 17  
            self.gs.cmdr.current_cargo[15] = 250            
            self.display_brief(self.m5_debrief)
                            
    def check_destroy(self, ship):
       if ship.type == cs.SHIP_CONSTRICTOR:
           self.gs.cmdr.mission = 2  # MISSION_1_COMPLETE
       if (ship.type == cs.SHIP_THARGOID
               and self.gs.cmdr.mission == MISSION_4_BRIEFED):
           self.destroyed_thargoids += 1
           self.gs.info_message_left(f'Destroyed {self.destroyed_thargoids}/{MAX_THARGOIDS} Thargoids')
           if self.destroyed_thargoids >= MAX_THARGOIDS:
               self.gs.cmdr.mission = MISSION_4_COMPLETE
               self.gs.msg_left.text = 'Thargons destroyed'
            
    def spawn_ship(self):
        # triggered every 4.25 seconds
        # lone hunter on missions
        gs = self.gs
        
        if (gs.cmdr.mission == MISSION_1_HUNT
                and gs.cmdr.galaxy_number == 1
                and gs.present_planet.name == 'Orarra'
                and gs.swat.ship_count.get(cs.SHIP_CONSTRICTOR, 0) == 0):
            return cs.SHIP_CONSTRICTOR
            
        elif gs.cmdr.mission == MISSION_2_BRIEFED and rand255() >= 220:
            return cs.SHIP_THARGOID
            
        elif gs.cmdr.mission == MISSION_3_BRIEFED and rand255() >= 220:
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
            return None
            
        elif (gs.cmdr.mission == MISSION_4_BRIEFED
              and gs.present_planet.name == planet_4_1
              and rand255() >= 0):
            # produce 10 thargoids, less any already destroyed.
            # this produces a cluster of aliens in the local area, slowly
            # reducing as you kill.
            # since ships further than 56km disappear, you would otherwise
            # get attrition by distance
            # stops at 10 thargoids they do not get replaced
            # logger.error(f'existing thargoids {self.gs.swat.ship_count[cs.SHIP_THARGOID]}')
         
            generated = 0
            while self.gs.swat.ship_count[cs.SHIP_THARGOID] < (MAX_THARGOIDS - self.destroyed_thargoids):
                ship_type = cs.SHIP_THARGOID
                z = random.randint(-SPAWN_DISTANCE, SPAWN_DISTANCE)
                x = random.randint(-SPAWN_DISTANCE, SPAWN_DISTANCE)
                y = random.randint(-SPAWN_DISTANCE, SPAWN_DISTANCE)
                station_position = self.universe[1].location
                thargoid_position = station_position + Vector(x, y, z)
                # logger.error(f'spawning thargoid at {thargoid_position}')
                rotmat = self.gs.swat.rotmat_facing(thargoid_position, station_position)
                newship = gs.swat.add_new_ship(ship_type, *thargoid_position.to_tuple,  rotmat, 0, 0)
                if newship == cs.MAX_UNIV_OBJECTS - 2:
                    break
                gs.swat.ship_list[cs.SHIP_THARGOID].max_loot = 0
                generated += 1
            # logger.error(f'generated {generated}ships')
            return None
            
        elif (gs.cmdr.mission == MISSION_5_BRIEFED
              and gs.present_planet.name == planet_5_1
              and rand255() >= 0):            
            
            return cs.SHIP_BOA
        else:
            return None    
            
    def scoop_cargo(self, obj):
        if (obj.type == cs.SHIP_CARGO
                and obj.parent == cs.SHIP_ASP2
                and self.gs.cmdr.mission == MISSION_3_BRIEFED):
           self.gs.cmdr.current_cargo[cs.ALIEN_ITEMS_IDX] += 1
           self.gs.info_message("Scooped: Cloaking Device")
           
    def system_arrival(self):
        # mission specific arrngements when we arrive in system
        if (self.gs.cmdr.mission == MISSION_5_BRIEFED
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
        if self.gs.cmdr.mission == MISSION_1_HUNT:
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
        # Trigger Mission 1: score > 256 and in Galaxy 1 or 2
        if self.cmdr.mission == MISSION_NONE and score >= 256 and gal_num < 2:
            self.constrictor_briefing()
            return MISSION_1_HUNT

        # Trigger Mission 1 Debrief
        if self.cmdr.mission == MISSION_1_COMPLETE:
            self.constrictor_debrief()
            return MISSION_1_DEBRIEFED

        # Trigger Mission 2: score > 1280 and in Galaxy 3
        if self.cmdr.mission == MISSION_1_DEBRIEFED and score >= 1280 and gal_num == 2:
            self.display_brief(self.m2_brief_a)
            return MISSION_2_START

        # Trigger Mission 2 Part 2: Reach Ceerdi
        if self.cmdr.mission == MISSION_2_START and present_planet.name == 'Ceerdi':
            self.display_brief(self.m2_brief_b)
            return MISSION_2_BRIEFED

        # Trigger Mission 2 End: Reach end planet
        if self.cmdr.mission == MISSION_2_BRIEFED and present_planet.name == 'Soiserla':
            self.thargoid_debrief()
            return MISSION_2_COMPLETE
            
        # Trigger Mission 3
        if self.cmdr.mission == MISSION_2_COMPLETE and gal_num == 2:
            logger.error('first brief')
            # self.state = ST_SETUP
            self.display_brief(self.m3_brief_a)
            return MISSION_3_START

        # Trigger Mission 3 Part 2: Reach 1st waypoint
        if self.cmdr.mission == MISSION_3_START and present_planet.name == planet_3_1:
            # self.state = ST_SETUP
            self.display_brief(self.m3_brief_b)
            return MISSION_3_BRIEFED

        # Trigger Mission 3 End: Reach end planet
        if (self.cmdr.mission == MISSION_3_BRIEFED
                and present_planet.name == planet_3_2
                and self.cmdr.current_cargo[cs.ALIEN_ITEMS_IDX] >= 3):
            # self.state = ST_SETUP
            self.cloaking_debrief()
            return MISSION_3_COMPLETE
            
        # Trigger Mission 4 : score > 1500 and in Galaxy 4
        if self.cmdr.mission == MISSION_3_COMPLETE and score >= 1500 and gal_num == 3:
            # logger.error('first brief')
            # self.state = ST_SETUP
            self.display_brief(self.m4_brief_a)
            self.state = ST_SETUP
            return MISSION_4_BRIEFED
         
        if self.cmdr.mission == MISSION_4_COMPLETE:
           self.thargoid_invasion_debrief()
           return MISSION_4_FINISHED
           
        # Trigger Mission 5 :  in Galaxy 4
        if self.cmdr.mission == MISSION_4_FINISHED and  gal_num == 3:
            # self.state = ST_SETUP
            self.display_brief(self.m5_brief_a)
            self.state = ST_SETUP
            return MISSION_5_BRIEFED
            
        if  self.cmdr.mission == MISSION_5_BRIEFED and gs.present_planet.name == planet_5_1:
              # clear the cargo hold(!) and fill with refugees                        
              
              gs.cmdr.current_cargo = [0] * 17 + [250]               
              gs.input_queue.put('OK')
              gs.input_queue.put('Status')
              gs.info_message('Go! Go')
              return MISSION_5_COMPLETE
              
        if self.cmdr.mission == MISSION_5_COMPLETE and gs.present_planet.name != planet_5_1:
            self.supernova_debrief()
            return MISSION_5_COMPLETE
            
        self.gs.current_screen = cs.SCR_PLANET_DATA
