"""
nation.py – Nation state, resource management, diplomacy tracking.
"""
import random
from constants import *
from entities import Town, Army


class DiplomaticStatus:
    PEACE    = 'peace'
    WAR      = 'war'
    TRADE    = 'trade'      # reserved for future treaty-style trade; not assigned anywhere today
    ALLIANCE = 'alliance'   # mutual defence + resource sharing


class Nation:
    def __init__(self, idx, name, color, capital_x, capital_y, world):
        self.idx        = idx
        self.name       = name
        self.color      = color
        self.letter     = name[0].upper()
        self.alive      = True
        self.death_turn  = None   # turn the nation was eliminated, or None
        self.absorbed_by = None   # name of the nation that absorbed this one, or None

        # Resources (stockpile)
        self.res = {
            RES_FOOD:  float(START_FOOD),
            RES_WOOD:  float(START_WOOD),
            RES_METAL: float(START_METAL),
            RES_GOLD:  float(START_GOLD),
        }

        # Entities
        self.towns  : list[Town] = []
        self.armies : list[Army] = []

        # Territory
        self.tiles  : set        = set()   # set of (x,y)

        # Diplomacy  {other_idx: DiplomaticStatus}
        self.diplomacy      = {}
        self.peace_timer    = {}   # {other_idx: turns of enforced peace remaining}
        self.war_cooldown   = {}   # {other_idx: cooldown turns}
        self.trade_deals    = {}   # {other_idx: {res: amount per turn}} — reserved; not read or written today
        self.alliance_cd    = {}   # {other_idx: turns before can re-ally}
        self.alliance_age   = {}   # {other_idx: turns the alliance has been active}
        self.betrayed_turns = 0    # turns remaining of reputation penalty (others wary)
        self.army_surge_turns = 0  # turns remaining of post-betrayal attack bonus

        # Nation trait (dict loaded from traits.json5, assigned by Game)
        self.trait : dict | None = None

        # Doctrine shifts (e.g. assassination). Each entry: turn, from_trait, to_trait, ids.
        self.trait_history : list[dict] = []

        # Turns remaining before this slot is eligible for a rebellion event.
        # Set when the nation is absorbed via surrender; counts down while dead.
        self.rebellion_cooldown = 0

        # Allied to two nations who are at war with each other — builds until break.
        self.alliance_contradiction_turns = 0

        # How many times this nation *slot* was reactivated (e.g. civil-war rebel).
        # 0 = initial spawn; increments each time spawn_rebel_nation revives the slot.
        self.slot_revivals = 0

        # Stats history (for charts)
        self.history = {
            'territory': [], 'population': [], 'gold': [],
            'food': [], 'wood': [], 'metal': [],
            'armies': [], 'army_strength': [],
            'battles_won': 0, 'battles_lost': 0,
            'trades_done': 0, 'alliances_formed': 0,
        }

        # Place capital
        cap = Town(capital_x, capital_y, idx, is_capital=True)
        cap.level = 2
        cap.population = 80
        cap.gold_local = 80
        self.towns.append(cap)
        world.t(capital_x, capital_y).town = cap
        world.set_tile_owner(capital_x, capital_y, idx)

        # Claim starting territory (5x5 around capital)
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                nx, ny = capital_x+dx, capital_y+dy
                if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE:
                    t = world.t(nx, ny)
                    if t.terrain != TERRAIN_OCEAN:
                        world.set_tile_owner(nx, ny, idx)
                        self.tiles.add((nx, ny))

        self._world = world

    # ── trait helpers ─────────────────────────────────────────────────────
    def trait_val(self, key, default=0):
        """Return a trait modifier value, or default if the trait lacks that key."""
        if self.trait:
            return self.trait.get(key, default)
        return default

    # ── capitals / cities ──────────────────────────────────────────────────
    @property
    def capital(self):
        if not self.towns: return None
        return max(self.towns, key=lambda t: t.population)

    # ── territory ─────────────────────────────────────────────────────────
    def total_population(self):
        return sum(t.population for t in self.towns)

    def total_armies(self):
        return len([a for a in self.armies if a.is_alive()])

    def army_strength(self):
        return sum(a.strength for a in self.armies if a.is_alive())

    # ── diplomacy helpers ─────────────────────────────────────────────────
    def status_with(self, other_idx):
        return self.diplomacy.get(other_idx, DiplomaticStatus.PEACE)

    def at_war_with(self, other_idx):
        return self.status_with(other_idx) == DiplomaticStatus.WAR

    def allied_with(self, other_idx):
        return self.status_with(other_idx) == DiplomaticStatus.ALLIANCE

    def allies(self):
        """Return list of indices we are allied with."""
        return [idx for idx, s in self.diplomacy.items()
                if s == DiplomaticStatus.ALLIANCE]

    def ally_count(self):
        return len(self.allies())

    # ── war ───────────────────────────────────────────────────────────────
    def declare_war(self, other_idx, turn):
        # Break any alliance first
        if self.allied_with(other_idx):
            self._sever_alliance(other_idx, betrayal=True)
        self.diplomacy[other_idx] = DiplomaticStatus.WAR
        self.peace_timer.pop(other_idx, None)

    def make_peace(self, other_idx, turn):
        self.diplomacy[other_idx] = DiplomaticStatus.PEACE
        self.peace_timer[other_idx] = PEACE_MIN_TURNS
        self.war_cooldown[other_idx] = WAR_COOLDOWN

    def can_declare_war(self, other_idx):
        if self.allied_with(other_idx): return False   # must break alliance first
        if self.peace_timer.get(other_idx, 0) > 0: return False
        if self.war_cooldown.get(other_idx, 0) > 0: return False
        return True

    # ── alliances ─────────────────────────────────────────────────────────
    def can_ally(self, other_idx):
        if self.at_war_with(other_idx): return False
        if self.allied_with(other_idx): return False
        if self.ally_count() >= ALLIANCE_MAX: return False
        if self.alliance_cd.get(other_idx, 0) > 0: return False
        return True

    def alliance_tier(self, other_idx):
        """Return 0-4 based on how long the alliance has lasted."""
        age = self.alliance_age.get(other_idx, 0)
        for i in range(len(ALLIANCE_TIER_AGES) - 1, -1, -1):
            if age >= ALLIANCE_TIER_AGES[i]:
                return i
        return 0

    def mutual_def_chance(self, other_idx):
        return ALLIANCE_MUTUAL_DEF[self.alliance_tier(other_idx)]

    def form_alliance(self, other_idx):
        self.diplomacy[other_idx] = DiplomaticStatus.ALLIANCE
        self.alliance_cd.pop(other_idx, None)
        self.alliance_age[other_idx] = 0
        self.history['alliances_formed'] += 1

    def break_alliance(self, other_idx, betrayal=False):
        """Break alliance from our side. Betrayal sets a longer cooldown."""
        self._sever_alliance(other_idx, betrayal=betrayal)

    def _sever_alliance(self, other_idx, betrayal=False):
        if self.diplomacy.get(other_idx) == DiplomaticStatus.ALLIANCE:
            self.diplomacy[other_idx] = DiplomaticStatus.PEACE
        cd = ALLIANCE_BETRAYAL_CD if betrayal else ALLIANCE_COOLDOWN
        self.alliance_cd[other_idx] = cd
        self.alliance_age.pop(other_idx, None)
        if betrayal:
            rep_mul = self.trait_val('betrayal_rep_mul', 1.0)
            self.betrayed_turns   = int(BETRAYAL_REP_TURNS * rep_mul)
            self.army_surge_turns = BETRAYAL_SURGE_TURNS

    def tick_diplomacy(self):
        for k in list(self.peace_timer):
            self.peace_timer[k] = max(0, self.peace_timer[k]-1)
        for k in list(self.war_cooldown):
            self.war_cooldown[k] = max(0, self.war_cooldown[k]-1)
        for k in list(self.alliance_cd):
            self.alliance_cd[k] = max(0, self.alliance_cd[k]-1)
        # Age active alliances; cap at max tier age so dict stays clean
        age_inc = max(1, int(self.trait_val('alliance_age_mul', 1.0)))
        for idx, status in list(self.diplomacy.items()):
            if status == DiplomaticStatus.ALLIANCE:
                self.alliance_age[idx] = min(
                    self.alliance_age.get(idx, 0) + age_inc,
                    ALLIANCE_TIER_AGES[-1] + 1)
            elif self.at_war_with(idx):
                # Partner declared war — alliance collapses without betrayal bonus
                self.alliance_age.pop(idx, None)
        # Tick reputation and surge counters
        if self.betrayed_turns  > 0: self.betrayed_turns  -= 1
        if self.army_surge_turns > 0: self.army_surge_turns -= 1

    # ── resource helpers ──────────────────────────────────────────────────
    def can_afford(self, costs: dict):
        return all(self.res.get(r, 0) >= v for r, v in costs.items())

    def spend(self, costs: dict):
        for r, v in costs.items():
            self.res[r] = max(0, self.res[r] - v)

    def earn(self, gains: dict):
        for r, v in gains.items():
            self.res[r] = self.res.get(r, 0) + v

    def army_build_cost(self, level):
        """Gold only required for armies above level 3."""
        mul = self.trait_val('army_cost_mul', 1.0)
        cost = {
            RES_FOOD:  int(ARMY_COST_FOOD  * level * mul),
            RES_WOOD:  int(ARMY_COST_WOOD  * level * mul),
            RES_METAL: int(ARMY_COST_METAL * level * mul),
        }
        if level > 3:
            cost[RES_GOLD] = int(ARMY_COST_GOLD * (level - 3) * mul)
        return cost

    def army_upkeep_cost(self):
        n = self.total_armies()
        return {RES_FOOD: ARMY_UPKEEP_FOOD * n}

    # ── resource collection ────────────────────────────────────────────────
    def collect_resources(self, world, season_food_mul=1.0):
        """Gather resources from tiles in gathering radius of each town.
        Owned tiles: full yield. Neutral tiles in radius: 40%.
        Allied tiles in radius: 60% (access granted by ally).
        Enemy tiles: blocked."""
        for town in self.towns:
            r = town.radius + self.trait_val('town_radius_bonus', 0)
            for tile in world.tiles_in_radius(town.x, town.y, r):
                owned = (tile.owner == self.idx)
                allied_owner = (tile.owner >= 0
                                and not owned
                                and self.allied_with(tile.owner))
                neutral = (tile.owner == -1)

                if tile.owner >= 0 and not owned and not allied_owner:
                    continue  # enemy tile — no access

                if owned:
                    eff = 1.0
                elif allied_owner:
                    eff = 0.6
                else:  # neutral
                    eff = 0.4

                d = tile.deposits
                gold_mul = self.trait_val('gold_income_mul', 1.0)
                food_mul = self.trait_val('food_yield_mul', 1.0) * season_food_mul
                if tile.entity == 'farm' and owned:
                    self.res[RES_FOOD] += PROD_FARM * food_mul
                elif tile.terrain == TERRAIN_RIVER and tile.entity != 'mine':
                    self.res[RES_FOOD] += d[RES_FOOD] * 0.5 * eff * food_mul
                if tile.entity == 'mine' and owned:
                    self.res[RES_METAL] += PROD_MINE
                elif tile.terrain == TERRAIN_FOREST:
                    self.res[RES_WOOD] += d[RES_WOOD] * 0.4 * eff
                # Natural deposits (all terrain types)
                for res in (RES_FOOD, RES_WOOD, RES_METAL, RES_GOLD):
                    if d[res] > 0 and tile.entity is None:
                        if res == RES_GOLD:
                            mul = gold_mul
                        elif res == RES_FOOD:
                            mul = food_mul
                        else:
                            mul = 1.0
                        self.res[res] += d[res] * 0.2 * eff * mul

    def pay_upkeep(self):
        cost = self.army_upkeep_cost()
        for r, v in cost.items():
            self.res[r] = max(0, self.res[r] - v)
        return True

    # ── snapshot for charts ───────────────────────────────────────────────
    def snapshot(self):
        h = self.history
        h['territory'].append(len(self.tiles))
        h['population'].append(int(self.total_population()))
        h['gold'].append(int(self.res[RES_GOLD]))
        h['food'].append(int(self.res[RES_FOOD]))
        h['wood'].append(int(self.res[RES_WOOD]))
        h['metal'].append(int(self.res[RES_METAL]))
        h['armies'].append(self.total_armies())
        h['army_strength'].append(int(self.army_strength()))
        for k in ('territory', 'population', 'gold', 'food', 'wood', 'metal',
                  'armies', 'army_strength'):
            if len(h[k]) > CHART_HISTORY:
                h[k] = h[k][-CHART_HISTORY:]
