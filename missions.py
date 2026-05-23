import time
import constants as cs
# Mission State Constants
MISSION_NONE = 0
MISSION_1_HUNT = 1
MISSION_1_COMPLETE = 2
MISSION_1_DEBRIEFED = 3
MISSION_2_START = 4
MISSION_2_BRIEFED = 5
MISSION_2_COMPLETE = 6


class MissionManager:
    def __init__(self, gs):
        self.gs = gs
        self.cmdr = gs.commander
        self.universe = gs.universe
        self.gfx = gs.gfx
        self.kbd = gs.kbd
        # Mission 1 Text (The Constrictor)
        self.m1_brief_a = (
            "Greetings Commander, I am Captain Curruthers of "
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
            "THE CONSTRICTOR WAS LAST SEEN AT REESDICE, COMMANDER.",
            "A STRANGE LOOKING SHIP LEFT HERE A WHILE BACK. LOOKED BOUND FOR AREXE.",
            "YEP, AN UNUSUAL NEW SHIP HAD A GALACTIC HYPERDRIVE FITTED HERE, USED IT TOO.",
            "I HEAR A WEIRD LOOKING SHIP WAS SEEN AT ERRIUS.",
            "THIS STRANGE SHIP DEHYPED HERE FROM NOWHERE, SUN SKIMMED AND JUMPED. I HEAR IT WENT TO INBIBE.",
            "ROGUE SHIP WENT FOR ME AT AUSAR. MY LASERS DIDN'T EVEN SCRATCH ITS HULL.",
            "OH DEAR ME YES. A FRIGHTFUL ROGUE WITH WHAT I BELIEVE YOU PEOPLE CALL A LEAD ",
            "POSTERIOR SHOT UP LOTS OF THOSE BEASTLY PIRATES AND WENT TO USLERI.",
            "YOU CAN TACKLE THE VICIOUS SCOUNDREL IF YOU LIKE. HE'S AT ORARRA.",
            "THERE'S A REAL DEADLY PIRATE OUT THERE.",
            "BOY ARE YOU IN THE WRONG GALAXY!"
        ]

    def get_mission_planet_desc(self, planet_num):
        """
        Returns special mission-related text when visiting specific planets.
        Matches the pnum logic from missions.c
        """
        if self.cmdr.galaxy_number == 0:
            mapping = {150: 0, 36: 1, 28: 2}
            if planet_num in mapping:
                return self.m1_pdesc[mapping[planet_num]]

        if self.cmdr.galaxy_number == 1:
            # Clues scattered across Galaxy 2
            g2_clues = [32, 68, 164, 220, 106, 16, 162, 3, 107, 26, 192, 184, 5]
            if planet_num in g2_clues:
                return self.m1_pdesc[3]
            if planet_num == 253:
                return self.m1_pdesc[4]
            if planet_num == 79:
                return self.m1_pdesc[5]
            if planet_num == 53:
                return self.m1_pdesc[6]
            if planet_num == 118:
                return self.m1_pdesc[7]
            if planet_num == 193:
                return self.m1_pdesc[8]

        if self.cmdr.galaxy_number == 2 and planet_num == 101:
            return self.m1_pdesc[9]

        return None

    def constrictor_briefing(self):
        """Displays the scrolling text and rotating ship for Mission 1."""
        self.cmdr.mission = MISSION_1_HUNT
        
        self.gfx.clear_display()
        self.gfx.draw_centre_text(0, "INCOMING MESSAGE", color="GOLD")

        self.gfx.draw_pretty_text(0, 3, self.m1_brief_a)
        
        brief_end = self.m1_brief_b if self.cmdr.galaxy_number == 0 else self.m1_brief_c
        self.gfx.draw_pretty_text(0, 10, brief_end)
        self.gfx.draw_centre_text(8, "Press space to continue.", color="GOLD")

        # Set up a rotating Constrictor in the display area
        self.universe.clear()
                
        self.universe.add_new_ship(cs.SHIP_CONSTRICTOR, pos=(200, 90, 600), rot=(-127, -127))
        # TODO this won't work, split same as intro.py
        while not self.kbd.is_pressed("space"):
            # Clear the area where the ship is drawn
            self.gfx.clear_area(310, 50, 510, 180)
            self.universe.update()
            # Keep ship at fixed distance for viewing
            self.universe.objects[0].pos.z = 600
            self.gfx.update_screen()
            time.sleep(0.01)

    def check_mission_brief(self, docked_planet_id):
        """
        Main logic gate for triggering missions based on score and location.
        """
        score = self.cmdr.score
        gal_num = self.cmdr.galaxy_number

        # Trigger Mission 1: score > 256 and in Galaxy 1 or 2
        if self.cmdr.mission == MISSION_NONE and score >= 256 and gal_num < 2:
            self.constrictor_briefing()
            return

        # Trigger Mission 1 Debrief
        if self.cmdr.mission == MISSION_1_COMPLETE:
            self.constrictor_debrief()
            return

        # Trigger Mission 2: score > 1280 and in Galaxy 3
        if self.cmdr.mission == MISSION_1_DEBRIEFED and score >= 1280 and gal_num == 2:
            self.thargoid_brief_1()
            return

        # Trigger Mission 2 Part 2: Reach Ceerdi (Planet 215, 84)
        if self.cmdr.mission == MISSION_2_START and docked_planet_id == (215, 84):
            self.thargoid_brief_2()
            return

        # Trigger Mission 2 End: Reach Birera (Planet 63, 72)
        if self.cmdr.mission == MISSION_2_BRIEFED and docked_planet_id == (63, 72):
            self.thargoid_debrief()
            return

    def constrictor_debrief(self):
        self.cmdr.mission = MISSION_1_DEBRIEFED
        self.cmdr.score += 256
        self.cmdr.credits += 50000  # 5000.0 Credits
        
        self.gfx.clear_display()
        self.gfx.draw_centre_text(0, "INCOMING MESSAGE", color="GOLD")
        self.gfx.draw_centre_text(3, "Congratulations Commander!", color="GOLD")
        self.gfx.draw_pretty_text(0, 5, "There will always be a place for you in Her Majesty's Space Navy.")
        self.gfx.update_screen()
        self.wait_for_space()

    def wait_for_space(self):
        while not self.kbd.is_pressed("space"):
            time.sleep(0.1)
