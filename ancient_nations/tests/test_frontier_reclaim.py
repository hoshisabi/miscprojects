"""Frontier reclaim Phase 1 — raider incursions (default off in balance.json5)."""
import unittest
from unittest.mock import patch

import game as game_mod
from game import Game
from entities import Army, Battle
from snapshot import battle_dict, army_dict
import constants


class TestFrontierReclaimSynthetic(unittest.TestCase):
    def _living_tile(self, g):
        for n in g.nations:
            if n.alive and n.tiles:
                return next(iter(n.tiles))
        self.fail('no living nation tile')

    def _eligible_neighbor(self, g):
        nx, ny = self._living_tile(g)
        tx, ty = nx + 1, ny
        if tx >= constants.MAP_SIZE:
            tx, ty = nx - 1, ny
        tile = g.world.t(tx, ty)
        tile.owner = -1
        tile.was_released = True
        tile.neutral_vacant_turns = constants.FRONTIER_NEUTRAL_TURNS
        return tile

    def test_never_owned_vacancy_stays_zero(self):
        g = Game(seed=99, num_nations=4)
        t = g.world.t(50, 50)
        t.owner = -1
        t.was_released = False
        t.neutral_vacant_turns = 0
        with patch.object(constants, 'FRONTIER_RECLAIM_ENABLED', False):
            g._tick_neutral_vacancy()
        self.assertEqual(t.neutral_vacant_turns, 0)

    def test_released_vacancy_increments_when_disabled(self):
        g = Game(seed=99, num_nations=4)
        t = g.world.t(50, 50)
        t.owner = -1
        t.was_released = True
        t.neutral_vacant_turns = 0
        with patch.object(constants, 'FRONTIER_RECLAIM_ENABLED', False):
            g._tick_neutral_vacancy()
        self.assertEqual(t.neutral_vacant_turns, 1)

    def test_spawn_when_enabled_on_eligible_tile(self):
        g = Game(seed=101, num_nations=4)
        tile = self._eligible_neighbor(g)
        with patch.object(game_mod, 'FRONTIER_SPAWN_CHANCE', 1.0), \
             patch.object(game_mod, 'FRONTIER_MAX_RAIDERS', 12):
            g._tick_frontier_spawns(10)
        self.assertTrue(any(a.frontier_raider for a in tile.armies))

    def test_no_spawn_on_tile_with_nation_army(self):
        g = Game(seed=104, num_nations=4)
        tile = self._eligible_neighbor(g)
        nation = next(n for n in g.nations if n.alive)
        guest = Army(tile.x, tile.y, nation.idx, level=2)
        tile.armies.append(guest)
        tile.army = guest
        with patch.object(game_mod, 'FRONTIER_SPAWN_CHANCE', 1.0), \
             patch.object(game_mod, 'FRONTIER_MAX_RAIDERS', 12):
            g._tick_frontier_spawns(10)
        self.assertFalse(any(a.frontier_raider for a in tile.armies))

    def test_raider_win_steps_onto_fought_tile(self):
        g = Game(seed=105, num_nations=4)
        nation = next(n for n in g.nations if n.alive)
        rx, ry = 40, 40
        dx, dy = 41, 40
        r_tile = g.world.t(rx, ry)
        d_tile = g.world.t(dx, dy)
        r_tile.owner = -1
        d_tile.owner = nation.idx
        raider = Army(rx, ry, -1, level=5)
        raider.frontier_raider = True
        raider.spawn_turn = 1
        raider.health = raider.max_health = 200
        defender = Army(dx, dy, nation.idx, level=1)
        defender.health = 1
        defender.max_health = 1
        r_tile.armies.append(raider)
        r_tile.army = raider
        d_tile.armies.append(defender)
        d_tile.army = defender
        with patch.object(g.combat, 'resolve', return_value=(
                -1,
                Battle(10, dx, dy, -1, nation.idx, raider, defender, -1, 0, 1),
        )):
            g._resolve_raider_vs_nation(raider, defender, d_tile, 10)
        self.assertEqual((raider.x, raider.y), (dx, dy))
        self.assertIn(raider, d_tile.armies)
        self.assertNotIn(raider, r_tile.armies)

    def test_battle_dict_labels_raider_not_last_nation(self):
        names = ['Alpha', 'Beta', 'Carius']
        b = Battle(1, 0, 0, -1, 0, None, None, -1, 0, 1)
        d = battle_dict(b, names)
        self.assertEqual(d['attacker'], 'Frontier raiders')
        self.assertEqual(d['winner'], 'Frontier raiders')
        self.assertNotEqual(d['attacker'], 'Carius')
        a = Army(0, 0, -1, level=2)
        a.frontier_raider = True
        self.assertEqual(army_dict(a, names)['nation'], 'Frontier raiders')

    def test_no_spawn_when_disabled(self):
        g = Game(seed=102, num_nations=4)
        tile = self._eligible_neighbor(g)
        with patch.object(game_mod, 'FRONTIER_RECLAIM_ENABLED', False), \
             patch.object(game_mod, 'FRONTIER_SPAWN_CHANCE', 1.0):
            g._tick_frontier_system(10)
        self.assertFalse(tile.armies)

    def test_ttl_disbands_raider(self):
        g = Game(seed=103, num_nations=4)
        tile = g.world.t(40, 40)
        tile.owner = -1
        army = Army(40, 40, -1, level=2)
        army.frontier_raider = True
        army.spawn_turn = 1
        tile.armies.append(army)
        ttl = constants.FRONTIER_RAIDER_MAX_TTL
        g._tick_frontier_raider_ttl(1 + ttl)
        self.assertFalse(tile.armies)


class TestFrontierReclaimSimBacked(unittest.TestCase):
    def test_spawn_possible_on_long_run_with_forced_rates(self):
        """Search seeds for one run where bleed + high spawn chance produces a raider."""
        found = False
        for seed in range(1, 25):
            g = Game(seed=seed, num_nations=6)
            with patch.object(game_mod, 'FRONTIER_RECLAIM_ENABLED', True), \
                 patch.object(game_mod, 'FRONTIER_SPAWN_CHANCE', 0.05), \
                 patch.object(game_mod, 'FRONTIER_NEUTRAL_TURNS', 10):
                for _ in range(400):
                    g.process_turn()
            if g._frontier_raider_count() > 0:
                found = True
                break
            msgs = ' '.join(m for _t, m, _n in g.logs)
            if 'Frontier raiders emerge' in msgs:
                found = True
                break
        self.assertTrue(found, 'expected at least one frontier spawn in seed search 1-24')


if __name__ == '__main__':
    unittest.main()
