"""
entities.py – Town, Army, Castle, Farm, Mine, Road entity classes.
"""
import random
import math
from constants import *


# ─────────────────────────────────────────────────────────────────────────────
class Town:
    _id_counter = 0

    def __init__(self, x, y, nation_idx, is_capital=False):
        Town._id_counter += 1
        self.id          = Town._id_counter
        self.x           = x
        self.y           = y
        self.nation      = nation_idx
        self.level       = 1         # 1-3 (town), 4 = city
        self.is_capital  = is_capital
        self.population  = 20
        self.name        = self._gen_name(nation_idx, is_capital)

        # Local stockpile
        self.resources   = {RES_FOOD:20, RES_WOOD:15, RES_METAL:10, RES_GOLD:0}
        self.gold_local  = 30 if is_capital else 10

        # Development
        self.roads_to    = []   # list of (x,y) connected towns
        self.army_queue  = 0    # turns until next army is ready
        self.build_queue = None # ('farm'|'mine'|'castle', tx, ty)

    @property
    def radius(self):
        return TOWN_RADIUS[min(self.level-1, 2)]

    @property
    def max_army_level(self):
        return TOWN_MAX_ARMY_LVL[min(self.level-1, 2)]

    def pop_needed_for_next_level(self):
        if self.level >= 4: return None
        return TOWN_GROWTH_POP[self.level-1]

    def grow_population(self, food_surplus):
        growth = POP_GROWTH_BASE + food_surplus * POP_GROWTH_FOOD
        self.population += max(0, growth)
        # level up?
        req = self.pop_needed_for_next_level()
        if req and self.population >= req and self.level < 4:
            self.level += 1
            return True   # levelled up
        return False

    def level_name(self):
        names = {1:'Village',2:'Town',3:'Large Town',4:'City'}
        if self.is_capital: return 'Capital'
        return names.get(self.level,'Town')

    def _gen_name(self, nidx, capital):
        prefixes = [
            ['Roma','Aqua','Urb','Arx','Vicus'],
            ['Athena','Sparta','Korin','Theba','Delphi'],
            ['Perse','Susa','Ecbat','Pars','Media'],
            ['Memphis','Luxor','Sais','Abyd','Khem'],
            ['Tyros','Sidon','Byblos','Utica','Carth'],
            ['Skyth','Borys','Olbia','Tanais','Getae'],
        ]
        suffixes = ['','polis','um','ia','ax','on','ica','opolis']
        p = random.choice(prefixes[nidx % len(prefixes)])
        s = random.choice(suffixes)
        return p + s


# ─────────────────────────────────────────────────────────────────────────────
class Army:
    _id_counter = 0

    def __init__(self, x, y, nation_idx, level=1):
        Army._id_counter += 1
        self.id           = Army._id_counter
        self.x            = x
        self.y            = y
        self.nation       = nation_idx
        self.level        = level        # 1-10
        self.health       = level * 10   # hit points
        self.max_health   = level * 10
        self.moves_left   = 0
        self.destination  = None   # (tx,ty)
        self.path         = []     # list of (x,y)
        self.order        = None   # 'attack'|'defend'|'expand'|'return'|'build'
        self.target       = None   # (tx,ty) or nation_idx
        self.battles_won  = 0
        self.battles_lost = 0
        self.turns_alive  = 0
        self.build_target = None  # ('castle'|'farm'|'mine', tx, ty)

    @property
    def strength(self):
        """Effective combat strength."""
        hp_ratio = self.health / self.max_health
        return self.level * hp_ratio

    def speed(self, world):
        t = world.t(self.x, self.y)
        return t.terrain_speed()

    def is_alive(self):
        return self.health > 0

    def __repr__(self):
        return (f"Army#{self.id}[N{self.nation} L{self.level} "
                f"@({self.x},{self.y}) hp={self.health}/{self.max_health}]")


# ─────────────────────────────────────────────────────────────────────────────
class Battle:
    """Record of a battle."""
    def __init__(self, turn, ax, ay, atk_nation, def_nation,
                 atk_army, def_army, winner, atk_losses, def_losses, notes=''):
        self.turn        = turn
        self.x           = ax
        self.y           = ay
        self.atk_nation  = atk_nation
        self.def_nation  = def_nation   # -1 if neutral
        self.atk_army    = atk_army     # Army obj snapshot
        self.def_army    = def_army
        self.winner      = winner       # nation_idx or -1
        self.atk_losses  = atk_losses
        self.def_losses  = def_losses
        self.notes       = notes

    def summary(self, nation_names):
        an = nation_names[self.atk_nation]
        dn = nation_names[self.def_nation] if self.def_nation>=0 else 'Neutral'
        wn = nation_names[self.winner] if self.winner>=0 else 'Neutral'
        return (f"T{self.turn:4d} | {an:12s} → {dn:12s} | "
                f"Winner:{wn:12s} | Losses: {self.atk_losses}/{self.def_losses}")
