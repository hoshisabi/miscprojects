"""
ai.py – Nation AI decision making. Each turn every living nation:
  1. Evaluates its resource situation
  2. Decides on expansion / development
  3. Manages armies (spawn, order, move)
  4. Handles diplomacy (trade, war, peace)
"""
import random
import math
from constants import *
from entities import Army, Town
from pathfinding import find_path


# ─────────────────────────────────────────────────────────────────────────────
class NationAI:
    def __init__(self, nation, world, game):
        self.n     = nation
        self.world = world
        self.game  = game

    # ── main entry ────────────────────────────────────────────────────────
    def tick(self, turn):
        if not self.n.alive: return
        self._check_surrender(turn)
        if not self.n.alive: return   # may have just surrendered
        self._tick_diplomacy(turn)
        self._manage_armies(turn)
        self._expansion_decisions(turn)
        self._development_decisions(turn)
        self._trade_decisions(turn)

    # ── diplomacy ─────────────────────────────────────────────────────────
    def _resolve_allied_to_both_sides_war(self, turn):
        """If allied to both sides of a war, stress builds until the younger treaty breaks."""
        allies = self.n.allies()
        if len(allies) != 2:
            self.n.alliance_contradiction_turns = 0
            return
        a, b = allies[0], allies[1]
        g = self.game
        if not (g.nations[a].alive and g.nations[b].alive):
            self.n.alliance_contradiction_turns = 0
            return
        if not g.nations[a].at_war_with(b):
            self.n.alliance_contradiction_turns = 0
            return
        age_a = self.n.alliance_age.get(a, 0)
        age_b = self.n.alliance_age.get(b, 0)
        younger = a if age_a <= age_b else b
        older = b if younger == a else a
        self.n.alliance_contradiction_turns += 1
        if self.n.alliance_contradiction_turns < ALLIANCE_STRESS_BREAK_TURNS:
            return
        self.n.alliance_contradiction_turns = 0
        younger_n = g.nations[younger]
        self.n.break_alliance(younger, betrayal=False)
        if younger_n.alive and younger_n.allied_with(self.n.idx):
            younger_n.break_alliance(self.n.idx, betrayal=False)
        self.game.log(turn,
            f"[DIPLO] {self.n.name} ends alliance with {younger_n.name} "
            f"(divided loyalty vs {g.nations[older].name})",
            self.n.idx)

    def _tick_diplomacy(self, turn):
        self.n.tick_diplomacy()
        self._resolve_allied_to_both_sides_war(turn)
        my_str = self.n.army_strength() or 1

        for other in self.game.nations:
            if other.idx == self.n.idx or not other.alive: continue
            oi = other.idx

            # --- WAR: seek peace if losing badly ---
            if self.n.at_war_with(oi):
                their_str = other.army_strength() or 1
                ratio = my_str / their_str
                # Don't negotiate peace when desperate enough to surrender —
                # _check_surrender already ran this tick and gets priority
                surrender_desperate = (
                    len(self.n.tiles) < SURRENDER_TILE_THRESHOLD
                    or (not self.n.armies and len(self.n.tiles) < 20)
                )
                if not surrender_desperate and ratio < 0.5 and random.random() < 0.15:
                    self._offer_peace(other, turn)

            # --- ALLIANCE: mutual-defence + break check + union vote ---
            elif self.n.allied_with(oi):
                self._check_mutual_defence(other, turn, my_str)
                self._check_alliance_break(other, turn, my_str)
                ally_age = min(self.n.alliance_age.get(oi, 0),
                               other.alliance_age.get(self.n.idx, 0))
                self._check_union_vote(other, turn, ally_age)

            # --- PEACE (warrable): consider declaring war ---
            elif self.n.can_declare_war(oi):
                their_str = other.army_strength() or 1
                ratio = my_str / (their_str or 1)
                adjacent = self._is_adjacent_to(other)
                if adjacent and ratio >= AI_AGGRO_RATIO:
                    if random.random() < 0.12:
                        self._declare_war(other, turn)

            # --- PEACE: consider forming alliance ---
            if (not self.n.at_war_with(oi)
                    and not self.n.allied_with(oi)
                    and self.n.can_ally(oi)
                    and other.can_ally(self.n.idx)):
                if self._should_ally(other, my_str):
                    if random.random() < AI_ALLY_CHANCE:
                        self._propose_alliance(other, turn)

    def _declare_war(self, other, turn):
        # Warn allies that we're breaking a treaty
        if self.n.allied_with(other.idx):
            self.game.log(turn,
                f"[ALLY] {self.n.name} BETRAYS alliance with {other.name}!",
                self.n.idx)
        self.n.declare_war(other.idx, turn)
        other.declare_war(self.n.idx, turn)
        self.game.log(turn,
            f"[WAR]  {self.n.name} declares WAR on {other.name}!",
            self.n.idx)

    def _offer_peace(self, other, turn):
        their_str = other.army_strength() or 1
        my_str    = self.n.army_strength() or 1
        if their_str / (my_str or 1) > 0.8 or random.random() < 0.4:
            self.n.make_peace(other.idx, turn)
            other.make_peace(self.n.idx, turn)
            self.game.log(turn,
                f"[peace]  {self.n.name} and {other.name} sign PEACE.",
                self.n.idx)

    # ── alliance helpers ──────────────────────────────────────────────────
    def _should_ally(self, other, my_str):
        """True when it's strategically wise to ally with other."""
        # Refuse to ally a known betrayer (reputation penalty)
        if other.betrayed_turns > 20 and random.random() < BETRAYAL_ALLY_CHANCE_MOD:
            return False
        rivals = [n for n in self.game.nations
                  if n.alive and n.idx != self.n.idx and n.idx != other.idx]
        if not rivals:
            return False
        top_rival_str = max(n.army_strength() for n in rivals) or 1
        combined      = my_str + (other.army_strength() or 1)
        return top_rival_str > my_str * 1.2 or combined < top_rival_str * 1.5

    def _propose_alliance(self, other, turn):
        """Both sides mutually agree to an alliance."""
        # Other AI accepts if it also finds the alliance strategically sound
        other_ai  = self.game.ai[other.idx]
        their_str = other.army_strength() or 1
        if other_ai._should_ally(self.n, their_str) or random.random() < 0.3:
            self.n.form_alliance(other.idx)
            other.form_alliance(self.n.idx)
            self.game.log(turn,
                f"[ALLY] {self.n.name} and {other.name} form an ALLIANCE!",
                self.n.idx)

    def _check_mutual_defence(self, ally, turn, my_str):
        """If our ally is at war, consider joining on their side."""
        for enemy in self.game.nations:
            if not enemy.alive or enemy.idx == self.n.idx: continue
            if not ally.at_war_with(enemy.idx): continue
            if self.n.at_war_with(enemy.idx): continue   # already in it
            if not self.n.can_declare_war(enemy.idx): continue
            # Join if we're strong enough and not already overstretched
            wars_active = sum(1 for n in self.game.nations
                              if self.n.at_war_with(n.idx))
            if wars_active < 2 and random.random() < self.n.mutual_def_chance(ally.idx):
                self.n.declare_war(enemy.idx, turn)
                enemy.declare_war(self.n.idx, turn)
                self.game.log(turn,
                    f"[ALLY] {self.n.name} joins {ally.name}'s war against "
                    f"{enemy.name}!",
                    self.n.idx)

    def _check_alliance_break(self, ally, turn, my_str):
        """Break alliance if ally is becoming a threat or we want to attack them."""
        their_str = ally.army_strength() or 1
        # Betray if they're way stronger and adjacent (threat) — rare
        if their_str > my_str * 2.5 and self._is_adjacent_to(ally):
            if random.random() < 0.02:
                self._execute_betrayal(ally, turn)

    def _execute_betrayal(self, ally, turn):
        """Plunder ally's gold+metal, declare war, set surge/rep counters."""
        plunder = {}
        for r in (RES_GOLD, RES_METAL):
            amount = int(ally.res[r] * BETRAYAL_PLUNDER_RATE)
            ally.res[r]   = max(0, ally.res[r] - amount)
            self.n.res[r] = self.n.res.get(r, 0) + amount
            plunder[RESOURCE_NAMES[r]] = amount

        self.n.break_alliance(ally.idx, betrayal=True)
        ally.break_alliance(self.n.idx, betrayal=False)
        self.n.declare_war(ally.idx, turn)
        ally.declare_war(self.n.idx, turn)

        plunder_str = ' '.join(f"{v}{k}" for k, v in plunder.items())
        self.game.log(turn,
            f"[ALLY] {self.n.name} BETRAYS {ally.name}! "
            f"Plunders {plunder_str}. War declared!",
            self.n.idx)

    def _check_union_vote(self, ally, turn, ally_age):
        """Very long alliances may vote to merge.  Only the larger nation initiates
        (to avoid processing the same pair twice)."""
        if ally_age < UNION_VOTE_MIN_AGE:
            return
        # Only the larger nation calls the vote
        if len(self.n.tiles) < len(ally.tiles):
            return
        if random.random() > UNION_VOTE_CHANCE:
            return

        roll = random.random()
        if roll < UNION_SUCCESS_CHANCE:
            # Vote passes — smaller is absorbed, trait blended
            smaller = ally if len(ally.tiles) <= len(self.n.tiles) else self.n
            larger  = self.n if smaller is ally else ally
            # Blend: pick trait of whichever has more tiles (dominant culture)
            merged_trait = larger.trait or smaller.trait
            self.game.peaceful_annex(larger, smaller, merged_trait, turn)

        elif roll < UNION_SUCCESS_CHANCE + UNION_FAIL_BAD_CHANCE:
            # Vote fails badly — independence faction seizes power
            self.game.log(turn,
                f"[UNION] {self.n.name}+{ally.name} union vote REJECTED! "
                f"Independence faction takes control — war erupts!",
                self.n.idx)
            self._execute_betrayal(ally, turn)

        else:
            # Vote fails quietly — alliance holds, no hard feelings
            self.game.log(turn,
                f"[UNION] {self.n.name}+{ally.name} union vote failed. "
                f"Alliance continues.",
                self.n.idx)

    def _check_surrender(self, turn):
        """If critically outmatched and at war, consider surrendering."""
        enemies = [o for o in self.game.nations
                   if o.alive and self.n.at_war_with(o.idx)]
        if not enemies:
            return

        tile_count = len(self.n.tiles)
        my_str     = self.n.army_strength() or 1
        desperate  = (tile_count < SURRENDER_TILE_THRESHOLD
                      or (not self.n.armies and tile_count < 20))
        if not desperate:
            return

        strongest   = max(enemies, key=lambda o: o.army_strength())
        their_str   = strongest.army_strength()
        # If we have no armies at all, ratio is irrelevant — we're defenceless
        ratio = (my_str / their_str) if their_str > 0 else 0.0

        if ratio < SURRENDER_STRENGTH_RATIO and random.random() < SURRENDER_CHANCE:
            self.game.absorb_nation(strongest, self.n, turn)

    def _is_adjacent_to(self, other):
        """Check if this nation's territory borders another's."""
        other_tiles = other.tiles   # set of (x,y) — O(1) lookup
        for (x, y) in self.n.tiles:
            if ((x+1, y) in other_tiles or (x-1, y) in other_tiles or
                    (x, y+1) in other_tiles or (x, y-1) in other_tiles):
                return True
        return False

    def _resource_pressure(self):
        """0-1 score; high = running low on multiple resources."""
        shortages = 0
        for r in (RES_FOOD, RES_WOOD, RES_METAL):
            if self.n.res[r] < AI_LOW_RESOURCE:
                shortages += 1
        return shortages / 3.0

    # ── army management ───────────────────────────────────────────────────
    def _manage_armies(self, turn):
        # Move existing armies
        for army in list(self.n.armies):
            if not army.is_alive():
                self._remove_army(army)
                continue
            self._move_army(army, turn)
            army.turns_alive += 1

        # Spawn new armies if needed & affordable
        self._maybe_spawn_armies(turn)

    def _maybe_spawn_armies(self, turn):
        max_armies = max(4, len(self.n.tiles) // 10)
        current    = self.n.total_armies()
        if current >= max_armies: return

        # Pick highest-level available town
        for town in sorted(self.n.towns, key=lambda t: t.level, reverse=True):
            if self.n.res[RES_FOOD] < 30: break
            # Base level from resources; gold boosts above level 3
            gold_bonus = int(self.n.res[RES_GOLD] // 40)
            level = min(town.max_army_level, max(1, 2 + gold_bonus))
            cost  = self.n.army_build_cost(level)
            if self.n.can_afford(cost):
                self.n.spend(cost)
                army = Army(town.x, town.y, self.n.idx, level)
                army.order = self._pick_order()
                self.n.armies.append(army)
                t = self.world.t(town.x, town.y)
                t.armies.append(army)
                t.army = army
                self.game.log(turn,
                    f"  {self.n.name} trained Level-{level} army at {town.name}",
                    self.n.idx)
                break   # one spawn per turn

    def _pick_order(self):
        p = self._resource_pressure()
        if p > 0.6: return 'expand'
        at_war = any(self.n.at_war_with(o.idx)
                     for o in self.game.nations if o.idx!=self.n.idx and o.alive)
        if at_war: return 'attack'
        return random.choice(['expand','expand','attack','defend'])

    def _move_army(self, army, turn):
        if army.path:
            steps = max(1, int(self.world.t(army.x,army.y).terrain_speed()))
            for _ in range(steps):
                if not army.path: break
                nx,ny = army.path.pop(0)
                self._step_army(army, nx, ny, turn)
        else:
            self._assign_destination(army, turn)

    def _assign_destination(self, army, turn):
        if army.order == 'attack' or army.order == 'expand':
            dest = self._find_expansion_target(army)
        elif army.order == 'defend':
            dest = self._find_defense_target(army)
        else:
            dest = self._find_expansion_target(army)

        road_allied = {idx for idx in self.n.allies()
                       if self.n.alliance_tier(idx) >= 3}

        if dest:
            army.destination = dest
            army.path = find_path(self.world, army.x, army.y, dest[0], dest[1],
                                   self.n.idx, road_allied=road_allied)
            if not army.path:
                army.destination = None  # unreachable, retry next turn
        else:
            # Wander to unclaimed adjacent land
            candidates = []
            for t in self.world.tiles_in_radius(army.x, army.y, 5):
                if t.is_land() and t.owner != self.n.idx:
                    candidates.append((t.x, t.y))
            if candidates:
                d = random.choice(candidates)
                army.path = find_path(self.world, army.x, army.y, d[0], d[1],
                                       self.n.idx, road_allied=road_allied)

    def _find_expansion_target(self, army):
        """Find the best tile to conquer: prioritise needed resources."""
        needed = self._most_needed_resource()
        best_score = -1
        best_tile  = None
        cx, cy = army.x, army.y

        # Search radius around army
        for t in self.world.tiles_in_radius(cx, cy, 18):
            if not t.is_land(): continue
            if t.owner == self.n.idx: continue

            # Skip tiles owned by friends at peace
            if t.owner >= 0:
                other = self.game.nations[t.owner]
                if not self.n.at_war_with(t.owner): continue

            # Score based on resource deposits
            score = 0
            d = t.deposits
            score += d[needed] * 3
            for r in range(NUM_RESOURCES):
                score += d[r]
            # Penalise distance (Manhattan — no sqrt needed for relative scoring)
            dist = abs(t.x - cx) + abs(t.y - cy)
            score /= (dist + 1)

            if score > best_score:
                best_score = score
                best_tile  = (t.x, t.y)

        return best_tile

    def _find_defense_target(self, army):
        """Return coordinates of our most threatened border tile."""
        rows = self.world.tiles
        for x, y in self.n.tiles:
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx, ny = x+dx, y+dy
                if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE:
                    nb = rows[ny][nx]
                    if nb.armies and nb.armies[0].nation != self.n.idx:
                        return (x, y)
        return None

    def _most_needed_resource(self):
        """Return the resource index we have the least of (weighted by value)."""
        best = RES_FOOD
        best_score = float('inf')
        for r in (RES_FOOD, RES_WOOD, RES_METAL, RES_GOLD):
            score = self.n.res[r] / (self.game.world.resource_values[r] or 1)
            if score < best_score:
                best_score = score
                best = r
        return best

    def _step_army(self, army, nx, ny, turn):
        # Remove from old tile
        old_t = self.world.t(army.x, army.y)
        if army in old_t.armies: old_t.armies.remove(army)
        if old_t.army == army:   old_t.army = old_t.armies[0] if old_t.armies else None

        target_t = self.world.t(nx, ny)

        # Combat?
        enemy_armies = [a for a in target_t.armies if a.nation != self.n.idx]
        if enemy_armies:
            enemy = enemy_armies[0]
            atk_surge = self.n.army_surge_turns > 0
            # Tier-4 joint-command: check if defender has a Tier-4 ally also at war
            def_nation = self.game.nations[enemy.nation]
            tier4_def = any(
                def_nation.allied_with(a.idx)
                and def_nation.alliance_tier(a.idx) >= 4
                and a.at_war_with(self.n.idx)
                for a in self.game.nations
                if a.alive and a.idx != def_nation.idx
            )
            # Trait-based dice bonuses
            atk_trait_dice = self.n.trait_val('atk_dice_bonus', 0)
            def_trait_dice = def_nation.trait_val('def_dice_bonus', 0)
            if target_t.entity == 'castle':
                def_trait_dice += def_nation.trait_val('castle_def_bonus', 0)
            winner, battle = self.game.combat.resolve(
                army, enemy, target_t, turn,
                atk_surge=atk_surge, tier4_def=tier4_def,
                atk_trait_dice=atk_trait_dice, def_trait_dice=def_trait_dice)
            self.game.battles.append(battle)
            self.game.log(turn,
                f"[WAR]  Battle at ({nx},{ny}): {self.n.name} vs "
                f"{self.game.nations[enemy.nation].name} > "
                f"{'WIN' if winner==self.n.idx else 'LOSS'}",
                self.n.idx)

            if winner == self.n.idx:
                # Conquer tile
                self._conquer_tile(target_t, army, turn)
                if not enemy.is_alive():
                    self._remove_army(enemy, self.game.nations[enemy.nation])
                army.x, army.y = nx, ny
                target_t.armies.append(army)
                target_t.army = army
            else:
                # Repelled – stay put (army may be dead)
                if not army.is_alive():
                    self._remove_army(army)
                else:
                    army.x, army.y = old_t.x, old_t.y
                    old_t.armies.append(army)
                    old_t.army = army
                army.path = []
        else:
            # No enemy – just move
            army.x, army.y = nx, ny
            target_t.armies.append(army)
            target_t.army = army
            # Claim tile if not ours
            if target_t.owner != self.n.idx:
                self._conquer_tile(target_t, army, turn)

    def _conquer_tile(self, tile, army, turn):
        prev_owner = tile.owner
        if prev_owner == self.n.idx: return
        if prev_owner >= 0:
            prev_nation = self.game.nations[prev_owner]
            prev_nation.tiles.discard((tile.x, tile.y))
        self.world.set_tile_owner(tile.x, tile.y, self.n.idx)
        tile.captured_turn = turn
        self.n.tiles.add((tile.x, tile.y))
        # Transfer any town
        if tile.town:
            old_town = tile.town
            if old_town in (self.game.nations[prev_owner].towns if prev_owner>=0 else []):
                self.game.nations[prev_owner].towns.remove(old_town)
            old_town.nation = self.n.idx
            self.n.towns.append(old_town)
            self.game.log(turn,
                f"  {self.n.name} captured {old_town.name}!",
                self.n.idx)

    def _remove_army(self, army, nation=None):
        n = nation or self.n
        if army in n.armies:
            n.armies.remove(army)
        t = self.world.t(army.x, army.y)
        if army in t.armies: t.armies.remove(army)
        if t.army == army:   t.army = t.armies[0] if t.armies else None

    # ── expansion / development ───────────────────────────────────────────
    def _expansion_decisions(self, turn):
        """Claim neutral adjacent tiles using town influence."""
        radius_bonus = self.n.trait_val('town_radius_bonus', 0)
        for town in self.n.towns:
            r = town.radius + radius_bonus
            for tile in self.world.tiles_in_radius(town.x, town.y, r):
                if tile.owner == -1 and tile.is_land():
                    self.world.set_tile_owner(tile.x, tile.y, self.n.idx)
                    self.n.tiles.add((tile.x, tile.y))

    def _development_decisions(self, turn):
        """Build farms, mines, roads."""
        if turn % 3 != (self.n.idx % 3): return   # stagger building
        w = self.world
        dcm = self.n.trait_val('dev_cost_mul', 1.0)   # Builder trait discount

        # Build farms near rivers if food is low
        farm_wood = DEV_FARM_WOOD * dcm
        if self.n.res[RES_FOOD] < AI_LOW_RESOURCE * 2:
            for (x,y) in random.sample(list(self.n.tiles), min(20, len(self.n.tiles))):
                t = w.t(x,y)
                if t.can_build_farm() and t.terrain == TERRAIN_RIVER:
                    if self.n.res[RES_WOOD] >= farm_wood:
                        t.entity = 'farm'
                        self.n.res[RES_WOOD] -= farm_wood
                        self.n.res[RES_FOOD] -= DEV_FARM_FOOD
                        break

        # Build mines in mountains if metal low
        mine_wood  = DEV_MINE_WOOD  * dcm
        mine_metal = DEV_MINE_METAL * dcm
        if self.n.res[RES_METAL] < AI_LOW_RESOURCE:
            for (x,y) in random.sample(list(self.n.tiles), min(20, len(self.n.tiles))):
                t = w.t(x,y)
                if t.terrain == TERRAIN_MOUNTAIN and t.entity is None:
                    if (self.n.res[RES_WOOD]  >= mine_wood and
                            self.n.res[RES_METAL] >= mine_metal):
                        t.entity = 'mine'
                        self.n.res[RES_WOOD]  -= mine_wood
                        self.n.res[RES_METAL] -= mine_metal
                        break

        # Build roads between towns (if wood available)
        if self.n.res[RES_WOOD] > 60 and len(self.n.towns) > 1:
            towns = self.n.towns
            if len(towns) >= 2:
                t1 = random.choice(towns)
                t2 = min([t for t in towns if t is not t1],
                         key=lambda t: math.dist((t1.x,t1.y),(t.x,t.y)),
                         default=None)
                if t2:
                    path = find_path(w, t1.x, t1.y, t2.x, t2.y, self.n.idx)
                    road_unit = (DEV_ROAD_WOOD + DEV_ROAD_METAL) * dcm
                    cost = len(path) * road_unit
                    if self.n.res[RES_WOOD] >= cost and cost > 0:
                        self.n.res[RES_WOOD] -= cost
                        for (rx,ry) in path:
                            rt = w.t(rx,ry)
                            if rt.is_land():
                                rt.road = True

        # Build castles at border tiles with armies
        castle_wood  = DEV_CASTLE_WOOD  * dcm
        castle_metal = DEV_CASTLE_METAL * dcm
        if self.n.res[RES_WOOD] >= castle_wood and self.n.res[RES_METAL] >= castle_metal:
            for army in self.n.armies:
                t = w.t(army.x, army.y)
                if (t.entity is None and t.town is None and
                        t.is_land() and t.terrain != TERRAIN_OCEAN):
                    is_border = any(nb.owner != self.n.idx
                                    for nb in w.neighbors4(army.x, army.y))
                    if is_border and random.random() < 0.05:
                        t.entity = 'castle'
                        self.n.res[RES_WOOD]  -= castle_wood
                        self.n.res[RES_METAL] -= castle_metal
                        break

        # Spawn new towns where population pressure exists
        self._maybe_spawn_town(turn)

    def _maybe_spawn_town(self, turn):
        """Spawn a new town if capital is level 3+ and we have room."""
        if self.n.res[RES_WOOD] < 50 or self.n.res[RES_FOOD] < 50: return
        if len(self.n.towns) >= 8: return
        capital = self.n.capital
        if not capital or capital.level < 3: return
        if random.random() > 0.03: return  # low chance per turn

        # Find a good spot ~10-15 tiles from capital, on plains/forest, owned
        candidates = []
        for (x,y) in self.n.tiles:
            t = self.world.t(x,y)
            if (t.town is None and t.entity is None and
                    t.terrain in (TERRAIN_PLAIN, TERRAIN_FOREST)):
                d = math.dist((capital.x, capital.y), (x, y))
                if 10 <= d <= 20:
                    candidates.append((x,y))

        if candidates:
            x,y = random.choice(candidates)
            town = Town(x, y, self.n.idx, is_capital=False)
            self.world.t(x,y).town = town
            self.n.towns.append(town)
            self.n.res[RES_WOOD]  -= 30
            self.n.res[RES_FOOD]  -= 20
            self.game.log(turn,
                f"  {self.n.name} founded {town.name} at ({x},{y})",
                self.n.idx)

    # ── trade ─────────────────────────────────────────────────────────────
    def _trade_decisions(self, turn):
        if random.random() > AI_TRADE_CHANCE: return
        my_surplus = self._surplus_resource()
        my_need    = self._most_needed_resource()
        if my_surplus == my_need: return

        for other in self.game.nations:
            if other.idx == self.n.idx or not other.alive: continue
            if self.n.at_war_with(other.idx): continue
            their_surplus = self._surplus_of(other)
            their_need    = self._need_of(other)

            # Mutually beneficial?
            if their_surplus == my_need and their_need == my_surplus:
                # Merchant trait: use the better of the two sides' multiplier
                trade_mul = max(self.n.trait_val('trade_mul', 1.0),
                                other.trait_val('trade_mul', 1.0))
                amount = int(20 * trade_mul)
                if (self.n.res[my_surplus] >= amount and
                        other.res[their_surplus] >= amount):
                    self.n.res[my_surplus]    -= amount
                    self.n.res[my_need]       += amount
                    other.res[their_surplus]  -= amount
                    other.res[their_need]     += amount
                    self.n.history['trades_done'] += 1
                    other.history['trades_done']  += 1
                    self.game.log(turn,
                        f"  {self.n.name} <> {other.name}: "
                        f"trade {RESOURCE_NAMES[my_surplus]}<>"
                        f"{RESOURCE_NAMES[my_need]}",
                        self.n.idx)
                    break

    def _surplus_resource(self):
        best=RES_FOOD; best_v=-1
        for r in range(NUM_RESOURCES):
            v = self.n.res[r]
            if v > best_v: best_v=v; best=r
        return best

    def _surplus_of(self, other):
        best=RES_FOOD; best_v=-1
        for r in range(NUM_RESOURCES):
            v=other.res[r]
            if v>best_v: best_v=v; best=r
        return best

    def _need_of(self, other):
        best=RES_FOOD; best_v=float('inf')
        for r in range(NUM_RESOURCES):
            v=other.res[r]
            if v<best_v: best_v=v; best=r
        return best
