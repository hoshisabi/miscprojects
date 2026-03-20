"""
events.py – Random world events that fire periodically.

Event metadata (rarity, labels, etc.) is loaded from data/events.json5 so
players can tune frequency without touching code.  Effect logic lives here.
"""
import random
import math
from pathlib import Path
from constants import *
from loader import load_json5

# ── Load event metadata ────────────────────────────────────────────────────────
_DATA = Path(__file__).parent / 'data'
_EVENT_META = load_json5(_DATA / 'events.json5')['events']

# Build lookup dicts from metadata
EVENT_RARITY    = {k: v['rarity']       for k, v in _EVENT_META.items()}
EVENT_COOLDOWN  = {k: v['rarity'] // v.get('cooldown_div', 3)
                   for k, v in _EVENT_META.items()}
EVENT_LABEL     = {k: v['label']        for k, v in _EVENT_META.items()}

# Assassination-specific config
_ASSN_META = _EVENT_META.get('assassination', {})
ASSN_CHANGE_CHANCE = _ASSN_META.get('change_chance', 0.5)

_REBEL_META        = _EVENT_META.get('rebellion', {})
REBEL_MIN_TILES    = _REBEL_META.get('min_tiles', 30)
REBEL_SPLIT_FRAC   = _REBEL_META.get('split_fraction', 0.33)
REBEL_TILES_SCALE  = _REBEL_META.get('tiles_scale', 5000)

# ── Event type constants ───────────────────────────────────────────────────────
EVT_EARTHQUAKE   = 'earthquake'
EVT_FLOOD        = 'flood'
EVT_DROUGHT      = 'drought'
EVT_PLAGUE       = 'plague'
EVT_GOLD_RUSH    = 'gold_rush'
EVT_FOREST_FIRE  = 'forest_fire'
EVT_VOLCANIC_ASH = 'volcanic_ash'
EVT_RICH_VEIN    = 'rich_vein'
EVT_MIGRATION    = 'migration'
EVT_ASSASSINATION= 'assassination'
EVT_REBELLION    = 'rebellion'


class WorldEvent:
    def __init__(self, event_type, turn, cx, cy, radius, magnitude, description, effects):
        self.type        = event_type
        self.turn        = turn
        self.cx          = cx
        self.cy          = cy
        self.radius      = radius
        self.magnitude   = magnitude
        self.description = description
        self.effects     = effects

    def to_dict(self):
        return {
            'type':        self.type,
            'turn':        self.turn,
            'location':    [self.cx, self.cy],
            'radius':      self.radius,
            'magnitude':   self.magnitude,
            'description': self.description,
            'effects':     self.effects,
        }


# ─────────────────────────────────────────────────────────────────────────────
class EventSystem:
    def __init__(self, game):
        self.game    = game
        self.history : list[WorldEvent] = []
        self._cooldowns = {k: 0 for k in EVENT_RARITY}

    def tick(self, turn):
        fired = []
        for evt_type, rarity in EVENT_RARITY.items():
            cd = self._cooldowns[evt_type]
            if cd > 0:
                self._cooldowns[evt_type] -= 1
                continue
            if random.random() < 1.0 / rarity:
                evt = self._fire(evt_type, turn)
                if evt:
                    fired.append(evt)
                    self._cooldowns[evt_type] = EVENT_COOLDOWN[evt_type]
        return fired

    def _fire(self, evt_type, turn):
        w = self.game.world
        land = [(x,y) for y in range(5, MAP_SIZE-5)
                       for x in range(5, MAP_SIZE-5)
                       if w.t(x,y).is_land()]
        if not land:
            return None
        cx, cy = random.choice(land)
        mag = random.randint(3, 10)

        dispatch = {
            EVT_EARTHQUAKE:    self._earthquake,
            EVT_FLOOD:         self._flood,
            EVT_DROUGHT:       self._drought,
            EVT_PLAGUE:        self._plague,
            EVT_GOLD_RUSH:     self._gold_rush,
            EVT_FOREST_FIRE:   self._forest_fire,
            EVT_VOLCANIC_ASH:  self._volcanic_ash,
            EVT_RICH_VEIN:     self._rich_vein,
            EVT_MIGRATION:     self._migration,
            EVT_ASSASSINATION: self._assassination,
            EVT_REBELLION:     self._rebellion,
        }
        fn = dispatch.get(evt_type)
        return fn(turn, cx, cy, mag) if fn else None

    # ── individual events ──────────────────────────────────────────────────
    def _earthquake(self, turn, cx, cy, mag):
        w       = self.game.world
        radius  = mag
        effects = {'terrain_changed': 0, 'armies_damaged': 0,
                   'buildings_destroyed': 0}

        for tile in w.tiles_in_radius(cx, cy, radius):
            dist = math.dist((cx,cy),(tile.x,tile.y))
            intensity = 1.0 - dist/radius

            if tile.terrain == TERRAIN_PLAIN and random.random() < intensity * 0.15:
                tile.terrain = TERRAIN_MOUNTAIN
                tile.deposits[RES_METAL] += random.uniform(1,4)
                effects['terrain_changed'] += 1

            if tile.entity in ('castle','farm','mine') and random.random() < intensity * 0.4:
                tile.entity = None
                effects['buildings_destroyed'] += 1

            for army in list(tile.armies):
                if random.random() < intensity * 0.5:
                    dmg = random.randint(1, max(1, int(mag * intensity)))
                    army.health = max(0, army.health - dmg)
                    effects['armies_damaged'] += 1
                    if not army.is_alive():
                        self.game.ai[army.nation]._remove_army(army)

        desc = (f"EARTHQUAKE mag-{mag} near ({cx},{cy})! "
                f"{effects['buildings_destroyed']} buildings destroyed, "
                f"{effects['armies_damaged']} armies damaged.")
        evt = WorldEvent(EVT_EARTHQUAKE, turn, cx, cy, radius, mag, desc, effects)
        self.history.append(evt)
        self.game.log(turn, f"[{EVENT_LABEL[EVT_EARTHQUAKE]}] {desc}")
        return evt

    def _flood(self, turn, cx, cy, mag):
        w      = self.game.world
        radius = mag + 3
        effects = {'tiles_flooded': 0, 'farms_destroyed': 0}

        for tile in w.tiles_in_radius(cx, cy, radius):
            if tile.terrain in (TERRAIN_PLAIN, TERRAIN_DESERT, TERRAIN_FOREST):
                dist = math.dist((cx,cy),(tile.x,tile.y))
                if random.random() < (1 - dist/radius) * 0.5:
                    if tile.entity == 'farm':
                        tile.entity = None
                        effects['farms_destroyed'] += 1
                    tile.terrain = TERRAIN_RIVER
                    tile.deposits[RES_FOOD] = max(tile.deposits[RES_FOOD],
                                                   random.uniform(2,5))
                    effects['tiles_flooded'] += 1

        desc = (f"FLOOD near ({cx},{cy})! "
                f"{effects['tiles_flooded']} tiles flooded, "
                f"{effects['farms_destroyed']} farms washed away. (rivers will recede)")
        evt = WorldEvent(EVT_FLOOD, turn, cx, cy, radius, mag, desc, effects)
        self.history.append(evt)
        self.game.log(turn, f"[{EVENT_LABEL[EVT_FLOOD]}] {desc}")
        self.game.pending_recoveries.append((turn+12, cx, cy, radius, 'flood'))
        return evt

    def _drought(self, turn, cx, cy, mag):
        effects = {'nations_affected': 0, 'food_lost': 0}
        radius  = mag * 3

        for nation in self.game.nations:
            if not nation.alive: continue
            cap = nation.capital
            if not cap: continue
            if math.dist((cx,cy),(cap.x,cap.y)) <= radius:
                food_penalty = mag * 5
                nation.res[RES_FOOD] = max(0, nation.res[RES_FOOD] - food_penalty)
                effects['nations_affected'] += 1
                effects['food_lost'] += food_penalty

        desc = (f"DROUGHT near ({cx},{cy}) radius {radius}! "
                f"{effects['nations_affected']} nations lost {effects['food_lost']} food.")
        evt = WorldEvent(EVT_DROUGHT, turn, cx, cy, radius, mag, desc, effects)
        self.history.append(evt)
        self.game.log(turn, f"[{EVENT_LABEL[EVT_DROUGHT]}] {desc}")
        return evt

    def _plague(self, turn, cx, cy, mag):
        effects = {'pop_lost': 0, 'armies_weakened': 0}
        radius  = mag * 2

        for nation in self.game.nations:
            if not nation.alive: continue
            for town in nation.towns:
                if math.dist((cx,cy),(town.x,town.y)) <= radius:
                    lost = int(town.population * 0.1 * mag / 10)
                    town.population = max(5, town.population - lost)
                    effects['pop_lost'] += lost
            for army in nation.armies:
                if math.dist((cx,cy),(army.x,army.y)) <= radius:
                    if random.random() < 0.3:
                        army.health = max(1, int(army.health * 0.7))
                        effects['armies_weakened'] += 1

        desc = (f"PLAGUE outbreak near ({cx},{cy})! "
                f"{effects['pop_lost']} population lost, "
                f"{effects['armies_weakened']} armies weakened.")
        evt = WorldEvent(EVT_PLAGUE, turn, cx, cy, radius, mag, desc, effects)
        self.history.append(evt)
        self.game.log(turn, f"[{EVENT_LABEL[EVT_PLAGUE]}] {desc}")
        return evt

    def _gold_rush(self, turn, cx, cy, mag):
        w      = self.game.world
        radius = mag + 2
        effects = {'gold_added': 0, 'tiles': 0}

        for tile in w.tiles_in_radius(cx, cy, radius):
            if tile.is_land() and random.random() < 0.3:
                amount = random.uniform(1, mag * 0.5)
                tile.deposits[RES_GOLD] += amount
                effects['gold_added'] += amount
                effects['tiles'] += 1

        w._calc_resource_values()
        desc = (f"GOLD RUSH near ({cx},{cy})! "
                f"New deposits found on {effects['tiles']} tiles "
                f"(+{effects['gold_added']:.0f} total gold value).")
        evt = WorldEvent(EVT_GOLD_RUSH, turn, cx, cy, radius, mag, desc, effects)
        self.history.append(evt)
        self.game.log(turn, f"[{EVENT_LABEL[EVT_GOLD_RUSH]}] {desc}")
        return evt

    def _forest_fire(self, turn, cx, cy, mag):
        w      = self.game.world
        radius = mag + 2
        effects = {'forests_burned': 0, 'plains_created': 0}

        for tile in w.tiles_in_radius(cx, cy, radius):
            dist = math.dist((cx,cy),(tile.x,tile.y))
            if tile.terrain == TERRAIN_FOREST and random.random() < (1-dist/radius)*0.7:
                tile.terrain  = TERRAIN_PLAIN
                tile.deposits[RES_WOOD] = 0
                tile.deposits[RES_FOOD] = max(tile.deposits[RES_FOOD], 1.5)
                if tile.entity == 'farm':
                    tile.entity = None
                effects['forests_burned'] += 1
                effects['plains_created'] += 1

        desc = (f"FOREST FIRE near ({cx},{cy})! "
                f"{effects['forests_burned']} forest tiles burned to plains.")
        evt = WorldEvent(EVT_FOREST_FIRE, turn, cx, cy, radius, mag, desc, effects)
        self.history.append(evt)
        self.game.log(turn, f"[{EVENT_LABEL[EVT_FOREST_FIRE]}] {desc}")
        return evt

    def _volcanic_ash(self, turn, cx, cy, mag):
        w      = self.game.world
        radius = mag + 5
        effects = {'tiles_covered': 0, 'food_lost': 0}

        mountains = [(t.x,t.y) for y in range(MAP_SIZE) for x in range(MAP_SIZE)
                     for t in [w.t(x,y)] if t.terrain==TERRAIN_MOUNTAIN]
        if mountains:
            cx,cy = min(mountains, key=lambda p: math.dist((cx,cy),p))

        for tile in w.tiles_in_radius(cx, cy, radius):
            dist = math.dist((cx,cy),(tile.x,tile.y))
            if tile.is_land() and tile.terrain != TERRAIN_MOUNTAIN:
                if random.random() < (1-dist/radius)*0.5:
                    if tile.entity == 'farm':
                        tile.entity = None
                    if tile.terrain != TERRAIN_OCEAN:
                        tile.terrain = TERRAIN_DESERT
                        tile.deposits[RES_FOOD] *= 0.3
                        effects['tiles_covered'] += 1

        for nation in self.game.nations:
            if not nation.alive: continue
            cap = nation.capital
            if cap and math.dist((cx,cy),(cap.x,cap.y)) <= radius:
                penalty = mag * 3
                nation.res[RES_FOOD] = max(0, nation.res[RES_FOOD] - penalty)
                effects['food_lost'] += penalty

        desc = (f"VOLCANIC ASH from ({cx},{cy})! "
                f"{effects['tiles_covered']} tiles covered, "
                f"{effects['food_lost']} food lost to ash fall.")
        evt = WorldEvent(EVT_VOLCANIC_ASH, turn, cx, cy, radius, mag, desc, effects)
        self.history.append(evt)
        self.game.log(turn, f"[{EVENT_LABEL[EVT_VOLCANIC_ASH]}] {desc}")
        return evt

    def _rich_vein(self, turn, cx, cy, mag):
        w      = self.game.world
        radius = mag // 2 + 2
        effects = {'metal_added': 0, 'tiles': 0}

        for tile in w.tiles_in_radius(cx, cy, radius):
            if tile.is_land():
                amount = random.uniform(2, mag * 0.8)
                tile.deposits[RES_METAL] += amount
                effects['metal_added'] += amount
                effects['tiles'] += 1

        w._calc_resource_values()
        desc = (f"RICH VEIN discovered near ({cx},{cy})! "
                f"+{effects['metal_added']:.0f} metal across {effects['tiles']} tiles.")
        evt = WorldEvent(EVT_RICH_VEIN, turn, cx, cy, radius, mag, desc, effects)
        self.history.append(evt)
        self.game.log(turn, f"[{EVENT_LABEL[EVT_RICH_VEIN]}] {desc}")
        return evt

    def _migration(self, turn, cx, cy, mag):
        effects = {'nation': None, 'pop_gained': 0}

        best_nation = None
        best_dist   = float('inf')
        for nation in self.game.nations:
            if not nation.alive or not nation.towns: continue
            cap = nation.capital
            if not cap: continue
            d = math.dist((cx,cy),(cap.x,cap.y))
            if d < best_dist:
                best_dist   = d
                best_nation = nation

        if best_nation:
            town = max(best_nation.towns, key=lambda t: t.population)
            gain = mag * 15
            town.population += gain
            effects['nation']     = best_nation.name
            effects['pop_gained'] = gain
            desc = (f"MIGRATION wave reaches {best_nation.name}! "
                    f"{town.name} gains {gain} population.")
            self.game.log(turn, f"[{EVENT_LABEL[EVT_MIGRATION]}] {desc}",
                          best_nation.idx)
        else:
            desc = "Migration wave dissipated."

        evt = WorldEvent(EVT_MIGRATION, turn, cx, cy, 0, mag, desc, effects)
        self.history.append(evt)
        return evt

    def _assassination(self, turn, cx, cy, mag):
        """A nation's leader is killed. The successor may have a different trait."""
        # Pick a random alive nation, weighted toward those at war (more instability)
        candidates = [n for n in self.game.nations if n.alive]
        if not candidates:
            return None

        weights = []
        for n in candidates:
            at_war = sum(1 for o in self.game.nations if n.at_war_with(o.idx))
            weights.append(1 + at_war)

        total = sum(weights)
        r = random.random() * total
        target = candidates[0]
        for n, w in zip(candidates, weights):
            r -= w
            if r <= 0:
                target = n
                break

        old_trait  = target.trait
        old_name   = old_trait['name'] if old_trait else 'Unknown'
        effects    = {'nation': target.name, 'old_trait': old_name, 'new_trait': old_name,
                      'trait_changed': False}

        if random.random() < ASSN_CHANGE_CHANCE:
            # New leader, different vision — pick a random different trait
            all_traits = self.game.trait_list
            others = [t for t in all_traits if t['id'] != (old_trait or {}).get('id')]
            if others:
                new_trait = random.choice(others)
                target.trait = new_trait
                effects['new_trait']    = new_trait['name']
                effects['trait_changed'] = True
        # else: loyal general keeps the same policies

        if effects['trait_changed']:
            desc = (f"ASSASSINATION! {target.name}'s leader is dead! "
                    f"New ruler brings {effects['new_trait']} vision "
                    f"(was {old_name}).")
        else:
            desc = (f"ASSASSINATION! {target.name}'s leader is dead! "
                    f"The new ruler upholds {old_name} tradition.")

        evt = WorldEvent(EVT_ASSASSINATION, turn, cx, cy, 0, mag, desc, effects)
        self.history.append(evt)
        self.game.log(turn, f"[{EVENT_LABEL[EVT_ASSASSINATION]}] {desc}", target.idx)
        return evt

    def _rebellion(self, turn, cx, cy, mag):
        """Civil war: an empire fractures; a dead slot becomes a rebel state.

        Every alive nation has a size-based rebellion chance multiplied by its
        trait's rebellion_prone_mul.  Nations are checked from most-likely to
        least-likely; the first to pass its roll becomes the fractured parent.
        If none pass, no rebellion fires this cycle.
        """
        alive = [n for n in self.game.nations if n.alive]
        dead  = [n for n in self.game.nations
                 if not n.alive and n.rebellion_cooldown <= 0]
        if not dead or not alive:
            return None   # no free slot or no nations to fracture

        # Compute per-nation rebellion chance: proportional to territory,
        # scaled by trait modifier.  Cap at 0.9 so nothing is guaranteed.
        candidates = []
        for n in alive:
            base_chance = len(n.tiles) / REBEL_TILES_SCALE
            prone_mul   = n.trait_val('rebellion_prone_mul', 1.0)
            chance      = min(0.9, base_chance * prone_mul)
            candidates.append((chance, n))

        # Sort most-likely first, then roll each in turn; stop at first hit.
        candidates.sort(key=lambda x: x[0], reverse=True)
        parent = None
        for chance, n in candidates:
            if random.random() < chance:
                parent = n
                break

        if not parent:
            return None   # no nation's roll triggered — quiet turn

        rebel = self.game.spawn_rebel_nation(
            turn, parent,
            min_tiles=REBEL_MIN_TILES,
            split_fraction=REBEL_SPLIT_FRAC,
        )
        if not rebel:
            return None

        desc = (f"CIVIL WAR! {parent.name} fractures! "
                f"{rebel.name} rises as a rebel state [{rebel.trait['name']}] "
                f"with {len(rebel.tiles)} tiles.")
        effects = {
            'parent':       parent.name,
            'rebel':        rebel.name,
            'tiles_split':  len(rebel.tiles),
            'trait':        rebel.trait['name'],
        }

        evt = WorldEvent(EVT_REBELLION, turn, cx, cy, 0, mag, desc, effects)
        self.history.append(evt)
        self.game.log(turn, f"[{EVENT_LABEL[EVT_REBELLION]}] {desc}", rebel.idx)
        return evt
