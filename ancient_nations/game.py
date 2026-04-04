"""
game.py – Central game state and turn processing.
"""
import random
import math
from pathlib import Path
from constants import *
from world import World
from nation import Nation
from entities import Town, Army
from ai import NationAI
from combat import resolve_battle
from events import EventSystem
from loader import load_json5
from namegen import NationNameGenerator


# ─────────────────────────────────────────────────────────────────────────────
class CombatManager:
    def __init__(self, game):
        self.game = game

    def resolve(self, attacker, defender, tile, turn,
                atk_surge=False, tier4_def=False,
                atk_trait_dice=0, def_trait_dice=0):
        return resolve_battle(attacker, defender, tile, turn, self.game.log,
                              atk_surge=atk_surge, tier4_def=tier4_def,
                              atk_trait_dice=atk_trait_dice,
                              def_trait_dice=def_trait_dice,
                              nations=self.game.nations)


# ─────────────────────────────────────────────────────────────────────────────
class Game:
    def __init__(self, seed=None, num_nations=NUM_NATIONS):
        self.turn     = 0
        self.paused   = True
        self.speed    = TURN_DELAY
        self.logs     = []          # list of (turn, msg, nation_idx|-1)
        self.battles  = []          # list of Battle objects

        # World
        self.world    = World(seed)

        # Trait pool — shuffle so each run assigns traits differently
        _data = Path(__file__).parent / 'data'
        self.trait_list = load_json5(_data / 'traits.json5')['traits']
        self._trait_pool = self.trait_list[:]
        random.shuffle(self._trait_pool)

        # Nations
        self.nations    : list[Nation] = []
        self.combat     = CombatManager(self)
        self._namegen   = NationNameGenerator()
        self._spawn_nations(num_nations)

        # AI controllers
        self.ai = [NationAI(n, self.world, self) for n in self.nations]

        # Event system
        self.events              = EventSystem(self)
        self.events_history      : list = []   # WorldEvent objects
        self.pending_recoveries  : list = []   # [(turn, cx, cy, r, type)]

        self.log(0, f"=== ANCIENT NATIONS begins. Seed:{self.world.seed} ===")
        self.log(0, f"  {num_nations} nations on a {MAP_SIZE}x{MAP_SIZE} map")

    # ── nation spawning ────────────────────────────────────────────────────
    def _spawn_nations(self, n):
        valid = self.world.valid_spawn_points()
        random.shuffle(valid)
        spawned = []

        for i in range(n):
            placed = False
            for x,y in valid:
                dist_ok = all(math.dist((x,y),(sx,sy)) >= MIN_NATION_DISTANCE
                               for sx,sy in spawned)
                if dist_ok:
                    nation = Nation(i, self._namegen.generate(), NATION_COLORS[i], x, y,
                                    self.world)
                    nation.trait = self._trait_pool[i % len(self._trait_pool)]
                    self.nations.append(nation)
                    spawned.append((x,y))
                    self.log(0,
                        f"  {nation.name} founded at ({x},{y}) "
                        f"[{nation.trait['name']}]",
                        i)
                    placed = True
                    break
            if not placed:
                # Fallback: pick furthest from all spawned
                best_dist = -1; bx,by = valid[0]
                for px,py in valid:
                    d = min((math.dist((px,py),(sx,sy)) for sx,sy in spawned),
                             default=float('inf'))
                    if d > best_dist:
                        best_dist=d; bx,by=px,py
                nation = Nation(i, self._namegen.generate(), NATION_COLORS[i], bx, by,
                                self.world)
                nation.trait = self._trait_pool[i % len(self._trait_pool)]
                self.nations.append(nation)
                spawned.append((bx,by))

    # ── main turn processing ───────────────────────────────────────────────
    def process_turn(self):
        self.turn += 1
        t = self.turn
        season_food = self._season_food_mul()

        # 1. Resource collection
        for n in self.nations:
            if n.alive:
                n.collect_resources(self.world, season_food)

        # 1b. Alliance trade dividends (Tier 1+)
        self._apply_alliance_dividends(t)

        # 2. Population growth & town levelling
        for n in self.nations:
            if not n.alive: continue
            for town in n.towns:
                food_surplus = max(0, n.res[RES_FOOD] - 50)
                levelled = town.grow_population(food_surplus * 0.1)
                if levelled:
                    self.log(t,
                        f"  {town.name} grew to {town.level_name()}!",
                        n.idx)
                    # Update capital tracking
                    cap = n.capital
                    if cap:
                        for tw in n.towns:
                            tw.is_capital = (tw is cap)

        # 3. AI decisions (movement, building, diplomacy)
        for ai in self.ai:
            if ai.n.alive:
                ai.tick(t)

        # 3b. Territory far from any town slowly reverts to neutral (carrying cost)
        self._tick_territory_abandonment(t)

        # 4. Pay upkeep
        for n in self.nations:
            if not n.alive: continue
            n.pay_upkeep()
            # If food runs out, armies starve
            if n.res[RES_FOOD] <= 0:
                if n.armies:
                    victim = random.choice(n.armies)
                    victim.health = max(0, victim.health - 5)
                    if not victim.is_alive():
                        self.ai[n.idx]._remove_army(victim)
                        self.log(t, f"  {n.name}'s army starved!", n.idx)

        # 4b. Famine: prolonged national food stress downgrades towns
        self._tick_famine_towns(t)

        # 5. World events
        new_evts = self.events.tick(t)
        self.events_history.extend(new_evts)

        # 5b. Terrain recovery (floods receding, etc.)
        self._process_recoveries(t)

        # 6. Eliminate bankrupt nations
        self._check_eliminations(t)

        # 6b. Tick rebellion cooldowns on absorbed nation slots
        for n in self.nations:
            if not n.alive and n.rebellion_cooldown > 0:
                n.rebellion_cooldown -= 1

        # 7. Snapshot for charts
        for n in self.nations:
            n.snapshot()

    def _apply_alliance_dividends(self, t):
        """Bilateral resource bonus for Tier 1+ alliances.
        Each pair is processed once; both nations receive the dividend."""
        processed = set()
        for n in self.nations:
            if not n.alive: continue
            for ally_idx in n.allies():
                pair = (min(n.idx, ally_idx), max(n.idx, ally_idx))
                if pair in processed: continue
                processed.add(pair)
                ally = self.nations[ally_idx]
                if not ally.alive: continue
                # Use the lower of the two sides' tier (both must have aged it)
                tier = min(n.alliance_tier(ally_idx), ally.alliance_tier(n.idx))
                if tier < 1: continue
                bonus = ALLIANCE_DIVIDEND[tier]
                for r in (RES_FOOD, RES_WOOD, RES_METAL):
                    n.res[r]    += bonus
                    ally.res[r] += bonus

    def _process_recoveries(self, t):
        """Revert temporary terrain changes (e.g. floods receding)."""
        still_pending = []
        for (due_turn, cx, cy, radius, rtype) in self.pending_recoveries:
            if t >= due_turn:
                if rtype == 'flood':
                    for tile in self.world.tiles_in_radius(cx, cy, radius):
                        if tile.terrain == TERRAIN_RIVER and tile.entity is None:
                            if random.random() < 0.6:
                                tile.terrain = TERRAIN_PLAIN
                    self.log(t, f"[FLOOD] Waters recede near ({cx},{cy}).")
            else:
                still_pending.append((due_turn, cx, cy, radius, rtype))
        self.pending_recoveries = still_pending

    def _season_food_mul(self):
        """Alternating wet / dry halves affect food gathering (not deposits/gold)."""
        if SEASON_LENGTH_TURNS <= 0:
            return 1.0
        half = SEASON_LENGTH_TURNS
        phase = (self.turn - 1) % (2 * half)
        return SEASON_FOOD_MUL_WET if phase < half else SEASON_FOOD_MUL_DRY

    def _tick_territory_abandonment(self, t):
        """Tiles not covered by any friendly town gathering radius drift back to neutral."""
        for n in self.nations:
            if not n.alive:
                continue
            covered = set()
            bonus = n.trait_val('town_radius_bonus', 0)
            for town in n.towns:
                r = town.radius + bonus
                for tile in self.world.tiles_in_radius(town.x, town.y, r):
                    if tile.owner == n.idx:
                        covered.add((tile.x, tile.y))
            for xy in list(n.tiles):
                tile = self.world.t(xy[0], xy[1])
                if xy in covered:
                    tile.territory_neglect = 0
                    continue
                tile.territory_neglect += 1
                if tile.territory_neglect >= TERRITORY_NEGLECT_ABANDON_TURNS:
                    self._abandon_tile_to_neutral(n, tile, t)

    def _abandon_tile_to_neutral(self, nation, tile, t):
        nation.tiles.discard((tile.x, tile.y))
        tile.owner = -1
        tile.territory_neglect = 0
        tile.captured_turn = -1
        if tile.town is None and tile.entity is not None:
            tile.entity = None
        tile.road = False
        self.log(t,
            f"  {nation.name} lost control of distant land ({tile.x},{tile.y})",
            nation.idx)

    def _tick_famine_towns(self, t):
        """National food stress causes towns to lose levels over time."""
        for n in self.nations:
            if not n.alive:
                continue
            famine = n.res[RES_FOOD] <= FAMINE_FOOD_THRESHOLD
            any_downgrade = False
            for town in n.towns:
                if famine:
                    town.food_deficit_turns += 1
                else:
                    town.food_deficit_turns = 0
                if (town.food_deficit_turns >= FAMINE_DOWNGRADE_TURNS
                        and town.apply_famine_downgrade()):
                    any_downgrade = True
                    self.log(t,
                        f"  {town.name} shrank to {town.level_name()} (famine)",
                        n.idx)
            if any_downgrade:
                cap = n.capital
                if cap:
                    for tw in n.towns:
                        tw.is_capital = (tw is cap)

    def _check_eliminations(self, t):
        for n in self.nations:
            if not n.alive: continue
            if len(n.tiles) == 0 or (not n.towns and not n.armies):
                n.alive      = False
                n.death_turn = t
                self.log(t, f"[DEAD] {n.name} has been ELIMINATED!", -1)

    # ── peaceful union ────────────────────────────────────────────────────
    def peaceful_annex(self, larger, smaller, merged_trait, turn):
        """
        Successful union vote: smaller nation joins larger voluntarily.
        Longer rebellion cooldown than surrender — the populace agreed.
        The larger nation's trait is blended (replaced by merged_trait).
        """
        # Transfer tiles
        for xy in list(smaller.tiles):
            self.world.set_tile_owner(xy[0], xy[1], larger.idx)
            larger.tiles.add(xy)
        smaller.tiles = set()

        # Transfer towns
        for town in list(smaller.towns):
            town.nation = larger.idx
            town.is_capital = False
            larger.towns.append(town)
        smaller.towns = []

        # Transfer armies (they voted to join — armies follow)
        for army in list(smaller.armies):
            army.nation = larger.idx
            larger.armies.append(army)
        smaller.armies = []

        # Dissolve alliance cleanly on both sides
        larger.break_alliance(smaller.idx, betrayal=False)
        smaller.break_alliance(larger.idx, betrayal=False)

        # Apply the blended trait to the surviving nation
        larger.trait = merged_trait

        # Eliminate with long cooldown (willing union → stable → slower to rebel)
        smaller.alive        = False
        smaller.death_turn   = turn
        smaller.absorbed_by  = larger.name
        smaller.rebellion_cooldown = UNION_COOLDOWN_TURNS

        self.log(turn,
            f"[UNION] {smaller.name} votes to join {larger.name}! "
            f"A unified realm rises [{merged_trait['name']}].",
            larger.idx)

    # ── surrender / absorption ────────────────────────────────────────────
    def absorb_nation(self, winner, loser, turn):
        """
        Loser surrenders to winner.  All tiles and towns transfer; armies disband.
        The loser slot is eliminated but given a rebellion_cooldown so it cannot
        immediately re-emerge as a rebel state.
        """
        # Transfer tiles
        for xy in list(loser.tiles):
            self.world.set_tile_owner(xy[0], xy[1], winner.idx)
            winner.tiles.add(xy)
        loser.tiles = set()

        # Transfer towns
        for town in list(loser.towns):
            town.nation = winner.idx
            town.is_capital = False
            winner.towns.append(town)
        loser.towns = []

        # Disband armies
        for army in list(loser.armies):
            t = self.world.t(army.x, army.y)
            if army in t.armies: t.armies.remove(army)
            if t.army == army:   t.army = t.armies[0] if t.armies else None
        loser.armies = []

        # Eliminate with cooldown (slot locked against rebellion)
        loser.alive        = False
        loser.death_turn   = turn
        loser.absorbed_by  = winner.name
        loser.rebellion_cooldown = REBELLION_COOLDOWN_TURNS

        self.log(turn,
            f"[SURR] {loser.name} SURRENDERS to {winner.name}! "
            f"Absorbed into their empire.",
            loser.idx)

    # ── civil war / rebellion ─────────────────────────────────────────────
    def spawn_rebel_nation(self, turn, parent, min_tiles=30, split_fraction=0.33):
        """
        Carve off a rebel state from parent, reusing an eliminated nation's slot.
        Returns the reborn Nation, or None if conditions aren't met.
        """
        from ai import NationAI  # local import — avoids module-level circular dep

        dead_slots = [n for n in self.nations if not n.alive]
        if not dead_slots:
            return None

        cap = parent.capital
        if not cap or len(parent.tiles) < min_tiles:
            return None

        # Tiles farthest from the capital form the rebel core
        sorted_tiles = sorted(parent.tiles,
                              key=lambda xy: -math.dist(xy, (cap.x, cap.y)))
        split_n      = max(10, int(len(parent.tiles) * split_fraction))
        rebel_tiles  = set(sorted_tiles[:split_n])

        # Transfer tile ownership
        for xy in rebel_tiles:
            parent.tiles.discard(xy)
            self.world.set_tile_owner(xy[0], xy[1], dead_slots[0].idx)

        # Transfer any towns inside rebel territory
        rebel_towns = []
        for xy in list(rebel_tiles):
            tile = self.world.t(xy[0], xy[1])
            if tile.town and tile.town in parent.towns:
                town = tile.town
                parent.towns.remove(town)
                town.nation = dead_slots[0].idx
                town.is_capital = False
                rebel_towns.append(town)
        if rebel_towns:
            max(rebel_towns, key=lambda t: t.population).is_capital = True

        # Transfer armies already standing on rebel tiles
        rebel_armies = []
        for army in list(parent.armies):
            if (army.x, army.y) in rebel_tiles:
                parent.armies.remove(army)
                army.nation = dead_slots[0].idx
                rebel_armies.append(army)

        # Reactivate the slot
        slot = dead_slots[0]
        slot.slot_revivals += 1
        slot.alive         = True
        slot.tiles         = rebel_tiles
        slot.towns         = rebel_towns
        slot.armies        = rebel_armies
        slot.res           = {RES_FOOD:60, RES_WOOD:60, RES_METAL:40, RES_GOLD:20}
        slot.diplomacy     = {}
        slot.peace_timer   = {}
        slot.war_cooldown  = {}
        slot.alliance_cd   = {}
        slot.alliance_age  = {}
        slot.betrayed_turns     = 0
        slot.army_surge_turns   = 0
        slot.alliance_contradiction_turns = 0
        slot.name   = self._namegen.generate()
        slot.letter = slot.name[0].upper()
        slot.trait  = random.choice(self.trait_list)
        slot.history = {
            'territory': [], 'population': [], 'gold': [],
            'food': [], 'wood': [], 'metal': [],
            'armies': [], 'army_strength': [],
            'battles_won': 0, 'battles_lost': 0,
            'trades_done': 0, 'alliances_formed': 0,
        }

        # Restart the AI for this slot
        self.ai[slot.idx] = NationAI(slot, self.world, self)

        # Immediate war declaration
        slot.declare_war(parent.idx, turn)
        parent.declare_war(slot.idx, turn)

        return slot

    # ── logging ───────────────────────────────────────────────────────────
    def log(self, turn, msg, nation_idx=-1):
        self.logs.append((turn, msg, nation_idx))
        if len(self.logs) > LOG_MAX:
            self.logs = self.logs[-LOG_MAX:]

    def recent_logs(self, n=30):
        return self.logs[-n:]

    # ── queries ───────────────────────────────────────────────────────────
    def nation_at(self, x, y):
        t = self.world.t(x,y)
        if t.owner >= 0:
            return self.nations[t.owner]
        return None

    def tile_info(self, x, y):
        t = self.world.t(x,y)
        lines = [
            f"Tile ({x},{y})",
            f"  Terrain : {TERRAIN_NAMES[t.terrain]}",
            f"  Owner   : {self.nations[t.owner].name if t.owner>=0 else 'Neutral'}",
            f"  Entity  : {t.entity or 'none'}",
            f"  Road    : {'yes' if t.road else 'no'}",
            f"  Deposits: F{t.deposits[RES_FOOD]:.1f} "
            f"W{t.deposits[RES_WOOD]:.1f} "
            f"M{t.deposits[RES_METAL]:.1f} "
            f"G{t.deposits[RES_GOLD]:.1f}",
        ]
        if t.town:
            tw = t.town
            lines += [
                f"  Town    : {tw.name} ({tw.level_name()})",
                f"  Pop     : {int(tw.population)}",
            ]
        if t.armies:
            for a in t.armies:
                lines.append(
                    f"  Army L{a.level} hp={a.health}/{a.max_health} "
                    f"[{self.nations[a.nation].name}]")
        return lines
