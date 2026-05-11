# TODO list
#cross does not map when going from short to galactic
planets do not fill screen
flight does not show jumpscreen
view does not respond to pitch and roll
havent seen a planet yet
objects dont respond to view change

flight does not respond to keys




This is a Pythonista game based entirely upon the C version of Elite
by Christian Pinder
Many of the c files have been autoconverted to python by Google Gemini and Claude Sonnet 4.6
The graphics, keyboard input and joystick input will be provided by custom code
scanner, compass and hud are handled by custom code also
text output is also handled

as far as possible, the converted code is used for ship, player and flight logic
The intention is to keep the game as faithful to the original as possible
within limitations of the iPad
Each module is constructed as a class to avoid lots of globals
significant changes:
1. keyboard is replaced by an onscreen bespoke keyboard with labels instead of single letters
   The keyboard keys are reconfigured depending on mode
   
2. 2 joysticks, one for roll, pitch, the other for thrust
    Thrust is direct and will stay set when not touched. initially keep it as it was,
    with up.down to increase or decrease
    Fire button fires whenever held
    
3. Screen can be varied. Hud left and right sections are fixed size. Scanner width changes with screen size
   flight window fills screen. Watch out if original code uses fixed window
   
4. Sound is only cotrolled by device voume. it was not worth dedicating buttons to volume control

5. Graphics are handled by a combination of SpriteNodes for fixed items , and scene drawing for line drawing

6. Load and save use a json file, which makes it human readable (and editable ;)

7. we do not need seperate keys for firing laser in 4 directions, use view to control, and laser sight appears         only if laser fitted

8. read key for system search will be made by pulldown dialog list, maybe prepoluated aith system names in alphabetical order

9. the infinte loop in alg_main would make the system unresponsive. Replace with a routine entered every 1/60th
   second by Scene.update(). a state machine calls appropriate screens

10 for fixed items such as crosshairs and laser lines, draw them once and control alpha dynamically
   This is much faster and more secure than adding, removing. use this also to add safe and ecm icons to hud
  
11. Very imporantly, all text is rendered as sprites, which stay until removed. so some of the logic must change
    to either render them initially, or update if changed. just write a character into numpy matrix. only write sprites when text render
    need 3 arrays, character, color, background color. highlight will just change background
    
    Rows and columns are fixed length. Font sizes change to suit screen size
    

12. Pressing keys enters key into message queue. one message will be processed on each iteration. Hence they are approximately concurrent and multitouch. All keys and joystick pass messages onlyo queue, so implementing rollover.
    direction joystick emits messages when held, whether moved od not, and can move in two directions
    at once

13, toggle keys will be Target Missile/ Unarm. Escape/cancel escape,  Pause/resume   , Docking/abort docking
     equipment keys e.g. ECM will not enable until item bought
     
14. each block of text should finish with text render, which will check if there have been any changes

15. A major change to the program structure is the use of state machines
    As each routine may be called 60 times per second we may need another state machine to cover 
     setup section, at least one iteration section and a means to leave.
    we cannot have blocking loops within the routine.
    
16. Python is all about readability. so prioritise this above sticking rigidly to converted c code
    example use GalaxySeed x an y rather than d and a 
    
17. Added colour to planets, based upon galaxy seed s0_hi bits 3-0 
    colour list is cs.COLOUR_LIST, curated to show sensible colours, no primary or dark colours
    Chart views also use planet radius scaled to  9-23 pixels for short range and 3-7 pixels for galactic chart
    colour and size allows you to visually align galactic and short range chart
            
18. Implemented touch on charts, because it feels natural, rather than having to hold joystick

19. remove approximations to vector rotation. proper sine, cos are quick. remove tidy_matrix.
    Ship drawing is handled seperately, so no issue with distortion.
    
20. To cater for variable screen size, simplify translation of planet space (0-255) to flight rectangle.
    Use Point2 objects to avoid repetition of x, y operations
    
21. Last measured loop time was 4ms, out of budget of 16.6ms , so writing time is not an issue

22. I decided to make direction joystick analogue (-1.0 to + 1.0 in each axis)
    added Proportional Integral Dderivative control to make more responsive
    and natural.

     

Chris `Thomas. April 2026



Elite - The New Kind   Release 1.0
--------------------   -----------

Revision date: 22 July 2001

This is release 1.0 of Elite - The New Kind.
For changes since previous releases see below.

newkindb.zip contains a compiled version of the code designed to run under MS Windows 95/98/NT using the Allegro graphics library and DirectX.

newkind.zip contains source code for Elite - The New Kind.
If you want to recompile the game then please note the following...
a. The .wav and .dat files are not included in the source distribution to keep the size down, they can be found in newkindb.zip.
b. You need the WIP version of Allegro to compile the code.

The latest versions of the source and executable can always be found on the New Kind website...
http://www.newkind.co.uk

To run the supplied executable you will need DirectX installed.  Windows 98/ME/2000 and NT 4 (with latest service pack) come with this.
If you are using Windows 95 and you haven't already installed DirectX you will need to do so.
The DirectX runtime can be downloaded from the Microsoft website. (www.microsoft.com/directx).

Two pieces of music are included in Elite - The New Kind.  The Elite Theme and The Blue Danube.
The Elite Theme was composed by Aidan Bell and the Blue Danube was composed by Strauss.
I spent a long time hunting for the best MIDI versions of these pieces I could find.
To appreciate them properly you will need a decent Soft Synth Midi driver installed and set as you prefered Midi and Sound device.

Keys you can use...
Press Y or N on the intro screen.
Press Space on the ship parade screen.

F1  - Launch when docked, Front View when in flight.
F2  - Rear View
F3  - Left View
F4  - Right View when in flight.
	When docked, Buy Equipment for ship.
      Use up and down arrow keys to select item, return/enter key to buy.
F5  - Display Galactic Chart.
F6  - Short Range Chart.
F7  - Show information on selected planet.
F8  - Buy and sell items on the stock market.
      Use up and down arrow keys to select item, right arrow key to buy, left arrow key to sell.
F9  - Commander information.
F10 - Inventory.
F11 - Options screen (Save Game, Load Game, Game Settings, Quit).
      Use up and down arrows keys to select option, return/enter to select.

 A - Fire.
 S - Dive.
 X - Climb.
 < - Roll Left
 > - Roll Right
 / - Slow Down
Space - Speed up.

 C  - Activate docking computer, if fitted.
 D  - De-activate docking computer if switched on.
 E  - Active ECM, if fitted.
 H  - Hyperspace.
 J  - Warp Jump.
 M  - Fire missile.
 T  - Target a missile.
 U  - Un-target missile.
TAB - Detonate energy bomb, if fitted.
CTRL+H - Galactic Hyperspace, if fitted.
ESC - Launch escape capsule, if fitted.
 P  - Pause game.
 R  - Resume game when paused.

On The Chart Screens
--------------------
D - Select a planet and show distance to it.
F - Find planet by name.
O - Return cursor to current planet.
Cursor Keys - Move cross hairs around.


On The Game Settings Screen
---------------------------
From the Options Screen (F11) you can enter the Game Settings Screen. From here you can change
a number of settings that control how the game looks and plays.  Use the cursor keys to select an option
and the Enter/Return key to change it. The options can be saved as default for future games by pressing Enter
while on the Save Settings option (NB this is not necessary if you want to change the settings just for
the current game).  Game settings are held in the newkind.cfg file which should be in the same directory
as the newkind.exe file.



Release 1.0 - Changes since Beta 3.0
====================================

- Rocks, alloys and boulders no longer stop you from engaging the jump drive.

- Stopped tactics routine from being called while on the intro screens.

- Ramming ships was causing little damage to player's ship.  Now fixed.

- Switching views while in space now switches stars around.

- Moved all Allegro specific graphic functions into alg_gfx.c

- Moved keyboard handling routines into keyboard.c

- Moved file handling routines out of alg_main.c into file.c

- Added screen to allow player to set the game options from within the game.
  This means the player no longer has to hack newkind.cfg directly.

- Tidied graphics routines and removed all references to HDC.

- Fixed movement of crosshairs on chart screens so that they are clipped properly.

- Added explosion, cargo cannisters and alloys to the game over screen.

- Added escape capsule sequence.

- Added option for instant dock vs. auto-pilot docking.

- Fixed bug that allowed an enemy craft to launch multiple escape capsules.

- Fixed asteroids so that they move slower and don't try to evade attack.

- Added rock hermits.

- Tweaked the tactics routine again.

- Added limited joystick support (digital only at the moment).

- Added beep sound when missile target is locked.

- Added low pitch beep sound when missile is unarmed.

- Added Energy Low message when enegry levels reach critical.



Beta 3.0 - Changes since Beta 2.1
=================================

- Fixed bug that allowed lasers to fire too rapidly.

- The console was not being updated (i.e no of missiles) after a saved commander was loaded.  Now fixed.

- Added planet auto-select on chart screens ala NES.

- Asteroid mining implemented.

- Exploding ships now release alloys.

- Fixed bug that caused enemy ships to only fire when at close range.

- Thargoids can now appear.

- Witchspace ambush added.

- Anacondas now release worms and sidewinders when attacked.

- Attacked ships can now release escape capsules.

- Objects other than cargo cannisters can now be scooped.

- Corrected condition indicator code.  Was previously showing yellow even after danger had passed.

- Added ability to pause game (P key pauses, R resumes).

- The Cougar (a cloaked ship) can now appear.

- The second mission is now playable.

- Fixed bug that allowed enemy ships to fire from bizare angles.

- Rewrote tactics routines. New code now based on NES Elite.

- Docking computers now use full auto-pilot rather than just instant dock.

- Space station now launches shuttles and transporters bound for the planet.



Beta 2.1 - Changes since Beta 2.0
=================================

- Added code to set legal status to clean and fuel to maximum after using an escape capsule.

- Fixed enemy missile targeting so that other ships don't blow themselves up.

- Fixed speed of enemy ships which were moving too slowly in previous versions.

- Added game speed control option to newkind.cfg.


Beta 2.0 - Changes since Beta 1.1
=================================

- Fixed bug in enemy tactics which caused ships to run away.

- Set the max speed of player's ship to 0.30LM.

- Added code to display version number on options screen.

- Corrected spelling of "Feudal".

- Enabled docking computers (instant dock for the moment).

- Added hyperspace sound.

- Changed code to display number of credits instead of bounty.

- Set hyperspace count down to 15.

- Added Suns, cabin temperature and fuel scooping.

- Added left and right views when in flight.

- Enabled use of Energy Bomb, activated with TAB key.

- Changed scanner slightly, added code to display objects in different colours.

- Fixed warping of stars in rear view.

- Enabled Escape Capsule, use ESC key to abandon ship.

- Enabled Galactic Hyperspace.

- Added use of 'O' key on chart screens.

- Added ability to find planets by name.

- Added Windows icon created by Marcus Buchanan.

- Added code by Thomas Harte to anti-alias lines and improve hidden surface removal.

- Added option to newkind.cfg to enable anti-alias code.

- Added the first secret mission, hunt the Constrictor!

- Fixed equipment buying so that refund is given on existing lasers.

- Changed colour of fuel limit circle from white to green.

- Put some colour on the Local Chart screen.

- Changed look of ship lollipops on the scanner to look more like the original.

- Changed incoming laser sounds, one for hitting shields and one for hitting the hull.

- Fixed asteroids so that they travel in straight lines.

- Changed creation of ships so that the appear at more random locations.

- Removed the Constrictor and the Cougar from the ship parade intro.



Beta 1.1 - Changes since Beta 1.0
=================================

- Fixed bug in load and save routine which caused the player to aways return to Lave.

- Fixed bug in equipment buying screen.  Buying military lasers for the side or rear view
  would cause mining lasers to be fitted instead.

- Renamed files to be all lowercase.  This should ease ports to other OSes.

- Removed #include of windows only allegro files from alg_main.c

- Added #ifdef around use of GFX_DIRECTX in alg_main.c to allow compilation on non Windows OSes.



Work in progress
================

The following features have not yet been implemented but are being currently worked on.

- C64 Elite style scoring.

- Trumbles (from C64/NES Elite).

- View of docking bay after docking.

- Loading of different consoles not yet fully implemented.

- Enhance joystick support, i.e. use of more buttons and analogue control.


Known Problems
==============

- Bits of hidden surfaces on ships sometimes show through.

- Buying more than 255gs of Gold/Platinum doesn't work.
  It didn't in the original Elite either.  Broken as designed.


Have fun!

Christian Pinder.
<christian@newkind.co.uk>
http://www.newkind.co.uk
