import random
from copy import deepcopy
# Unit Constants
import constants as cs
import logging
logger = logging.getLogger(__name__)


class TradeManager:
    def __init__(self, game_state):
        self.gs = game_state
        self.cmdr = game_state.commander
        
        # The stock_market data structure
        # (Name, current_qty, current_price, base_price, eco_adjust, base_qty, mask, units)
        self.STOCK_MARKET = [
            {"name": "Food",         "base_price": 19,  "eco_adjust": -2, "base_qty": 6,   "mask": 0x01, "units": cs.TONNES},
            {"name": "Textiles",     "base_price": 20,  "eco_adjust": -1, "base_qty": 10,  "mask": 0x03, "units": cs.TONNES},
            {"name": "Radioactives", "base_price": 65,  "eco_adjust": -3, "base_qty": 2,   "mask": 0x07, "units": cs.TONNES},
            {"name": "Slaves",       "base_price": 40,  "eco_adjust": -5, "base_qty": 226, "mask": 0x1F, "units": cs.TONNES},
            {"name": "Liquor/Wines", "base_price": 83,  "eco_adjust": -5, "base_qty": 251, "mask": 0x0F, "units": cs.TONNES},
            {"name": "Luxuries",     "base_price": 196, "eco_adjust": 8,  "base_qty": 54,  "mask": 0x03, "units": cs.TONNES},
            {"name": "Narcotics",    "base_price": 235, "eco_adjust": 29, "base_qty": 8,   "mask": 0x78, "units": cs.TONNES},
            {"name": "Computers",    "base_price": 154, "eco_adjust": 14, "base_qty": 56,  "mask": 0x03, "units": cs.TONNES},
            {"name": "Machinery",    "base_price": 117, "eco_adjust": 6,  "base_qty": 40,  "mask": 0x07, "units": cs.TONNES},
            {"name": "Alloys",       "base_price": 78,  "eco_adjust": 1,  "base_qty": 17,  "mask": 0x1F, "units": cs.TONNES},
            {"name": "Firearms",     "base_price": 124, "eco_adjust": 13, "base_qty": 29,  "mask": 0x07, "units": cs.TONNES},
            {"name": "Furs",         "base_price": 176, "eco_adjust": -9, "base_qty": 220, "mask": 0x3F, "units": cs.TONNES},
            {"name": "Minerals",     "base_price": 32,  "eco_adjust": -1, "base_qty": 53,  "mask": 0x03, "units": cs.TONNES},
            {"name": "Gold",         "base_price": 97,  "eco_adjust": -1, "base_qty": 66,  "mask": 0x07, "units": cs.KILOGRAMS},
            {"name": "Platinum",     "base_price": 171, "eco_adjust": -2, "base_qty": 55,  "mask": 0x1F, "units": cs.KILOGRAMS},
            {"name": "Gem-Stones",   "base_price": 45,  "eco_adjust": -1, "base_qty": 250, "mask": 0x0F, "units": cs.GRAMS},
            {"name": "Alien Items",  "base_price": 53,  "eco_adjust": 15, "base_qty": 192, "mask": 0x07, "units": cs.TONNES},
        ]
        
        # Initialize current price and quantity fields
        for item in self.STOCK_MARKET:
            item["current_price"] = 0
            item["current_quantity"] = 0
            
    def set_stock_quantities(self, quant):
        for i, item in enumerate(self.stock_market):
            item["base_qty"] = quant[i]
             
        for item in self.stock_market:
            if item["name"] == "Alien Items":
                item["base_qty"] = 0
       
    def generate_stock_market(self, planet_economy):
        """
        Generates prices and quantities based on the planet's economy
        Mimics the 8-bit overflow/clamping of the original code.
        """
        market = deepcopy(self.STOCK_MARKET)
        for i, item in enumerate(market):
            # Price calculation
            price = item["base_price"]
            price += (self.cmdr.market_rnd & item["mask"])
            price += (planet_economy * item["eco_adjust"])
            price &= 0xFF  # Keep to 8-bit
            
            # Quantity calculation
            quant = item["base_qty"]
            quant += (self.cmdr.market_rnd & item["mask"])
            quant -= (planet_economy * item["eco_adjust"])
            quant &= 0xFF  # Keep to 8-bit
            
            if quant > 127:  # Mimic signed 8-bit check
                quant = 0
            
            quant &= 63  # Quantities in Elite are capped at 63
            
            item["current_price"] = price * 4
            item["current_quantity"] = quant

        # Alien items are special: found/scooped, but never bought from market
        market[cs.ALIEN_ITEMS_IDX]["current_quantity"] = 0
        return market

    def carrying_contraband(self):
        """Returns a 'threat level' based on illegal goods held."""
        illegal_goods = (self.cmdr.current_cargo[cs.SLAVES]
                         + self.cmdr.current_cargo[cs.NARCOTICS]) * 2
        illegal_goods += self.cmdr.current_cargo[cs.FIREARMS]
        return illegal_goods

    def total_cargo(self):
        """Calculates total tonnes currently in the hold."""
        cargo_held = 0
        for i in range(len(self.stock_market)):
            if (self.cmdr.current_cargo[i] > 0
                    and self.stock_market[i]["units"] == cs.TONNES):
                cargo_held += self.cmdr.current_cargo[i]
        return cargo_held

    def scoop_item(self, universe_obj_index, universe):
        """
        Handles the logic for fuel-scooping cargo canisters or debris.
        """
        obj = universe[universe_obj_index]
        parent = getattr(obj, 'parent', None)
        logger.debug(f'{obj}')
        if obj.flags & cs.FLG_DEAD:
            return

        # Cannot scoop missiles
        if obj.type == cs.SHIP_MISSILE:
            return

        # Check conditions for successful scooping
        # 1. Must have fuel scoop equipment
        # 2. Item must be in the lower half of the screen (y >= 0 in Elite's coordinate system)
        # 3. Must have cargo space
        if (not self.cmdr.fuel_scoop
                or obj.location.y >= 0
                or self.total_cargo() >= self.cmdr.cargo_capacity):
            
            # If conditions fail, you collide with the object instead
            obj.exploding = True
            damage = 128 + (obj.energy // 2)
            self.gs.space.damage_ship(damage, True)
            return

        # If it's a generic cargo canister
        if obj.type == cs.SHIP_CARGO:
            trade_type = random.randint(0, 255) & 15  # Randomly determine what's inside
            quantity = random.randint(0, 255) & 7
            self.cmdr.current_cargo[trade_type] += quantity
            logger.debug(f"Scooped: {quantity} {self.stock_market[trade_type]['name']}s")
            universe.remove_ship(universe_obj_index)
            return

        # If it's a specific item (like an escape pod or alloy)
        elif obj.type == cs.SHIP_ALLOY:
            # allow capture of alien items
            if parent in [cs.THARGON, cs.THARGOID]:
                self.cmdr.current_cargo[16] += 1
                self.gs.info_message("Scooped: Alien Items")
                universe.remove_ship(universe_obj_index)
                return
               
            self.cmdr.current_cargo[9] += 1
            self.gs.info_message("Scooped: Alloy")
            universe.remove_ship(universe_obj_index)
            return
        
        # Default collision if item isn't scoopable
        obj.exploding = True
        self.gs.space.damage_ship(obj.energy // 2, True)
        
        
if __name__ == '__main__':
   pass

