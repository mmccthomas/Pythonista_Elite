import constants as cs
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
ST_SETUP = 0   # Initialise and setup
ST_UPDATE = 1  # run rotating ship for intro1


class MissionManager:
    def __init__(self, gs):
        self.gs = gs
        self.cmdr = gs.cmdr
        self.universe = gs.universe
        self.gfx = gs.gfx
        self.kbd = gs.kbd
        self.state = 0
        
        # Mission 1 Text (The Constrictor)
        self.m1_brief_a = (
            "Greetings Commander, I am Captain Carruthers of "
            "Her Majesty's Space Navy and I beg a moment of your "
            "valuable time. We would like you to do a little job "
            "for us. The ship you see here is a new model, the "
            "Constrictor, equiped with a top secret new shield "
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
            "Ceerdi you will be briefed.If succesful, you will be rewarded."
            "---MESSAGE ENDS.")
  
        self.m2_brief_b = (
            "Good Day Commander. I am Agent Blake of Naval Intelligence. As you know, "
            "the Navy have been keeping the Thargoids off your ass out in deep space "
            "for many years now. Well the situation has changed. Our boys are ready "
            "for a push right to the home system of those murderers.")
        
        self.m2_brief_c = (
            "I have obtained the defence plans for their Hive Worlds. The beetles "
            "know we've got something but not what. If I transmit the plans to our "
            "base on Birera they'll intercept the transmission. I need a ship to "
            "make the run. You're elected. The plans are unipulse coded within "
            "this transmission. You will be paid. Good luck Commander. ---MESSAGE ENDS.")
        
        self.m2_debrief = (
            "You have served us well and we shall remember. "
            "We did not expect the Thargoids to find out about you."
            "For the moment please accept this Navy Extra Energy Unit as payment. "
            "---MESSAGE ENDS.")
            
    def get_mission_planet_desc(self, planet_num):
        """
        Returns special mission-related text when visiting specific planets.
        Matches the pnum logic from missions.c
        called from planets.py in description
        """
        if self.gs.cmdr.galaxy_number == 0:
            mapping = {150: 0, 36: 1, 28: 2}  # Xeer, Reesdice, Arexe
            if planet_num in mapping:
                return self.m1_pdesc[mapping[planet_num]]

        if self.gs.cmdr.galaxy_number == 1:
            # Clues scattered across Galaxy 2
            g2_clues = [32, 68, 164, 220, 106, 16, 162, 3, 107, 26, 192, 184, 5]
            #  Bebege, Cearso, Dicela, Eringe, Gexein, Isarin, Letibema,
            #  Maisso, Onen, Ramaza, Sosole, Tivere,Veriar. -> Errius
            
            match planet_num:
                case _ if planet_num in g2_clues:
                    return self.m1_pdesc[3]
                case 253:  # Errius
                    return self.m1_pdesc[4]
                case 79:  # Inbibe
                    return self.m1_pdesc[5]
                case 53:  # Ausar
                    return self.m1_pdesc[6]
                case 118:  # Usleri
                    return self.m1_pdesc[7]
                case 193:  # Orarra
                    return self.m1_pdesc[8]

        if self.gs.cmdr.galaxy_number == 2 and planet_num == 101:
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

    def check_mission_brief(self, present_planet):
        """
        Main logic gate for triggering missions based on score and location.
        """
        self.cmdr = self.gs.cmdr
        score = self.cmdr.score
        gal_num = self.cmdr.galaxy_number
        present_planet_id = (present_planet.x, present_planet.y)
        # logger.debug(f'{self.cmdr.mission=}')
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
            self.thargoid_brief_1()
            return MISSION_2_START

        # Trigger Mission 2 Part 2: Reach Ceerdi (Planet 215, 84)
        if self.cmdr.mission == MISSION_2_START and present_planet_id == (215, 84):
            
            self.thargoid_brief_2()
            return MISSION_2_BRIEFED

        # Trigger Mission 2 End: Reach Birera (Planet 63, 72)
        if self.cmdr.mission == MISSION_2_BRIEFED and present_planet_id == (63, 72):
            self.thargoid_debrief()
            return
            
        self.gs.current_screen = cs.SCR_PLANET_DATA
                                  
    def constrictor_debrief(self):
        
        if self.state == ST_SETUP:
            logger.debug('')
            # self.gs.cmdr.mission = MISSION_1_DEBRIEFED
            self.gs.cmdr.score += 256
            self.gs.cmdr.credits += 100000  # 10000.0 Credits
            self.state = ST_UPDATE
            
        if self.state == ST_UPDATE:
            self.gfx.clear_display()
            self.gfx.display_centre_text(0, "INCOMING MESSAGE", color=cs.GOLD)
            self.gfx.display_centre_text(3, "Congratulations Commander!", color=cs.GOLD)
            self.gfx.display_pretty_text(0, 4, "You suceeded in your mission to destroy the Constrictor.")
            self.gfx.display_pretty_text(0, 5, "Please accept a reward of 10000 credits.")
            self.gfx.display_pretty_text(0, 6, "There will always be a place for you in Her Majesty's Space Navy.")
            self.gfx.display_centre_text(cs.NUM_LINES-1, "Press OK to continue.", color=cs.GOLD)
            self.gfx.update_screen()
            
    def thargoid_brief_1(self):
        
        if self.state == ST_SETUP:
            self.state = ST_UPDATE
        if self.state == ST_UPDATE:
            self.gfx.clear_display()
            self.gfx.display_centre_text(0, "INCOMING MESSAGE", 140, cs.GOLD)
            self.gfx.display_pretty_text(0, 3, self.m2_brief_a)
            self.gfx.display_centre_text(cs.NUM_LINES-1, "Press OK to continue.", 140, cs.GOLD)
            self.gfx.update_screen()
        
        # read_key

    def thargoid_brief_2(self):
    
        if self.state == ST_SETUP:
            self.state = ST_UPDATE
        if self.state == ST_UPDATE:
            self.gfx.clear_display()
            self.gfx.display_centre_text(0, "INCOMING MESSAGE", 140, cs.GOLD)
            self.gfx.display_pretty_text(0, 3, self.m2_brief_b)
            self.gfx.display_pretty_text(0, 10, self.m2_brief_c)
            # self.gfx.draw_sprite(IMG_BLAKE, 352, 46)
            self.gfx.display_centre_text(cs.NUM_LINES-1, "Press OK to continue.", 140, cs.GOLD)
            self.gfx.update_screen()
        # read_key
    
    def thargoid_debrief(self):
        if self.state == ST_SETUP:
            self.gs.cmdr.score += 256
            self.gs.cmdr.energy_unit = 2
            self.state = ST_UPDATE
        if self.state == ST_UPDATE:
            self.gfx.clear_display()
            self.gfx.display_centre_text(0, "INCOMING MESSAGE", 140, cs.GOLD)
            self.gfx.display_centre_text(3, "Well done Commander.", 140, cs.GOLD)
            self.gfx.display_pretty_text(0, 4, self.m2_debrief)
            self.gfx.display_centre_text(cs.NUM_LINES-1, "Press OK to continue.", 140, cs.GOLD)
            self.gfx.update_screen()
        # read_key

